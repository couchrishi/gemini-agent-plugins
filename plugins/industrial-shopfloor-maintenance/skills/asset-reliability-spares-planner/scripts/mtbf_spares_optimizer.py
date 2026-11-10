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
        return {"spare_parts": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="asset-reliability-spares-planner", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"spare_parts": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"spare_parts": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    z = _to_float(cfg.get("service_level_z"), 1.65)

    spares = _as_list(data.get("spare_parts"))
    plans: list[dict[str, Any]] = []

    for sp in spares:
        part_id = str(sp.get("part_id") or "PART-1")
        desc = str(sp.get("description") or part_id)
        criticality = str(sp.get("asset_criticality") or "STANDARD").upper()
        op_hours = (_to_float(sp.get("fleet_operating_hours")) or 8760.0)
        failures = _to_int(sp.get("observed_failures"), 0)
        qty_per_fail = (_to_float(sp.get("qty_per_failure")) or 1.0)
        lead_days = (_to_float(sp.get("lead_time_days")) or 14.0)
        on_hand = _to_float(sp.get("on_hand_qty"), 0.0)
        on_order = _to_float(sp.get("on_order_qty"), 0.0)
        unit_cost = _to_float(sp.get("unit_cost_usd"), 0.0)

        # Conservative lower-bound MTBF when failures==0 (right-censored runtime, never infinite)
        censored = failures == 0
        eff_failures = failures if failures > 0 else 0.5
        mtbf_hours = op_hours / eff_failures
        hourly_demand = (qty_per_fail / mtbf_hours) * _to_float(sp.get("installed_base_count"), 1)
        lead_demand = hourly_demand * (lead_days * 24.0)
        safety_stock = math.ceil(z * math.sqrt(max(lead_demand, 0.01)))
        rop = math.ceil(lead_demand + safety_stock)
        net_avail = on_hand + on_order
        shortfall = max(0, rop - _to_int(net_avail))

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
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute MTBF, safety stock, and spare part reorder points.")
    parser.add_argument("--input", required=True, type=Path, help="Path to asset reliability and spares JSON")
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
