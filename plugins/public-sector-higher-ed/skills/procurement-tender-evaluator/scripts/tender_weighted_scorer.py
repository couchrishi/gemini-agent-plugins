#!/usr/bin/env python3
"""Scores public procurement vendor tenders with mandatory compliance gates and normalized commercial weighting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "technical_weight_pct": 50.0,
    "sustainability_weight_pct": 15.0,
    "commercial_weight_pct": 35.0,
    "min_technical_pass_score": 70.0,
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

    bids = data.get("bids") or data.get("proposals") or []
    w_tech = _to_float(cfg.get("technical_weight_pct"), 50.0)
    w_sust = _to_float(cfg.get("sustainability_weight_pct"), 15.0)
    w_comm = _to_float(cfg.get("commercial_weight_pct"), 35.0)
    min_tech = _to_float(cfg.get("min_technical_pass_score"), 70.0)

    # Pass 1: Determine mandatory compliance gates BEFORE finding lowest compliant bid price
    pre_screened: list[dict[str, Any]] = []
    compliant_prices: list[float] = []

    for b in bids:
        bid_id = str(b.get("bid_id") or "BID-1")
        vendor = str(b.get("vendor_name") or bid_id)
        price = _to_float(b.get("total_bid_price_usd"), 0.0)
        tech_score = _to_float(b.get("technical_score_100"), 0.0)
        sust_score = _to_float(b.get("sustainability_score_100"), 0.0)

        disq_reasons: list[str] = []
        if b.get("debarred_or_sanctioned", False):
            disq_reasons.append("VENDOR_DEBARRED_OR_SANCTIONED")
        if not b.get("coi_declaration_signed", False):
            disq_reasons.append("MISSING_COI_ATTESTATION")
        if not b.get("tax_clearance_valid", False):
            disq_reasons.append("EXPIRED_TAX_CLEARANCE")
        if not b.get("bid_bond_submitted", True):
            disq_reasons.append("MISSING_BID_BOND")
        if tech_score < min_tech:
            disq_reasons.append(f"TECHNICAL_BELOW_MIN ({tech_score:.1f} < {min_tech:.1f})")
        if price <= 0:
            disq_reasons.append("INVALID_NON_POSITIVE_PRICE")

        compliant = len(disq_reasons) == 0
        if compliant:
            compliant_prices.append(price)

        pre_screened.append(
            {
                "bid_id": bid_id,
                "vendor_name": vendor,
                "total_bid_price_usd": round(price, 2),
                "technical_score_100": round(tech_score, 2),
                "sustainability_score_100": round(sust_score, 2),
                "compliant": compliant,
                "disqualification_reasons": disq_reasons,
            }
        )

    lowest_price = min(compliant_prices) if compliant_prices else None
    scored: list[dict[str, Any]] = []

    for item in pre_screened:
        if item["compliant"] and lowest_price:
            comm_raw_100 = (lowest_price / item["total_bid_price_usd"]) * 100.0
            weighted_total = (
                item["technical_score_100"] * (w_tech / 100.0)
                + item["sustainability_score_100"] * (w_sust / 100.0)
                + comm_raw_100 * (w_comm / 100.0)
            )
            status = "COMPLIANT_RANKED"
        else:
            comm_raw_100 = 0.0
            weighted_total = 0.0
            status = "DISQUALIFIED_NON_COMPLIANT"

        scored.append(
            {
                **item,
                "commercial_score_100": round(comm_raw_100, 2),
                "weighted_total_score": round(weighted_total, 2),
                "evaluation_status": status,
                "rank": None,
            }
        )

    compliant_sorted = sorted(
        [x for x in scored if x["compliant"]],
        key=lambda x: (-x["weighted_total_score"], x["total_bid_price_usd"]),
    )
    for idx, x in enumerate(compliant_sorted, 1):
        x["rank"] = idx

    final_list = compliant_sorted + [x for x in scored if not x["compliant"]]
    winner = compliant_sorted[0] if compliant_sorted else None

    return {
        "skill": "procurement-tender-evaluator",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "tender_id": str(data.get("tender_id") or "RFP-001"),
            "bids_received": len(final_list),
            "compliant_bids": len(compliant_sorted),
            "disqualified_bids": len(final_list) - len(compliant_sorted),
            "lowest_compliant_price_usd": lowest_price,
            "recommended_top_vendor": winner["vendor_name"] if winner else None,
            "recommended_top_score": winner["weighted_total_score"] if winner else None,
        },
        "bid_rankings": final_list,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(bids), existing=["Sealed bid repository truncated; procurement award blocked until all envelopes parsed."] if data.get("truncated") else []),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Public Procurement Tender Evaluation Scorecard (`{s['tender_id']}`)",
            "",
            f"- **Bids Received:** {s['bids_received']} | **Compliant:** {s['compliant_bids']} | "
            f"**Disqualified:** {s['disqualified_bids']} | **Top Ranked:** {s['recommended_top_vendor'] or 'NONE'} "
            f"({s['recommended_top_score'] or 0:.2f})",
            "",
            "| Rank | Vendor | Bid Price | Tech | Sust | Comm | Weighted Score | Status | Notes |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |",
        ]
    )
    for b in result["bid_rankings"]:
        rk = str(b["rank"]) if b["rank"] else "-"
        lines.append(
            f"| {rk} | {b['vendor_name']} (`{b['bid_id']}`) | ${b['total_bid_price_usd']:,.2f} | "
            f"{b['technical_score_100']:.1f} | {b['sustainability_score_100']:.1f} | {b['commercial_score_100']:.1f} | "
            f"**{b['weighted_total_score']:.2f}** | `{b['evaluation_status']}` | "
            f"{', '.join(b['disqualification_reasons']) or 'All gates passed'} |"
        )
    lines.extend(["", "Award recommendation requires formal Procurement Evaluation Board HITL sign-off."])
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate sealed public tenders with compliance gates and weighted scoring.")
    parser.add_argument("--input", required=True, type=Path, help="Path to tender bids JSON")
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
