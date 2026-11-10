#!/usr/bin/env python3
"""Checks E2B ICSR 4 minimum safety criteria, computes statutory reporting clocks, and detects raw PHI."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "fatal_lt_susar_days": 7,
    "serious_unexpected_days": 15,
    "periodic_report_days": 90,
}

PHI_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "Email"),
    (re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"), "Phone"),
]


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


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return date.fromisoformat(s[:10]) if s else None


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)

    d_fatal = int(cfg.get("fatal_lt_susar_days", 7))
    d_serious = int(cfg.get("serious_unexpected_days", 15))
    d_periodic = int(cfg.get("periodic_report_days", 90))

    cases = data.get("cases", [])
    evaluations: list[dict[str, Any]] = []

    for c in cases:
        cid = str(c.get("case_id") or "ICSR-1")
        patient_ok = bool(str(c.get("patient_identifier") or "").strip())
        reporter_ok = bool(str(c.get("reporter_qualification") or "").strip())
        drug_ok = bool(str(c.get("suspect_drug") or "").strip())
        ae_ok = bool(str(c.get("adverse_event_term") or "").strip())

        missing_criteria: list[str] = []
        if not patient_ok:
            missing_criteria.append("Identifiable Patient")
        if not reporter_ok:
            missing_criteria.append("Identifiable Reporter")
        if not drug_ok:
            missing_criteria.append("Suspect Medicinal Product")
        if not ae_ok:
            missing_criteria.append("Adverse Event / MedDRA Term")

        narrative = str(c.get("narrative") or "")
        phi_hits = [label for pat, label in PHI_PATTERNS if pat.search(narrative)]

        aware_dt = _parse_date(c.get("awareness_date"))
        is_fatal_lt = bool(c.get("is_fatal_or_life_threatening", False))
        is_serious = bool(c.get("is_serious", False)) or is_fatal_lt
        expectedness = str(c.get("expectedness") or "expected").lower().strip()

        if is_fatal_lt and expectedness == "unexpected":
            sla_days = d_fatal
            sla_class = "7-Day Fatal/LT SUSAR"
        elif is_serious and expectedness == "unexpected":
            sla_days = d_serious
            sla_class = "15-Day Expedited SUSAR"
        else:
            sla_days = d_periodic
            sla_class = "90-Day Periodic PBRER"

        if aware_dt:
            due_dt = aware_dt + timedelta(days=sla_days)
            days_left = (due_dt - as_of).days
            due_str = due_dt.isoformat()
        else:
            due_str = None
            days_left = None

        valid_icsr = len(missing_criteria) == 0
        if phi_hits:
            intake_state = "PHI_REDACTION_REQUIRED"
        elif not valid_icsr:
            intake_state = "INCOMPLETE_FOLLOWUP_REQUIRED"
        elif days_left is not None and days_left < 0:
            intake_state = "REGULATORY_SLA_OVERDUE"
        elif days_left is not None and days_left <= 3:
            intake_state = "EXPEDITED_SIGN_OFF_URGENT"
        else:
            intake_state = "READY_FOR_PV_SIGN_OFF"

        evaluations.append(
            {
                "case_id": cid,
                "valid_4_ich_criteria": valid_icsr,
                "missing_ich_criteria": missing_criteria,
                "phi_detected": phi_hits,
                "reporting_class": sla_class,
                "awareness_date": aware_dt.isoformat() if aware_dt else None,
                "regulatory_due_date": due_str,
                "days_remaining": days_left,
                "intake_status": intake_state,
            }
        )

    return {
        "skill": "pharmacovigilance-safety-intake",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "cases_screened": len(evaluations),
            "valid_icsr_count": sum(1 for e in evaluations if e["valid_4_ich_criteria"]),
            "phi_redaction_alerts": sum(1 for e in evaluations if e["phi_detected"]),
            "urgent_or_overdue_count": sum(
                1 for e in evaluations if e["intake_status"] in {"REGULATORY_SLA_OVERDUE", "EXPEDITED_SIGN_OFF_URGENT"}
            ),
        },
        "icsr_evaluations": evaluations,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Pharmacovigilance E2B ICSR Completeness & SLA Watch (As Of {result['as_of_date']})",
            "",
            f"- **Cases Screened:** {s['cases_screened']} | **Valid 4-Criteria ICSRs:** {s['valid_icsr_count']} | "
            f"**PHI Redaction Alerts:** {s['phi_redaction_alerts']} | **Urgent/Overdue:** {s['urgent_or_overdue_count']}",
            "",
            "| Case ID | Valid 4-ICH | Reporting Class | Due Date | Days Left | PHI Alerts | Status |",
            "| :--- | :--- | :--- | :--- | ---: | :--- | :--- |",
        ]
    )
    for e in result["icsr_evaluations"]:
        lines.append(
            f"| `{e['case_id']}` | {'YES' if e['valid_4_ich_criteria'] else 'NO'} | {e['reporting_class']} | "
            f"{e['regulatory_due_date'] or 'MISSING'} | {e['days_remaining'] if e['days_remaining'] is not None else '—'} | "
            f"{', '.join(e['phi_detected']) or 'Clean'} | `{e['intake_status']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate E2B ICSR criteria, reporting SLAs, and PHI redaction.")
    parser.add_argument("--input", required=True, type=Path, help="Path to safety cases JSON")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--as-of", type=str, help="Reference ISO date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, as_of_date=args.as_of)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
