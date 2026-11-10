#!/usr/bin/env python3
"""Evaluates statutory benefits/aid eligibility with missing-document cure holds and PII/TIN redaction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "base_fpl_single_usd": 15060.0,
    "fpl_per_additional_member_usd": 5380.0,
    "eligibility_fpl_multiplier": 2.0,
    "statutory_cure_window_days": 15,
    "required_documents": ["identity_doc", "proof_of_income", "residency_proof"],
}

SSN_TIN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


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

    cases = data.get("cases") or []
    base_fpl = _to_float(cfg.get("base_fpl_single_usd"), 15060.0)
    add_member = _to_float(cfg.get("fpl_per_additional_member_usd"), 5380.0)
    mult = _to_float(cfg.get("eligibility_fpl_multiplier"), 2.0)
    cure_days = _to_int(cfg.get("statutory_cure_window_days"), 15)
    req_docs = list(cfg.get("required_documents", DEFAULT_CONFIG["required_documents"]))

    evaluated: list[dict[str, Any]] = []
    pii_hits = 0

    for c in cases:
        cid = str(c.get("case_id") or "CASE-1")
        hh_size = max(1, (_to_int(c.get("household_size")) or 1))
        annual_income = _to_opt_float(c.get("annual_household_income_usd"))
        docs = set(c.get("submitted_documents") or [])
        residency_eligible = bool(c.get("residency_verified", True))
        raw_notes = str(c.get("applicant_notes") or "")
        pii_redacted_count = len(SSN_TIN_RE.findall(raw_notes))
        pii_hits += pii_redacted_count

        fpl_100 = base_fpl + (hh_size - 1) * add_member
        max_income = round(fpl_100 * mult, 2)
        missing_docs = [d for d in req_docs if d not in docs]

        # Statutory safeguard: never issue denial solely because income/doc telemetry is absent -> cure notice
        if missing_docs or annual_income is None:
            determination = "PENDING_VERIFICATION_CURE_NOTICE"
            rationale = f"Missing mandatory document(s) ({', '.join(missing_docs) or 'income figure'}); issue {cure_days}-day cure notice."
        elif not residency_eligible:
            determination = "RECOMMEND_DENIAL_RESIDENCY"
            rationale = "Applicant fails statutory jurisdiction residency requirement (HITL caseworker review required)."
        elif float(annual_income) <= max_income:
            determination = "ELIGIBLE_RECOMMEND_AWARD"
            pct_fpl = round(float(annual_income) / fpl_100 * 100.0, 1)
            rationale = f"Verified household income ${float(annual_income):,.0f} ({pct_fpl:.1f}% FPL) <= {mult*100:.0f}% threshold ${max_income:,.0f}."
        else:
            determination = "RECOMMEND_DENIAL_OVER_INCOME"
            rationale = f"Verified household income ${float(annual_income):,.0f} exceeds threshold ${max_income:,.0f} (HITL sign-off required)."

        evaluated.append(
            {
                "case_id": cid,
                "household_size": hh_size,
                "annual_income_usd": float(annual_income) if annual_income is not None else None,
                "max_income_threshold_usd": max_income,
                "missing_documents": missing_docs,
                "pii_ssns_redacted": pii_redacted_count,
                "determination": determination,
                "cure_deadline_days": cure_days if determination == "PENDING_VERIFICATION_CURE_NOTICE" else None,
                "rationale": rationale,
                "hitl_caseworker_signoff_required": True,
            }
        )

    return {
        "skill": "citizen-case-eligibility-triager",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "cases_triaged": len(evaluated),
            "eligible_count": sum(1 for e in evaluated if e["determination"] == "ELIGIBLE_RECOMMEND_AWARD"),
            "pending_cure_count": sum(1 for e in evaluated if e["determination"] == "PENDING_VERIFICATION_CURE_NOTICE"),
            "recommended_denials": sum(1 for e in evaluated if e["determination"].startswith("RECOMMEND_DENIAL")),
            "pii_tokens_redacted": pii_hits,
        },
        "case_determinations": evaluated,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated), existing=["Case management queue truncated; batch excludes remaining active applications."] if data.get("truncated") else []),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Statutory Case Eligibility & Document Completeness Triage",
            "",
            f"- **Cases:** {s['cases_triaged']} | **Eligible:** {s['eligible_count']} | "
            f"**Pending Cure Notice:** {s['pending_cure_count']} | **Recommended Denials (HITL):** {s['recommended_denials']} | "
            f"**PII Tokens Redacted:** {s['pii_tokens_redacted']}",
            "",
            "| Case | HH Size | Income | Max Threshold | Missing Docs | Determination | Rationale |",
            "| :--- | ---: | ---: | ---: | :--- | :--- | :--- |",
        ]
    )
    for c in result["case_determinations"]:
        inc = f"${c['annual_income_usd']:,.0f}" if c["annual_income_usd"] is not None else "Missing"
        lines.append(
            f"| `{c['case_id']}` | {c['household_size']} | {inc} | ${c['max_income_threshold_usd']:,.0f} | "
            f"{', '.join(c['missing_documents']) or 'None'} | `{c['determination']}` | {c['rationale']} |"
        )
    lines.extend(["", "Final award or adverse action notices require licensed caseworker HITL approval."])
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate statutory citizen benefits eligibility with cure safeguards.")
    parser.add_argument("--input", required=True, type=Path, help="Path to citizen case packet JSON")
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
