#!/usr/bin/env python3
"""Computes executed contract renewal opt-out deadlines, CPI escalator breaches, and obligation calendars."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "max_renewal_notice_days": 60,
    "max_price_escalator_pct": 5.0,
    "max_breach_notify_hours": 72,
}


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
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        return {"contracts": rows}
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return date.fromisoformat(s[:10])


def _evaluate_contract(c: dict[str, Any], as_of: date, cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cid = str(c.get("contract_id") or "C-1")
    counterparty = str(c.get("counterparty") or "Unknown Vendor")
    annual_usd = float(c.get("annual_value_usd") or 0.0)
    auto_renew = str(c.get("auto_renewal", True)).lower() not in {"false", "0", "no"}
    notice_raw = c.get("notice_days")
    renewal_dt = _parse_date(c.get("renewal_date"))
    cpi_raw = c.get("cpi_escalator_pct")
    uncapped_cpi = bool(c.get("uncapped_cpi", False))
    breach_raw = c.get("breach_notify_hours")

    max_notice = int(cfg.get("max_renewal_notice_days", 60))
    max_cpi = float(cfg.get("max_price_escalator_pct", 5.0))
    max_breach_hrs = int(cfg.get("max_breach_notify_hours", 72))

    findings: list[str] = []
    calendar_events: list[dict[str, Any]] = []

    if auto_renew and (renewal_dt is None or notice_raw is None or str(notice_raw).strip() == ""):
        verification_status = "UNVERIFIED_MISSING_FIELDS"
        urgency = "UNVERIFIED"
        opt_out_str = None
        days_left = None
        findings.append("Auto-renewal clause lacks renewal_date or notice_days (never assume zero).")
    elif not auto_renew or renewal_dt is None:
        verification_status = "VERIFIED_OPT_IN"
        urgency = "NONE"
        opt_out_str = None
        days_left = None
    else:
        notice_days = int(notice_raw)
        verification_status = "VERIFIED"
        opt_out_dt = renewal_dt - timedelta(days=notice_days)
        opt_out_str = opt_out_dt.isoformat()
        days_left = (opt_out_dt - as_of).days
        if days_left < 0:
            urgency = "EXPIRED_WINDOW"
            findings.append(f"Opt-out deadline {opt_out_str} passed {abs(days_left)} days ago.")
        elif days_left <= 30:
            urgency = "CRITICAL_URGENT"
            findings.append(f"Opt-out deadline {opt_out_str} is in {days_left} days.")
        elif days_left <= 60:
            urgency = "ACTION_REQUIRED"
            findings.append(f"Opt-out window {opt_out_str} arrives in {days_left} days.")
        elif days_left <= 120:
            urgency = "MONITOR"
        else:
            urgency = "LONG_HORIZON"

        if notice_days > max_notice:
            findings.append(f"Notice period ({notice_days}d) exceeds playbook max ({max_notice}d).")

        calendar_events.append(
            {
                "contract_id": cid,
                "counterparty": counterparty,
                "event_type": "AUTO_RENEWAL_OPT_OUT_DEADLINE",
                "due_date": opt_out_str,
                "days_until_due": days_left,
                "urgency": urgency,
                "exposure_usd": round(annual_usd, 2),
            }
        )

    cpi_breach = False
    if uncapped_cpi:
        cpi_breach = True
        findings.append("Uncapped CPI / renewal uplift clause exposes annual fees.")
    elif cpi_raw is not None and str(cpi_raw).strip() != "":
        cpi_val = float(cpi_raw)
        if cpi_val > max_cpi:
            cpi_breach = True
            findings.append(f"Renewal escalator {cpi_val}% exceeds baseline {max_cpi}% cap.")

    dpa_breach = False
    if breach_raw is not None and str(breach_raw).strip() != "":
        if int(breach_raw) > max_breach_hrs:
            dpa_breach = True
            findings.append(f"Breach notify SLA {breach_raw}h exceeds {max_breach_hrs}h ceiling.")

    for ob in c.get("obligations", []):
        ob_due = _parse_date(ob.get("due_date"))
        calendar_events.append(
            {
                "contract_id": cid,
                "counterparty": counterparty,
                "event_type": str(ob.get("obligation_type") or "CONTRACT_OBLIGATION"),
                "due_date": ob_due.isoformat() if ob_due else None,
                "days_until_due": (ob_due - as_of).days if ob_due else None,
                "urgency": "UNVERIFIED" if ob_due is None else ("CRITICAL_URGENT" if (ob_due - as_of).days <= 30 else "MONITOR"),
                "exposure_usd": round(float(ob.get("penalty_or_credit_usd") or 0.0), 2),
            }
        )

    record = {
        "contract_id": cid,
        "counterparty": counterparty,
        "annual_value_usd": round(annual_usd, 2),
        "auto_renewal": auto_renew,
        "renewal_date": renewal_dt.isoformat() if renewal_dt else None,
        "notice_days": int(notice_raw) if notice_raw is not None and str(notice_raw).strip() != "" else None,
        "opt_out_deadline": opt_out_str,
        "days_until_opt_out": days_left,
        "urgency": urgency,
        "verification_status": verification_status,
        "cpi_escalator_breach": cpi_breach,
        "dpa_notify_breach": dpa_breach,
        "findings": findings,
    }
    return record, calendar_events


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)
    contracts = data.get("contracts", [])

    evaluated: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    for c in contracts:
        rec, evs = _evaluate_contract(c, as_of, cfg)
        evaluated.append(rec)
        all_events.extend(evs)

    all_events.sort(key=lambda e: (e["due_date"] is None, e["due_date"] or "9999-12-31", -e["exposure_usd"]))
    urgent = [e for e in evaluated if e["urgency"] in {"CRITICAL_URGENT", "ACTION_REQUIRED"}]
    expired = [e for e in evaluated if e["urgency"] == "EXPIRED_WINDOW"]
    unverified = [e for e in evaluated if e["verification_status"] == "UNVERIFIED_MISSING_FIELDS"]

    return {
        "skill": "executed-obligation-extractor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "contracts_audited": len(evaluated),
            "urgent_opt_out_count": len(urgent),
            "expired_opt_out_count": len(expired),
            "unverified_missing_count": len(unverified),
            "cpi_breach_count": sum(1 for e in evaluated if e["cpi_escalator_breach"]),
            "urgent_exposure_usd": round(sum(e["annual_value_usd"] for e in urgent + expired), 2),
        },
        "contracts": evaluated,
        "obligation_calendar": all_events,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Executed Contract Obligation & Renewal Calendar (As Of {result['as_of_date']})",
            "",
            f"- **Contracts Audited:** {s['contracts_audited']} | **Urgent/Action Windows:** {s['urgent_opt_out_count']} | "
            f"**Expired:** {s['expired_opt_out_count']} | **Unverified:** {s['unverified_missing_count']}",
            f"- **Urgent/Expired Annual Exposure:** ${s['urgent_exposure_usd']:,.2f} | **CPI Escalator Breaches:** {s['cpi_breach_count']}",
            "",
            "| Contract | Counterparty | Annual Value | Renewal Date | Notice Days | Opt-Out Deadline | Days Left | Urgency |",
            "| :--- | :--- | ---: | :--- | ---: | :--- | ---: | :--- |",
        ]
    )
    for c in result["contracts"]:
        lines.append(
            f"| `{c['contract_id']}` | {c['counterparty']} | ${c['annual_value_usd']:,.2f} | "
            f"{c['renewal_date'] or 'MISSING'} | {c['notice_days'] if c['notice_days'] is not None else 'MISSING'} | "
            f"{c['opt_out_deadline'] or 'UNVERIFIED'} | {c['days_until_opt_out'] if c['days_until_opt_out'] is not None else '—'} | `{c['urgency']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build executed contract renewal and obligation deadline calendar.")
    parser.add_argument("--input", required=True, type=Path, help="Path to executed contracts JSON or CSV")
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
