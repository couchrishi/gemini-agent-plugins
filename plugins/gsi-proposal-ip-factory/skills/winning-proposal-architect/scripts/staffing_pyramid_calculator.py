#!/usr/bin/env python3
"""Models GSI staffing pyramids, onshore/offshore leverage ratios, blended bill rates, and gross margins."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_sow_gross_margin_pct": 30.0,
    "critical_margin_floor_pct": 20.0,
    "target_offshore_leverage_pct": 55.0,
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
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            return _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="winning-proposal-architect",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"phases": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="winning-proposal-architect", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"phases": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"phases": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="winning-proposal-architect")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "winning-proposal-architect",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    min_margin = _to_float(cfg.get("min_sow_gross_margin_pct"), 30.0)
    crit_margin = _to_float(cfg.get("critical_margin_floor_pct"), 20.0)
    target_offshore = _to_float(cfg.get("target_offshore_leverage_pct"), 55.0)

    total_hours = 0.0
    offshore_hours = 0.0
    total_revenue = 0.0
    total_cost = 0.0
    phase_summaries: list[dict[str, Any]] = []

    for ph in _as_list(data.get("phases")):
        pname = str(ph.get("phase_name") or "Delivery Phase")
        weeks = (_to_float(ph.get("duration_weeks")) or 1.0)
        p_hours = 0.0
        p_off_hours = 0.0
        p_rev = 0.0
        p_cost = 0.0

        for r in _as_list(ph.get("roles")):
            fte = (_to_float(r.get("fte_count")) or 1.0)
            hrs_wk = (_to_float(r.get("hours_per_week")) or 40.0)
            loc = str(r.get("delivery_location") or "onshore").lower().strip()
            bill = _to_float(r.get("bill_rate_hourly"), 0.0)
            cost = _to_float(r.get("cost_rate_hourly"), 0.0)

            role_hrs = weeks * fte * hrs_wk
            role_rev = role_hrs * bill
            role_cost = role_hrs * cost
            p_hours += role_hrs
            if loc in {"offshore", "nearshore"}:
                p_off_hours += role_hrs
            p_rev += role_rev
            p_cost += role_cost

        p_gm_pct = ((p_rev - p_cost) / p_rev * 100.0) if p_rev > 0 else 0.0
        phase_summaries.append(
            {
                "phase_name": pname,
                "duration_weeks": weeks,
                "total_hours": round(p_hours, 1),
                "offshore_leverage_pct": round((p_off_hours / p_hours * 100.0) if p_hours > 0 else 0.0, 1),
                "revenue_usd": round(p_rev, 2),
                "cost_usd": round(p_cost, 2),
                "gross_margin_pct": round(p_gm_pct, 2),
            }
        )
        total_hours += p_hours
        offshore_hours += p_off_hours
        total_revenue += p_rev
        total_cost += p_cost

    gm_usd = total_revenue - total_cost
    gm_pct = (gm_usd / total_revenue * 100.0) if total_revenue > 0 else 0.0
    offshore_pct = (offshore_hours / total_hours * 100.0) if total_hours > 0 else 0.0
    blended_rate = (total_revenue / total_hours) if total_hours > 0 else 0.0

    if gm_pct < crit_margin:
        margin_gate = "CRITICAL_BELOW_20_BLOCKED"
    elif gm_pct < min_margin:
        margin_gate = "FINANCE_DESK_EXCEPTION_REQUIRED"
    else:
        margin_gate = "WITHIN_MARGIN_TARGET"

    return {
        "skill": "winning-proposal-architect",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "total_effort_hours": round(total_hours, 1),
            "offshore_leverage_pct": round(offshore_pct, 2),
            "below_offshore_target": offshore_pct < target_offshore,
            "total_revenue_usd": round(total_revenue, 2),
            "total_cost_usd": round(total_cost, 2),
            "gross_profit_usd": round(gm_usd, 2),
            "blended_gross_margin_pct": round(gm_pct, 2),
            "blended_bill_rate_hourly": round(blended_rate, 2),
            "margin_gate": margin_gate,
        },
        "phase_breakdown": phase_summaries,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# GSI Delivery Staffing Pyramid & Commercial Margin Model",
            "",
            f"- **Total Revenue:** ${s['total_revenue_usd']:,.2f} | **Loaded Cost:** ${s['total_cost_usd']:,.2f} | "
            f"**Gross Margin:** {s['blended_gross_margin_pct']:.2f}% (`{s['margin_gate']}`)",
            f"- **Total Effort:** {s['total_effort_hours']:,.1f} hrs | **Blended Rate:** ${s['blended_bill_rate_hourly']:,.2f}/hr | "
            f"**Offshore Leverage:** {s['offshore_leverage_pct']:.1f}%",
            "",
            "| Phase | Weeks | Hours | Offshore % | Revenue | Cost | Margin % |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for p in result["phase_breakdown"]:
        lines.append(
            f"| {p['phase_name']} | {p['duration_weeks']:.1f} | {p['total_hours']:,.1f} | "
            f"{p['offshore_leverage_pct']:.1f}% | ${p['revenue_usd']:,.2f} | ${p['cost_usd']:,.2f} | "
            f"{p['gross_margin_pct']:.2f}% |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute GSI delivery staffing pyramid, leverage, and margin.")
    parser.add_argument("--input", required=True, type=Path, help="Path to proposal staffing JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="winning-proposal-architect",
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        out = json.dumps(diag, indent=2, default=str)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0
    result = analyze(args.input, config=args.config, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
