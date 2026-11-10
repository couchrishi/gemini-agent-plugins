#!/usr/bin/env python3
"""Audits CRM pipeline snapshots for stage age, push counts, MEDDPICC gaps, and multi-currency FX."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "target_currency": "USD",
    "stage_stale_multiplier": 1.5,
    "max_push_count_before_flag": 2,
    "min_commit_contacts": 2,
    "target_pipeline_coverage_x": 3.0,
}

DEFAULT_STAGE_MEDIAN_DAYS = {
    "qualification": 18,
    "discovery": 21,
    "technical_validation": 28,
    "negotiation": 14,
    "commit": 10,
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


def load_payload(input_arg: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"opportunities": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"opportunities": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, (dict, list)):
        return {}
    if isinstance(data, list):
        return {"opportunities": data}
    return data


def _as_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"true", "1", "yes", "y"}


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)
    opps = data.get("opportunities") or data.get("records") or []
    fx_rates = {str(k).upper(): (_to_opt_float(v) if _to_opt_float(v) is not None else 1.0) for k, v in _as_dict(data.get("fx_rates"), {"USD": 1.0}).items()}
    stage_medians = {
        str(k).lower(): _to_float(v)
        for k, v in data.get("stage_median_days", DEFAULT_STAGE_MEDIAN_DAYS).items()
    }
    remaining_quota = _to_float(data.get("remaining_quota_usd"), 0.0)
    target_ccy = str(cfg.get("target_currency", "USD")).upper()
    stale_mult = _to_float(cfg.get("stage_stale_multiplier"), 1.5)
    max_push = _to_int(cfg.get("max_push_count_before_flag"), 2)
    min_contacts = _to_int(cfg.get("min_commit_contacts"), 2)
    target_cov = _to_float(cfg.get("target_pipeline_coverage_x"), 3.0)

    metadata = _as_dict(data.get("metadata"))
    total_available = _to_int(metadata.get("totalSize"), metadata.get("total_available", len(opps)))
    truncated = bool(metadata.get("truncated", total_available > len(opps) or metadata.get("done") is False))
    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"TRUNCATION_WARNING: SOQL batch returned {len(opps)} of {total_available} opportunities."
        )

    currencies_seen = {str(o.get("currency", target_ccy)).upper() for o in opps}
    missing_fx = sorted(c for c in currencies_seen if c != target_ccy and c not in fx_rates)
    if missing_fx:
        warnings.append(
            f"FX_CONVERSION_GAP: Missing FX rates for currencies {missing_fx}; unconverted deals excluded from normalized totals."
        )

    open_total_norm = 0.0
    weighted_total_norm = 0.0
    flagged_opps: list[dict[str, Any]] = []
    commit_at_risk_norm = 0.0
    closed_excluded = 0

    for idx, o in enumerate(opps):
        oid = str(o.get("opportunity_id") or f"OPP-{idx + 1}")
        name = str(o.get("name") or oid)
        stage = str(o.get("stage") or "").strip()
        forecast_cat = str(o.get("forecast_category") or "Pipeline").strip()
        is_closed = _as_bool(o.get("is_closed", False))
        prob = _to_float(o.get("probability_pct"), 0.0)
        ccy = str(o.get("currency") or target_ccy).upper()
        raw_amt = _to_float(o.get("amount"), 0.0)

        flags: list[str] = []
        if ("closed" in stage.lower() and not is_closed) or (is_closed and prob not in {0.0, 100.0}):
            flags.append(f"STAGE_CONTRADICTION ({stage}, is_closed={is_closed}, prob={prob}%)")

        if is_closed:
            closed_excluded += 1
            continue

        if ccy == target_ccy:
            norm_amt = raw_amt
            fx_ok = True
        elif ccy in fx_rates:
            norm_amt = raw_amt * fx_rates[ccy]
            fx_ok = True
        else:
            norm_amt = 0.0
            fx_ok = False
            flags.append(f"MISSING_FX_RATE:{ccy}")

        if fx_ok:
            open_total_norm += norm_amt
            weighted_total_norm += norm_amt * (prob / 100.0)

        days_in_stage = _to_float(o.get("days_in_stage"), 0.0)
        median = stage_medians.get(stage.lower().replace(" ", "_"), 21.0)
        if days_in_stage > median * stale_mult:
            flags.append(f"STALE_STAGE ({days_in_stage:.0f}d > {median * stale_mult:.1f}d)")

        pushes = _to_int(o.get("push_count"), 0)
        if pushes >= max_push:
            flags.append(f"CHRONIC_SLIPPAGE (pushed {pushes}x)")

        contacts = _to_int(o.get("active_contact_count"), 0)
        if contacts < min_contacts and forecast_cat.lower() in {"commit", "bestcase", "best case"}:
            flags.append(f"SINGLE_THREADED ({contacts} contacts < {min_contacts})")

        if forecast_cat.lower() == "commit":
            if not str(o.get("economic_buyer") or "").strip():
                flags.append("MISSING_ECONOMIC_BUYER")
            if not str(o.get("next_step") or "").strip():
                flags.append("MISSING_NEXT_STEP")
            if _to_int(o.get("days_since_activity"), 0) > 14:
                flags.append(f"COMMIT_INACTIVE ({o.get('days_since_activity')}d)")
            if flags and fx_ok:
                commit_at_risk_norm += norm_amt

        if flags:
            flagged_opps.append(
                {
                    "opportunity_id": oid,
                    "name": name,
                    "account_name": o.get("account_name"),
                    "stage": stage,
                    "forecast_category": forecast_cat,
                    "currency": ccy,
                    "raw_amount": raw_amt,
                    "normalized_amount": round(norm_amt, 2) if fx_ok else None,
                    "risk_flags": flags,
                }
            )

    coverage_x = round(open_total_norm / remaining_quota, 2) if remaining_quota > 0 else None
    coverage_healthy = (coverage_x >= target_cov) if coverage_x is not None else None

    return {
        "skill": "pipeline-hygiene-slippage",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "target_currency": target_ccy,
            "total_records_fetched": len(opps),
            "open_pipeline_count": len(opps) - closed_excluded,
            "closed_excluded_count": closed_excluded,
            "open_pipeline_normalized": round(open_total_norm, 2),
            "weighted_pipeline_normalized": round(weighted_total_norm, 2),
            "commit_at_risk_normalized": round(commit_at_risk_norm, 2),
            "flagged_opportunity_count": len(flagged_opps),
            "pipeline_coverage_x": coverage_x,
            "coverage_target_met": coverage_healthy,
            "fx_normalized": len(missing_fx) == 0,
        },
        "flagged_opportunities": flagged_opps,
        "truncation_warnings": _collect_truncation_warnings(data, count=None, existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# CRM Pipeline Hygiene & Slippage Audit ({s['target_currency']})",
            "",
            f"- **Open Pipeline:** {s['open_pipeline_normalized']:,.2f} {s['target_currency']} (Weighted: {s['weighted_pipeline_normalized']:,.2f})",
            f"- **Commit at Risk:** {s['commit_at_risk_normalized']:,.2f} {s['target_currency']} | **Coverage Ratio:** {s['pipeline_coverage_x']}x",
            f"- **Flagged Opportunities:** {s['flagged_opportunity_count']}",
            "",
            "| Opportunity | Account | Forecast | Norm Amount | Risk Flags |",
            "| :--- | :--- | :--- | ---: | :--- |",
        ]
    )
    for f in result["flagged_opportunities"]:
        amt_str = f"{f['normalized_amount']:,.2f}" if f["normalized_amount"] is not None else "MISSING_FX"
        lines.append(
            f"| `{f['opportunity_id']}` {f['name']} | {f['account_name']} | {f['forecast_category']} | "
            f"{amt_str} | {'; '.join(f['risk_flags'])} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit CRM pipeline slippage and multi-currency FX.")
    parser.add_argument("--input", required=True, type=Path, help="Path to opportunities JSON or CSV")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
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
