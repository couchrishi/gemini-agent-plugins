#!/usr/bin/env python3
"""Audits EHS Permit-to-Work (PTW) packages for LOTO isolation, gas test limits, and worker certification."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "o2_min_pct": 19.5,
    "o2_max_pct": 23.5,
    "max_lel_pct": 0.0,
    "max_gas_test_age_mins": 60,
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

    o2_min = float(cfg.get("o2_min_pct", 19.5))
    o2_max = float(cfg.get("o2_max_pct", 23.5))
    max_lel = float(cfg.get("max_lel_pct", 0.0))
    max_gas_age = int(cfg.get("max_gas_test_age_mins", 60))

    permits = data.get("permits", [])
    audits: list[dict[str, Any]] = []

    for p in permits:
        pid = str(p.get("permit_id") or "PTW-1")
        wtype = str(p.get("work_type") or "general").lower().strip()
        work_dt = _parse_date(p.get("work_date")) or as_of
        cert_exp = _parse_date(p.get("worker_cert_valid_until"))
        issuer_signed = bool(p.get("issuer_signed", False))
        loto = p.get("loto_isolated")

        stop_work_reasons: list[str] = []
        if not issuer_signed:
            stop_work_reasons.append("Area Authority / Issuer signature missing.")
        if cert_exp is None or cert_exp < work_dt:
            stop_work_reasons.append(f"Worker safety certification missing or expired ({cert_exp}).")

        if wtype in {"confined_space", "high_voltage"} and loto is not True:
            stop_work_reasons.append(f"Mandatory Lockout/Tagout (LOTO) verification missing for {wtype}.")

        if wtype == "confined_space":
            o2 = p.get("gas_test_o2_pct")
            lel = p.get("gas_test_lel_pct")
            age = p.get("gas_test_age_mins")
            if o2 is None or lel is None or age is None:
                stop_work_reasons.append("Mandatory atmospheric gas test fields missing (absent != safe).")
            else:
                if not (o2_min <= float(o2) <= o2_max):
                    stop_work_reasons.append(f"Unsafe O2 level {o2}% (must be {o2_min}%-{o2_max}%).")
                if float(lel) > max_lel:
                    stop_work_reasons.append(f"Flammable LEL {lel}% exceeds {max_lel}% limit.")
                if int(age) > max_gas_age:
                    stop_work_reasons.append(f"Gas test age {age}m exceeds {max_gas_age}m recency limit.")

        if wtype == "hot_work" and not bool(p.get("fire_watch_assigned", False)):
            stop_work_reasons.append("Dedicated Fire Watch not assigned for hot work.")

        status = "STOP_WORK_BLOCKED" if stop_work_reasons else "ELIGIBLE_FOR_EHS_ISSUE"
        audits.append(
            {
                "permit_id": pid,
                "facility": str(p.get("facility") or "Plant"),
                "work_type": wtype,
                "permit_status": status,
                "stop_work_reasons": stop_work_reasons,
            }
        )

    return {
        "skill": "ehs-safety-permit-auditor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "permits_audited": len(audits),
            "stop_work_blocked_count": sum(1 for a in audits if a["permit_status"] == "STOP_WORK_BLOCKED"),
            "eligible_count": sum(1 for a in audits if a["permit_status"] == "ELIGIBLE_FOR_EHS_ISSUE"),
        },
        "permit_audits": audits,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# EHS Permit-to-Work (PTW) & LOTO Safety Audit (As Of {result['as_of_date']})",
            "",
            f"- **Permits Audited:** {s['permits_audited']} | **STOP WORK Blocked:** {s['stop_work_blocked_count']} | "
            f"**Eligible for EHS Sign-Off:** {s['eligible_count']}",
            "",
            "| Permit | Facility | Work Type | Status | Safety Defects |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for a in result["permit_audits"]:
        notes = "; ".join(a["stop_work_reasons"]) or "All mandatory checks verified"
        lines.append(f"| `{a['permit_id']}` | {a['facility']} | `{a['work_type']}` | `{a['permit_status']}` | {notes} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit EHS Permit-to-Work packages for LOTO and gas safety.")
    parser.add_argument("--input", required=True, type=Path, help="Path to permits JSON")
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
