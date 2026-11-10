#!/usr/bin/env python3
"""Evaluates insurance claims against policy dates, exclusions, deductibles, sublimits, and coinsurance."""

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
    "high_value_claim_threshold": 100000.0,
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


def _evaluate_claim(c: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    cid = str(c.get("claim_id") or "CLM-1")
    pol = c.get("policy") or {}
    peril = str(c.get("peril") or "general").lower().strip()
    claimed = float(c.get("claimed_amount_usd") or 0.0)
    loss_dt = _parse_date(c.get("loss_date"))
    eff_dt = _parse_date(pol.get("effective_date"))
    exp_dt = _parse_date(pol.get("expiration_date"))
    doc_ok = bool(c.get("documentation_complete", True))
    excluded = {str(p).lower().strip() for p in pol.get("excluded_perils", [])}

    high_val_thresh = float(cfg.get("high_value_claim_threshold", 100000.0))

    in_period = bool(loss_dt and eff_dt and exp_dt and eff_dt <= loss_dt <= exp_dt)
    reasons: list[str] = []

    if not in_period:
        reasons.append(f"Loss date {loss_dt} outside policy period [{eff_dt}, {exp_dt}].")
        return {
            "claim_id": cid,
            "peril": peril,
            "claimed_amount_usd": round(claimed, 2),
            "net_payable_usd": 0.0,
            "reserve_escalation": False,
            "triage_decision": "COVERAGE_DENIED_OUT_OF_PERIOD",
            "notes": reasons,
        }

    if peril in excluded:
        reasons.append(f"Peril '{peril}' is explicitly excluded under policy {pol.get('policy_id')}.")
        return {
            "claim_id": cid,
            "peril": peril,
            "claimed_amount_usd": round(claimed, 2),
            "net_payable_usd": 0.0,
            "reserve_escalation": False,
            "triage_decision": "COVERAGE_DENIED_EXCLUSION",
            "notes": reasons,
        }

    deductible = float(pol.get("deductible_usd") or 0.0)
    coinsurance_insurer_pct = float(pol.get("insurer_coinsurance_pct", 100.0)) / 100.0
    sublimits = {str(k).lower().strip(): float(v) for k, v in (pol.get("sublimits") or {}).items()}
    agg_limit = float(pol.get("aggregate_limit_usd") or claimed)

    after_ded = max(0.0, claimed - deductible)
    insurer_portion = after_ded * coinsurance_insurer_pct
    capped = min(insurer_portion, sublimits.get(peril, agg_limit), agg_limit)
    reserve_esc = capped >= high_val_thresh

    if not doc_ok:
        decision = "PENDING_EVIDENCE_HOLD"
        reasons.append("Mandatory supporting claim evidence incomplete.")
    elif reserve_esc:
        decision = "RESERVE_ESCALATION_SENIOR_ADJUSTER"
        reasons.append(f"Net payable ${capped:,.2f} >= ${high_val_thresh:,.0f} authority cap.")
    else:
        decision = "ELIGIBLE_FOR_ADJUSTER_SIGN_OFF"

    return {
        "claim_id": cid,
        "peril": peril,
        "claimed_amount_usd": round(claimed, 2),
        "deductible_applied_usd": round(deductible, 2),
        "net_payable_usd": round(capped, 2),
        "reserve_escalation": reserve_esc,
        "triage_decision": decision,
        "notes": reasons,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    claims = data.get("claims") or ([data] if "claim_id" in data else [])
    triaged = [_evaluate_claim(c, cfg) for c in claims]

    return {
        "skill": "insurance-claims-triage-pack",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "claims_triaged": len(triaged),
            "denied_count": sum(1 for t in triaged if t["triage_decision"].startswith("COVERAGE_DENIED")),
            "reserve_escalation_count": sum(1 for t in triaged if t["reserve_escalation"]),
            "total_claimed_usd": round(sum(t["claimed_amount_usd"] for t in triaged), 2),
            "total_net_payable_usd": round(sum(t["net_payable_usd"] for t in triaged), 2),
        },
        "claim_evaluations": triaged,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Insurance Claims Coverage, Sublimit & Reserve Triage",
            "",
            f"- **Claims Triaged:** {s['claims_triaged']} | **Denied:** {s['denied_count']} | "
            f"**Reserve Escalations:** {s['reserve_escalation_count']}",
            f"- **Total Claimed:** ${s['total_claimed_usd']:,.2f} | **Calculated Net Payable:** ${s['total_net_payable_usd']:,.2f}",
            "",
            "| Claim ID | Peril | Claimed | Net Payable | Decision | Notes |",
            "| :--- | :--- | ---: | ---: | :--- | :--- |",
        ]
    )
    for t in result["claim_evaluations"]:
        lines.append(
            f"| `{t['claim_id']}` | {t['peril']} | ${t['claimed_amount_usd']:,.2f} | "
            f"**${t['net_payable_usd']:,.2f}** | `{t['triage_decision']}` | {'; '.join(t['notes']) or 'Covered'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate insurance claims against policy periods, deductibles, and limits.")
    parser.add_argument("--input", required=True, type=Path, help="Path to claims JSON")
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
