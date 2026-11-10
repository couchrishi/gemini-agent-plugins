#!/usr/bin/env python3
"""Computes asset MTBF, safety stock, reorder points (ROP), and spare parts expedite triggers."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "service_level_z": 1.65,
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
    z = float(cfg.get("service_level_z", 1.65))

    spares = data.get("spare_parts", [])
    plans: list[dict[str, Any]] = []

    for sp in spares:
        part_id = str(sp.get("part_id") or "PART-1")
        desc = str(sp.get("description") or part_id)
        criticality = str(sp.get("asset_criticality") or "STANDARD").upper()
        op_hours = float(sp.get("fleet_operating_hours") or 8760.0)
        failures = int(sp.get("observed_failures") or 0)
        qty_per_fail = float(sp.get("qty_per_failure") or 1.0)
        lead_days = float(sp.get("lead_time_days") or 14.0)
        on_hand = float(sp.get("on_hand_qty") or 0.0)
        on_order = float(sp.get("on_order_qty") or 0.0)
        unit_cost = float(sp.get("unit_cost_usd") or 0.0)

        # Conservative lower-bound MTBF when failures==0 (right-censored runtime, never infinite)
        censored = failures == 0
        eff_failures = failures if failures > 0 else 0.5
        mtbf_hours = op_hours / eff_failures
        hourly_demand = (qty_per_fail / mtbf_hours) * float(sp.get("installed_base_count", 1))
        lead_demand = hourly_demand * (lead_days * 24.0)
        safety_stock = math.ceil(z * math.sqrt(max(lead_demand, 0.01)))
        rop = math.ceil(lead_demand + safety_stock)
        net_avail = on_hand + on_order
        shortfall = max(0, rop - int(net_avail))

        if on_hand == 0 and criticality == "CRITICAL":
            status = "CRITICAL_STOCKOUT_EXPEDITE"
        elif shortfall > 0:
            status = "REORDER_BELOW_ROP"
        else:
            status = "ADEQUATE_COVERAGE"

        plans.append(
            {
                "part_id": part_id,
                "description": desc,
                "asset_criticality": criticality,
                "zero_failure_censored": censored,
                "mtbf_hours": round(mtbf_hours, 1),
                "lead_time_demand_units": round(lead_demand, 2),
                "safety_stock_units": safety_stock,
                "reorder_point_units": rop,
                "net_available_units": net_avail,
                "recommended_order_qty": shortfall,
                "estimated_order_cost_usd": round(shortfall * unit_cost, 2),
                "inventory_status": status,
            }
        )

    plans.sort(key=lambda x: (x["inventory_status"] == "ADEQUATE_COVERAGE", -x["estimated_order_cost_usd"]))

    return {
        "skill": "asset-reliability-spares-planner",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "parts_analyzed": len(plans),
            "critical_stockout_count": sum(1 for p in plans if p["inventory_status"] == "CRITICAL_STOCKOUT_EXPEDITE"),
            "reorder_triggered_count": sum(1 for p in plans if p["recommended_order_qty"] > 0),
            "total_recommended_spend_usd": round(sum(p["estimated_order_cost_usd"] for p in plans), 2),
        },
        "spares_plans": plans,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Asset Reliability & Critical Spares ROP Optimization",
            "",
            f"- **Parts Analyzed:** {s['parts_analyzed']} | **Critical Stockouts:** {s['critical_stockout_count']} | "
            f"**Reorder Triggers:** {s['reorder_triggered_count']} | **Recommended PO Spend:** ${s['total_recommended_spend_usd']:,.2f}",
            "",
            "| Part ID | Criticality | MTBF (h) | ROP | Net Avail | Order Qty | Est Spend | Status |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for p in result["spares_plans"]:
        lines.append(
            f"| `{p['part_id']}` | {p['asset_criticality']} | {p['mtbf_hours']:,.1f} | {p['reorder_point_units']} | "
            f"{p['net_available_units']:.0f} | **{p['recommended_order_qty']}** | ${p['estimated_order_cost_usd']:,.2f} | "
            f"`{p['inventory_status']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute MTBF, safety stock, and spare part reorder points.")
    parser.add_argument("--input", required=True, type=Path, help="Path to asset reliability and spares JSON")
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
