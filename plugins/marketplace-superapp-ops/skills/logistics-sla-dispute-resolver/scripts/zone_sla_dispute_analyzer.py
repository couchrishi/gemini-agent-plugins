#!/usr/bin/env python3
"""Resolves SuperApp zone delivery SLA disputes, attribution (merchant vs courier), and refund liability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "sla_grace_minutes": 5,
    "default_prep_sla_minutes": 15,
    "high_value_payout_hitl_usd": 50.0,
    "severe_lateness_full_refund_minutes": 30,
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
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    _loaded = json.loads(Path(input_arg).read_text(encoding="utf-8"))
    return _loaded if isinstance(_loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)

    disputes = data.get("disputes") or data.get("orders") or []
    grace = _to_int(cfg.get("sla_grace_minutes"), 5)
    default_prep_sla = _to_int(cfg.get("default_prep_sla_minutes"), 15)
    hitl_cap = _to_float(cfg.get("high_value_payout_hitl_usd"), 50.0)
    severe_late = _to_int(cfg.get("severe_lateness_full_refund_minutes"), 30)

    resolved: list[dict[str, Any]] = []
    for row in disputes:
        oid = str(row.get("order_id") or "ORD-1")
        zone = str(row.get("zone_id") or "ZONE-A")
        order_val = _to_float(row.get("order_value_usd"), 0.0)
        promised_mins = (_to_int(row.get("promised_total_minutes")) or 35)
        actual_mins = _to_int(row.get("actual_total_minutes"), 0)
        prep_sla = (_to_int(row.get("merchant_prep_sla_minutes")) or default_prep_sla)
        actual_prep = _to_int(row.get("actual_merchant_prep_minutes"), 0)
        transit_sla = max(5, promised_mins - prep_sla)
        actual_transit = (_to_int(row.get("actual_transit_minutes")) or max(0, actual_mins - actual_prep))
        weather_alert = bool(row.get("verified_weather_force_majeure", False))
        missing_telemetry = row.get("actual_total_minutes") is None

        lateness = max(0, actual_mins - promised_mins)
        if missing_telemetry:
            attribution = "MISSING_TELEMETRY_HOLD"
            refund_usd = 0.0
            merchant_share = 0.0
            platform_share = 0.0
        elif weather_alert:
            attribution = "WEATHER_FORCE_MAJEURE_WAIVED"
            refund_usd = round(min(order_val * 0.25, 10.0), 2) if lateness > grace else 0.0
            merchant_share = 0.0
            platform_share = refund_usd
        elif lateness <= grace:
            attribution = "INVALID_WITHIN_SLA"
            refund_usd = 0.0
            merchant_share = 0.0
            platform_share = 0.0
        else:
            prep_over = max(0, actual_prep - prep_sla)
            transit_over = max(0, actual_transit - transit_sla)
            refund_pct = 1.0 if lateness >= severe_late else 0.5
            refund_usd = round(order_val * refund_pct, 2)
            if prep_over > 0 and transit_over > 0:
                attribution = "SHARED_MERCHANT_COURIER_BREACH"
                total_over = prep_over + transit_over
                merchant_share = round(refund_usd * (prep_over / total_over), 2)
                platform_share = round(refund_usd - merchant_share, 2)
            elif prep_over > transit_over:
                attribution = "MERCHANT_PREP_BREACH"
                merchant_share = refund_usd
                platform_share = 0.0
            else:
                attribution = "COURIER_TRANSIT_BREACH"
                merchant_share = 0.0
                platform_share = refund_usd

        resolved.append(
            {
                "order_id": oid,
                "zone_id": zone,
                "promised_minutes": promised_mins,
                "actual_minutes": actual_mins if not missing_telemetry else None,
                "lateness_minutes": lateness,
                "attribution": attribution,
                "recommended_refund_usd": refund_usd,
                "merchant_liability_usd": merchant_share,
                "platform_courier_liability_usd": platform_share,
                "requires_hitl_approval": refund_usd >= hitl_cap or attribution == "MISSING_TELEMETRY_HOLD",
            }
        )

    total_refund = round(sum(r["recommended_refund_usd"] for r in resolved), 2)
    return {
        "skill": "logistics-sla-dispute-resolver",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "disputes_evaluated": len(resolved),
            "valid_sla_breaches": sum(
                1 for r in resolved if r["attribution"] in {"MERCHANT_PREP_BREACH", "COURIER_TRANSIT_BREACH", "SHARED_MERCHANT_COURIER_BREACH"}
            ),
            "weather_waived_count": sum(1 for r in resolved if r["attribution"] == "WEATHER_FORCE_MAJEURE_WAIVED"),
            "total_refund_liability_usd": total_refund,
            "total_merchant_recovery_usd": round(sum(r["merchant_liability_usd"] for r in resolved), 2),
        },
        "dispute_resolutions": resolved,
        "truncation_warnings": _collect_truncation_warnings(data, count=None, existing=["Dispute queue truncated; batch excludes remaining zone tickets."] if data.get("truncated") else []),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Logistics Zone SLA Dispute Resolution Matrix",
            "",
            f"- **Evaluated:** {s['disputes_evaluated']} | **Valid Breaches:** {s['valid_sla_breaches']} | "
            f"**Weather Waived:** {s['weather_waived_count']} | **Total Refund Liability:** ${s['total_refund_liability_usd']:,.2f}",
            "",
            "| Order | Zone | Late Mins | Attribution | Refund $ | Merchant Share | Platform Share | HITL Gate |",
            "| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :--- |",
        ]
    )
    for r in result["dispute_resolutions"]:
        lines.append(
            f"| `{r['order_id']}` | {r['zone_id']} | {r['lateness_minutes']} | `{r['attribution']}` | "
            f"${r['recommended_refund_usd']:,.2f} | ${r['merchant_liability_usd']:,.2f} | "
            f"${r['platform_courier_liability_usd']:,.2f} | {'HOLD_HITL' if r['requires_hitl_approval'] else 'AUTO_ELIGIBLE'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve zone delivery SLA disputes and refund liability split.")
    parser.add_argument("--input", required=True, type=Path, help="Path to SLA dispute telemetry JSON")
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
