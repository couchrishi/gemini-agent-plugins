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

    cases = data.get("cases") or []
    base_fpl = float(cfg.get("base_fpl_single_usd", 15060.0))
    add_member = float(cfg.get("fpl_per_additional_member_usd", 5380.0))
    mult = float(cfg.get("eligibility_fpl_multiplier", 2.0))
    cure_days = int(cfg.get("statutory_cure_window_days", 15))
    req_docs = list(cfg.get("required_documents", DEFAULT_CONFIG["required_documents"]))

    evaluated: list[dict[str, Any]] = []
    pii_hits = 0

    for c in cases:
        cid = str(c.get("case_id") or "CASE-1")
        hh_size = max(1, int(c.get("household_size") or 1))
        annual_income = c.get("annual_household_income_usd")
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
        "truncation_warnings": ["Case management queue truncated; batch excludes remaining active applications."] if data.get("truncated") else [],
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
