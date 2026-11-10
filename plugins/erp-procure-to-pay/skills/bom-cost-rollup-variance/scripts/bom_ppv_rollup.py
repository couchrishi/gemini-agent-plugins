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


def _to_float(val: Any, default: Any = 0.0) -> float:
    num = _to_opt_float(val)
    if num is not None:
        return num
    d = _to_opt_float(default)
    return d if d is not None else 0.0


def _to_opt_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        num = float(val)
        return None if (num != num or abs(num) == float("inf")) else num
    s = str(val).strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    for ch in (",", "$", "€", "£", "¥", "%"):
        s = s.replace(ch, "")
    s = s.strip()
    if not s:
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    if num != num or abs(num) == float("inf"):
        return None
    return -num if neg else num


def _to_int(val: Any, default: Any = 0) -> int:
    num = _to_opt_float(val)
    if num is None:
        num = _to_opt_float(default)
    if num is None:
        return 0
    try:
        return int(round(num))
    except (ValueError, TypeError, OverflowError):
        return 0


def _to_opt_int(val: Any) -> int | None:
    num = _to_opt_float(val)
    if num is None:
        return None
    try:
        return int(round(num))
    except (ValueError, TypeError, OverflowError):
        return None


def _safe_date(val: Any) -> Any:
    import datetime as _dt
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val.date()
    if isinstance(val, _dt.date):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _safe_datetime(val: Any) -> Any:
    import datetime as _dt
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val if val.tzinfo else val.replace(tzinfo=_dt.timezone.utc)
    if isinstance(val, _dt.date):
        return _dt.datetime(val.year, val.month, val.day, tzinfo=_dt.timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _strip_null_items(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_strip_null_items(x) for x in obj if x is not None]
    if isinstance(obj, dict):
        return {k: _strip_null_items(v) for k, v in obj.items()}
    return obj


def _as_list(val: Any, default: list[Any] | None = None) -> list[Any]:
    if isinstance(val, list):
        return [x for x in val if x is not None]
    if val is None:
        return list(default) if default is not None else []
    if isinstance(val, (tuple, set)):
        return [x for x in val if x is not None]
    return list(default) if default is not None else []


def _as_dict_list(val: Any) -> list[dict[str, Any]]:
    return [item for item in _as_list(val) if isinstance(item, dict)]


def _as_dict(val: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    return dict(default) if default is not None else {}


def _collect_truncation_warnings(
    data: dict[str, Any],
    *,
    count: int | None = None,
    existing: list[str] | None = None,
) -> list[str]:
    warnings = [str(w) for w in (existing or []) if w]
    meta = _as_dict(data.get("metadata"))
    trunc = bool(data.get("truncated")) or bool(meta.get("truncated"))
    if (
        data.get("done") is False
        or meta.get("done") is False
        or bool(data.get("next_page_token") or data.get("nextPageToken"))
        or bool(meta.get("next_page_token") or meta.get("nextPageToken"))
    ):
        trunc = True
    total_avail = data.get("total_available")
    if total_avail is None:
        total_avail = data.get("totalSize")
    if total_avail is None:
        total_avail = meta.get("total_available")
    if total_avail is None:
        total_avail = meta.get("totalSize")
    avail_int = _to_opt_int(total_avail)
    if avail_int is not None and count is not None and avail_int > count:
        trunc = True
    if trunc and not warnings:
        if avail_int is not None and count is not None:
            warnings.append(
                f"TRUNCATION_WARNING: Returned {count} of {avail_int} available records; totals and counts represent a partial dataset only."
            )
        else:
            warnings.append(
                "TRUNCATION_WARNING: Upstream feed reported truncated or paginated output; totals and counts represent a partial dataset only."
            )
    return warnings


def _load_enterprise_io() -> Any | None:
    try:
        from scripts import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    try:
        import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    eio_path = Path(__file__).resolve().parent / "enterprise_io.py"
    if eio_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("enterprise_io", eio_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


_ENTERPRISE_IO = _load_enterprise_io()


def _to_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"true", "yes", "y", "1", "on"}:
        return True
    if s in {"false", "no", "n", "0", "off", ""}:
        return False if s else default
    return bool(s)


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            _loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(_loaded, dict):
                cfg.update(_loaded)
    org_cfg = _to_bool(cfg.get("org_configured"), False)
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(
    input_arg: str | Path | dict[str, Any] | list[dict[str, Any]],
    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"bom_edges": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="bom-cost-rollup-variance", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"bom_edges": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"bom_edges": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    ppv_alert_pct = _to_float(cfg.get("ppv_alert_threshold_pct"), 5.0)

    items_map = {str(i["sku"]): i for i in _as_list(data.get("items")) if "sku" in i}
    edges = _as_list(data.get("bom_edges"))
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        psku = str(e.get("parent_sku") or "").strip()
        if psku:
            children_by_parent.setdefault(psku, []).append(e)

    target_skus = [str(s) for s in _as_list(data.get("target_assemblies"))]
    if not target_skus:
        all_children = {str(e.get("component_sku") or e.get("child_sku") or "") for e in edges}
        target_skus = sorted(p for p in children_by_parent if p not in all_children)

    cycles: list[list[str]] = []

    def _explode(sku: str, mult: float, stack: list[str], acc: dict[str, float]) -> None:
        if sku in stack:
            cycles.append(stack + [sku])
            return
        kids = _as_list(children_by_parent.get(sku))
        if not kids:
            acc[sku] = acc.get(sku, 0.0) + mult
            return
        for edge in kids:
            comp = str(edge.get("component_sku") or edge.get("child_sku") or "")
            q = _to_float(edge.get("qty_per_parent"), 1.0)
            scrap_pct = _to_float(edge.get("scrap_factor_pct"), 0.0) / 100.0
            eff_mult = mult * q * (1.0 + scrap_pct)
            _explode(comp, eff_mult, stack + [sku], acc)

    assembly_rollups: list[dict[str, Any]] = []
    component_variances_global: dict[str, dict[str, Any]] = {}

    for top_sku in target_skus:
        demand_qty = _to_float(items_map.get(top_sku) or {}.get("production_volume"), 1.0)
        leaf_qtys: dict[str, float] = {}
        _explode(top_sku, 1.0, [], leaf_qtys)

        std_unit_cost = 0.0
        act_unit_cost = 0.0
        for comp_sku, qty_per_fg in sorted(leaf_qtys.items()):
            cinfo = _as_dict(items_map.get(comp_sku))
            std_c = _to_float(cinfo.get("standard_unit_cost_usd"), 0.0)
            act_c = _to_float(cinfo.get("actual_unit_cost_usd"), std_c)
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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(drivers)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explode multi-level BOMs and calculate standard vs actual PPV.")
    parser.add_argument("--input", required=True, type=Path, help="Path to BOM and item cost JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, sheet=args.sheet)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
