#!/usr/bin/env python3
"""Classifies B2B telco provisioning order fallout, SLA breach aging, and Monthly Recurring Charge (MRC) at risk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "provisioning_sla_days": 15,
    "high_value_mrc_usd": 2500.0,
}

BUCKET_RULES: list[tuple[str, tuple[str, ...], str]] = [
    ("CREDIT_RISK_HOLD", ("credit", "deposit", "billing hold", "risk hold"), "Credit & Collections Desk"),
    ("ADDRESS_LOC_VALIDATION_FAIL", ("address", "geocode", "suite", "demarc", "site survey"), "Carrier Access Engineering"),
    ("NUMBER_PORT_LNP_FREEZE", ("lnp", "port", "foc rejected", "losing carrier", "csr mismatch"), "LNP Porting Operations"),
    ("FIBER_FACILITY_CAPACITY_SHORTAGE", ("no fiber", "splitter full", "olt port", "civil permit", "buildout"), "OSP Construction Planning"),
    ("CPE_BACKORDER", ("cpe", "router stock", "backorder", "serial unassigned"), "Hardware Fulfillment"),
]


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

    orders = data.get("fallout_orders") or data.get("orders") or []
    sla_days = _to_int(cfg.get("provisioning_sla_days"), 15)
    high_mrc = _to_float(cfg.get("high_value_mrc_usd"), 2500.0)

    classified: list[dict[str, Any]] = []
    bucket_totals: dict[str, dict[str, Any]] = {}

    for o in orders:
        oid = str(o.get("order_id") or "B2B-1")
        cust = str(o.get("customer_name") or "Enterprise Account")
        product = str(o.get("product_type") or "DIA_FIBER")
        mrc = _to_float(o.get("mrc_usd"), 0.0)
        age = _to_int(o.get("age_days"), 0)
        err_text = f"{o.get('fallout_code') or ''} {o.get('error_message') or ''}".lower()

        bucket = "UNCLASSIFIED_PROV_EXCEPTION"
        owner = "Order Fallout Triage Desk"
        for bname, keywords, downer in BUCKET_RULES:
            if any(k in err_text for k in keywords):
                bucket = bname
                owner = downer
                break

        sla_breached = age > sla_days
        priority = "P1_EXEC_ESCALATE" if (mrc >= high_mrc and sla_breached) else ("P2_URGENT" if sla_breached else "P3_STANDARD")

        b = bucket_totals.setdefault(bucket, {"bucket": bucket, "order_count": 0, "mrc_at_risk_usd": 0.0, "owner_queue": owner})
        b["order_count"] += 1
        b["mrc_at_risk_usd"] = round(b["mrc_at_risk_usd"] + mrc, 2)

        classified.append(
            {
                "order_id": oid,
                "customer_name": cust,
                "product_type": product,
                "mrc_usd": round(mrc, 2),
                "age_days": age,
                "sla_breached": sla_breached,
                "fallout_bucket": bucket,
                "assigned_queue": owner,
                "priority": priority,
            }
        )

    classified.sort(key=lambda x: (-int(x["sla_breached"]), -x["mrc_usd"], -x["age_days"]))
    buckets_list = sorted(bucket_totals.values(), key=lambda x: -x["mrc_at_risk_usd"])
    total_mrc = round(sum(c["mrc_usd"] for c in classified), 2)

    return {
        "skill": "b2b-order-fallout-resolver",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "orders_in_fallout": len(classified),
            "sla_breached_count": sum(1 for c in classified if c["sla_breached"]),
            "total_mrc_at_risk_usd": total_mrc,
            "annualized_arr_blocked_usd": round(total_mrc * 12.0, 2),
        },
        "bucket_rollup": buckets_list,
        "fallout_orders": classified,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(classified), existing=["CRM/OSS fallout backlog truncated; MRC-at-risk figure reflects partial queue."] if data.get("truncated") else []),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# B2B Telco Provisioning Fallout & MRC-at-Risk Triage",
            "",
            f"- **Orders in Fallout:** {s['orders_in_fallout']} | **SLA Breached:** {s['sla_breached_count']} | "
            f"**MRC at Risk:** ${s['total_mrc_at_risk_usd']:,.2f}/mo (${s['annualized_arr_blocked_usd']:,.2f} ARR)",
            "",
            "| Order | Customer | Product | MRC | Age (d) | Bucket | Assigned Queue | Priority |",
            "| :--- | :--- | :--- | ---: | ---: | :--- | :--- | :--- |",
        ]
    )
    for o in result["fallout_orders"]:
        lines.append(
            f"| `{o['order_id']}` | {o['customer_name']} | {o['product_type']} | ${o['mrc_usd']:,.2f} | "
            f"{o['age_days']} | `{o['fallout_bucket']}` | {o['assigned_queue']} | `{o['priority']}` |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify B2B telecom order fallout and calculate MRC at risk.")
    parser.add_argument("--input", required=True, type=Path, help="Path to B2B fallout queue JSON")
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
