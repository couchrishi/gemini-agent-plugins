#!/usr/bin/env python3
"""Rolls up multi-level BOM standard vs actual costs, detects BOM cycles, and quantifies PPV & scrap variance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "ppv_alert_threshold_pct": 5.0,
}


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    return json.loads(Path(input_arg).read_text(encoding="utf-8"))


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    ppv_alert_pct = float(cfg.get("ppv_alert_threshold_pct", 5.0))

    items_map = {str(i["sku"]): i for i in data.get("items", []) if "sku" in i}
    edges = data.get("bom_edges", [])
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        children_by_parent.setdefault(str(e["parent_sku"]), []).append(e)

    target_skus = [str(s) for s in data.get("target_assemblies", [])]
    if not target_skus:
        all_children = {str(e.get("component_sku") or e.get("child_sku") or "") for e in edges}
        target_skus = sorted(p for p in children_by_parent if p not in all_children)

    cycles: list[list[str]] = []

    def _explode(sku: str, mult: float, stack: list[str], acc: dict[str, float]) -> None:
        if sku in stack:
            cycles.append(stack + [sku])
            return
        kids = children_by_parent.get(sku, [])
        if not kids:
            acc[sku] = acc.get(sku, 0.0) + mult
            return
        for edge in kids:
            comp = str(edge.get("component_sku") or edge.get("child_sku") or "")
            q = float(edge.get("qty_per_parent", 1.0))
            scrap_pct = float(edge.get("scrap_factor_pct", 0.0)) / 100.0
            eff_mult = mult * q * (1.0 + scrap_pct)
            _explode(comp, eff_mult, stack + [sku], acc)

    assembly_rollups: list[dict[str, Any]] = []
    component_variances_global: dict[str, dict[str, Any]] = {}

    for top_sku in target_skus:
        demand_qty = float((items_map.get(top_sku) or {}).get("production_volume", 1.0))
        leaf_qtys: dict[str, float] = {}
        _explode(top_sku, 1.0, [], leaf_qtys)

        std_unit_cost = 0.0
        act_unit_cost = 0.0
        for comp_sku, qty_per_fg in sorted(leaf_qtys.items()):
            cinfo = items_map.get(comp_sku, {})
            std_c = float(cinfo.get("standard_unit_cost_usd", 0.0))
            act_c = float(cinfo.get("actual_unit_cost_usd", std_c))
            std_ext = qty_per_fg * std_c
            act_ext = qty_per_fg * act_c
            std_unit_cost += std_ext
            act_unit_cost += act_ext

            total_ppv = (act_c - std_c) * qty_per_fg * demand_qty
            ppv_pct = ((act_c - std_c) / std_c * 100.0) if std_c > 0 else 0.0
            g = component_variances_global.setdefault(
                comp_sku,
                {
                    "component_sku": comp_sku,
                    "description": str(cinfo.get("description") or comp_sku),
                    "standard_unit_cost_usd": round(std_c, 4),
                    "actual_unit_cost_usd": round(act_c, 4),
                    "ppv_pct": round(ppv_pct, 2),
                    "total_ppv_impact_usd": 0.0,
                    "alert": abs(ppv_pct) >= ppv_alert_pct,
                },
            )
            g["total_ppv_impact_usd"] = round(g["total_ppv_impact_usd"] + total_ppv, 2)

        unit_delta = act_unit_cost - std_unit_cost
        delta_pct = (unit_delta / std_unit_cost * 100.0) if std_unit_cost > 0 else 0.0
        assembly_rollups.append(
            {
                "assembly_sku": top_sku,
                "production_volume": demand_qty,
                "standard_unit_cost_usd": round(std_unit_cost, 4),
                "actual_unit_cost_usd": round(act_unit_cost, 4),
                "unit_ppv_usd": round(unit_delta, 4),
                "ppv_pct": round(delta_pct, 2),
                "extended_variance_usd": round(unit_delta * demand_qty, 2),
                "leaf_component_count": len(leaf_qtys),
            }
        )

    drivers = sorted(component_variances_global.values(), key=lambda x: -abs(x["total_ppv_impact_usd"]))

    return {
        "skill": "bom-cost-rollup-variance",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "assemblies_rolled_up": len(assembly_rollups),
            "cycle_count": len(cycles),
            "total_extended_ppv_usd": round(sum(a["extended_variance_usd"] for a in assembly_rollups), 2),
            "alert_component_count": sum(1 for d in drivers if d["alert"]),
        },
        "bom_cycles_detected": cycles,
        "assembly_rollups": assembly_rollups,
        "component_ppv_drivers": drivers,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Multi-Level BOM Cost Rollup & Purchase Price Variance (PPV)",
            "",
            f"- **Assemblies Rolled Up:** {s['assemblies_rolled_up']} | **Cycles Detected:** {s['cycle_count']} | "
            f"**Total Extended PPV:** ${s['total_extended_ppv_usd']:+,.2f}",
            "",
            "| Assembly SKU | Volume | Std Cost | Actual Cost | Unit PPV | PPV % | Extended Variance |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for a in result["assembly_rollups"]:
        lines.append(
            f"| `{a['assembly_sku']}` | {a['production_volume']:,.0f} | ${a['standard_unit_cost_usd']:,.2f} | "
            f"${a['actual_unit_cost_usd']:,.2f} | ${a['unit_ppv_usd']:+,.2f} | {a['ppv_pct']:+.2f}% | "
            f"**${a['extended_variance_usd']:+,.2f}** |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explode multi-level BOMs and calculate standard vs actual PPV.")
    parser.add_argument("--input", required=True, type=Path, help="Path to BOM and item cost JSON")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
