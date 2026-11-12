#!/usr/bin/env python3
"""Validates multi-year SaaS quotes, effective discounts, gross margin floors, and approval tiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "auto_approve_max_discount_pct": 15.0,
    "vp_approve_max_discount_pct": 25.0,
    "deal_desk_max_discount_pct": 35.0,
    "min_gross_margin_floor_pct": 60.0,
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
                skill_id="deal-desk-quote-guard",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"quotes": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="deal-desk-quote-guard", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"quotes": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"quotes": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _evaluate_quote(q: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    qid = str(q.get("quote_id") or "Q-1")
    customer = str(q.get("customer_name") or "Unknown Account")
    term_months = max(1, _to_int(q.get("term_months"), 12))
    term_years = term_months / 12.0
    payment_days = _to_int(q.get("payment_terms_days"), 30)
    billing_freq = str(q.get("billing_frequency", "annual")).lower()
    sla_credit_cap_pct = _to_float(q.get("sla_credit_cap_pct"), 10.0)
    has_tfc = _to_bool(q.get("termination_for_convenience"), False)

    ramp_years = _as_list(q.get("ramp_years"))
    list_tcv = 0.0
    net_tcv = 0.0
    total_cogs = 0.0
    year1_acv = 0.0

    if ramp_years:
        for idx, yr in enumerate(ramp_years):
            y_list = _to_float(yr.get("list_price_usd"), 0.0)
            y_net = _to_float(yr.get("net_price_usd"), 0.0)
            y_cogs = _to_float(yr.get("cogs_usd"), 0.0)
            list_tcv += y_list
            net_tcv += y_net
            total_cogs += y_cogs
            if idx == 0:
                year1_acv = y_net
    else:
        for item in _as_list(q.get("line_items")):
            qty = _to_float(item.get("quantity"), 1)
            unit_list = _to_float(item.get("unit_list_price_annual"), 0.0)
            unit_net = _to_float(item.get("unit_net_price_annual"), unit_list)
            unit_cogs = _to_float(item.get("unit_cogs_annual"), 0.0)
            list_tcv += qty * unit_list * term_years
            net_tcv += qty * unit_net * term_years
            total_cogs += qty * unit_cogs * term_years
        year1_acv = net_tcv / term_years

    blended_acv = net_tcv / term_years
    net_discount_pct = ((list_tcv - net_tcv) / list_tcv * 100.0) if list_tcv > 0 else 0.0
    gross_margin_pct = ((net_tcv - total_cogs) / net_tcv * 100.0) if net_tcv > 0 else 0.0

    non_standard_flags: list[str] = []
    if payment_days > 60:
        non_standard_flags.append(f"Extended payment terms: Net {payment_days} (> Net 60)")
    elif payment_days > 45:
        non_standard_flags.append(f"Elevated payment terms: Net {payment_days}")
    if billing_freq not in {"annual", "upfront"}:
        non_standard_flags.append(f"Non-annual billing cadence: {billing_freq}")
    if has_tfc:
        non_standard_flags.append("Termination for convenience clause present")
    if sla_credit_cap_pct > 10.0:
        non_standard_flags.append(f"Elevated SLA service credit cap: {sla_credit_cap_pct}%")
    if ramp_years and year1_acv < blended_acv * 0.65:
        non_standard_flags.append(f"Back-end loaded ramp (Year-1 ACV ${year1_acv:,.0f} vs Blended ${blended_acv:,.0f})")

    tier0_max = _to_float(cfg.get("auto_approve_max_discount_pct"), 15.0)
    tier1_max = _to_float(cfg.get("vp_approve_max_discount_pct"), 25.0)
    tier2_max = _to_float(cfg.get("deal_desk_max_discount_pct"), 35.0)
    margin_floor = _to_float(cfg.get("min_gross_margin_floor_pct"), 60.0)

    margin_breach = gross_margin_pct < margin_floor
    if net_discount_pct > tier2_max or margin_breach or payment_days > 60 or has_tfc or sla_credit_cap_pct > 10.0:
        tier = "Tier 3: CFO / Executive Desk"
    elif net_discount_pct > tier1_max or payment_days > 45 or billing_freq != "annual" or (ramp_years and len(ramp_years) > 1):
        tier = "Tier 2: Deal Desk & Finance"
    elif net_discount_pct > tier0_max or payment_days > 30:
        tier = "Tier 1: Regional Sales VP"
    else:
        tier = "Tier 0: Auto-Approved"

    return {
        "quote_id": qid,
        "customer_name": customer,
        "term_months": term_months,
        "list_tcv_usd": round(list_tcv, 2),
        "net_tcv_usd": round(net_tcv, 2),
        "year1_acv_usd": round(year1_acv, 2),
        "blended_acv_usd": round(blended_acv, 2),
        "total_cogs_usd": round(total_cogs, 2),
        "net_effective_discount_pct": round(net_discount_pct, 2),
        "blended_gross_margin_pct": round(gross_margin_pct, 2),
        "margin_floor_breached": margin_breach,
        "non_standard_flags": non_standard_flags,
        "approval_tier": tier,
    }


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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="deal-desk-quote-guard")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "deal-desk-quote-guard",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    quotes = data.get("quotes") or ([data["quote"]] if "quote" in data else [data] if "quote_id" in data else [])
    evaluated = [_evaluate_quote(q, cfg) for q in quotes]
    tier3_count = sum(1 for e in evaluated if e["approval_tier"].startswith("Tier 3"))
    margin_breaches = sum(1 for e in evaluated if e["margin_floor_breached"])

    return {
        "skill": "deal-desk-quote-guard",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "quote_count": len(evaluated),
            "tier3_escalation_count": tier3_count,
            "margin_floor_breach_count": margin_breaches,
            "total_net_tcv_usd": round(sum(e["net_tcv_usd"] for e in evaluated), 2),
        },
        "evaluated_quotes": evaluated,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated)),
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
            "# Deal Desk Quote & Margin Guard",
            "",
            f"- **Quotes Evaluated:** {s['quote_count']} | **Total Net TCV:** ${s['total_net_tcv_usd']:,.2f}",
            f"- **Tier-3 Escalations:** {s['tier3_escalation_count']} | **Margin Floor Breaches:** {s['margin_floor_breach_count']}",
            "",
            "| Quote | Customer | Net TCV | Y1 ACV | Blended ACV | Discount % | Gross Margin % | Approval Tier |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for e in result["evaluated_quotes"]:
        lines.append(
            f"| `{e['quote_id']}` | {e['customer_name']} | ${e['net_tcv_usd']:,.2f} | ${e['year1_acv_usd']:,.2f} | "
            f"${e['blended_acv_usd']:,.2f} | {e['net_effective_discount_pct']:.1f}% | "
            f"{e['blended_gross_margin_pct']:.1f}% | {e['approval_tier']} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SaaS deal discounts, ramps, and gross margin floors.")
    parser.add_argument("--input", required=True, type=Path, help="Path to quote JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="deal-desk-quote-guard",
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
