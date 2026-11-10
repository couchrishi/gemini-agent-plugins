#!/usr/bin/env python3
"""Validates grant budget allowability, F&A indirect cost caps, cost-share match, PI effort, and accreditation freshness."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "max_indirect_fa_rate_pct": 52.0,
    "max_evidence_age_days": 365,
    "unallowable_categories": [
        "alcohol",
        "entertainment",
        "lobbying",
        "fines_penalties",
        "alumni_fundraising",
        "first_class_airfare",
    ],
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


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    as_of_str = str(data.get("as_of_date") or "2026-10-15")
    as_of_dt = date.fromisoformat(as_of_str[:10])
    max_fa_cap = float(data.get("sponsor_fa_cap_pct") or cfg.get("max_indirect_fa_rate_pct", 52.0))
    max_age_days = int(cfg.get("max_evidence_age_days", 365))
    unallowable_cats = {c.lower() for c in cfg.get("unallowable_categories", DEFAULT_CONFIG["unallowable_categories"])}

    budget_lines = data.get("budget_lines") or []
    artifacts = data.get("accreditation_artifacts") or []
    pi_allocations = data.get("pi_effort_allocations") or []

    mtdc_base = 0.0
    indirect_total = 0.0
    cost_share_total = 0.0
    unallowable_total = 0.0
    budget_findings: list[dict[str, Any]] = []

    for line in budget_lines:
        lid = str(line.get("line_id") or "BL-1")
        cat = str(line.get("category") or "general").lower()
        amt = float(line.get("amount_usd") or 0.0)
        is_indirect = bool(line.get("is_indirect_fa", False))
        mtdc_exempt = bool(line.get("mtdc_exempt", False))
        cs_amt = float(line.get("cost_share_amount_usd") or 0.0)
        cost_share_total += cs_amt

        if cat in unallowable_cats:
            unallowable_total += amt
            budget_findings.append(
                {
                    "line_id": lid,
                    "category": cat,
                    "amount_usd": round(amt, 2),
                    "severity": "BLOCKER",
                    "issue": f"UNALLOWABLE_COST_CATEGORY ({cat})",
                }
            )
            continue

        if is_indirect:
            indirect_total += amt
        elif not mtdc_exempt:
            mtdc_base += amt

    max_allowed_indirect = round(mtdc_base * (max_fa_cap / 100.0), 2)
    fa_excess = round(max(0.0, indirect_total - max_allowed_indirect), 2)
    if fa_excess > 0.01:
        budget_findings.append(
            {
                "line_id": "INDIRECT_FA_ROLLUP",
                "category": "indirect_fa",
                "amount_usd": fa_excess,
                "severity": "BLOCKER",
                "issue": f"FA_CAP_EXCEEDED (${indirect_total:,.2f} > ${max_allowed_indirect:,.2f} @ {max_fa_cap:.1f}% MTDC)",
            }
        )

    req_match_pct = float(data.get("required_cost_share_pct") or 0.0)
    total_direct_cost = mtdc_base + sum(float(l.get("amount_usd") or 0.0) for l in budget_lines if l.get("mtdc_exempt"))
    actual_match_pct = (cost_share_total / total_direct_cost * 100.0) if total_direct_cost > 0 else 0.0
    if req_match_pct > 0 and actual_match_pct < req_match_pct:
        budget_findings.append(
            {
                "line_id": "COST_SHARE_MATCH",
                "category": "cost_share",
                "amount_usd": round(total_direct_cost * (req_match_pct / 100.0) - cost_share_total, 2),
                "severity": "BLOCKER",
                "issue": f"COST_SHARE_SHORTFALL ({actual_match_pct:.1f}% < {req_match_pct:.1f}% required)",
            }
        )

    pi_findings: list[dict[str, Any]] = []
    for pi in pi_allocations:
        name = str(pi.get("pi_name") or pi.get("researcher_id") or "PI-1")
        total_pct = float(pi.get("proposed_effort_pct") or 0.0) + float(pi.get("existing_commitments_pct") or 0.0)
        if total_pct > 100.0:
            pi_findings.append({"pi_name": name, "total_effort_pct": round(total_pct, 1), "issue": "PI_OVERALLOCATED_GT_100_PCT"})

    artifact_findings: list[dict[str, Any]] = []
    for art in artifacts:
        aid = str(art.get("artifact_id") or "ART-1")
        status = str(art.get("status") or "PRESENT").upper()
        last_upd = art.get("last_verified_date")
        age_days = (as_of_dt - date.fromisoformat(str(last_upd)[:10])).days if last_upd else None
        if status != "PRESENT":
            artifact_findings.append({"artifact_id": aid, "status": "MISSING_REQUIRED_EVIDENCE", "age_days": age_days})
        elif age_days is not None and age_days > max_age_days:
            artifact_findings.append({"artifact_id": aid, "status": f"STALE_EVIDENCE ({age_days}d > {max_age_days}d)", "age_days": age_days})

    blocker_count = len(budget_findings) + len(pi_findings) + len(artifact_findings)
    readiness = "BLOCKED_REMEDIATE_BEFORE_SUBMISSION" if blocker_count > 0 else "READY_FOR_SPONSOR_SUBMISSION"

    return {
        "skill": "grant-accreditation-evidence-pack",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "award_or_review_id": str(data.get("grant_id") or "GRANT-001"),
            "mtdc_base_usd": round(mtdc_base, 2),
            "indirect_fa_requested_usd": round(indirect_total, 2),
            "max_allowed_indirect_usd": max_allowed_indirect,
            "unallowable_amount_usd": round(unallowable_total, 2),
            "cost_share_match_pct": round(actual_match_pct, 2),
            "blocker_count": blocker_count,
            "submission_readiness": readiness,
        },
        "budget_findings": budget_findings,
        "pi_effort_findings": pi_findings,
        "accreditation_artifact_findings": artifact_findings,
        "truncation_warnings": ["Grant sub-ledger truncated; F&A ceiling calculation may be incomplete."] if data.get("truncated") else [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Grant Budget Compliance & Accreditation Evidence Audit (`{s['award_or_review_id']}`)",
            "",
            f"- **Readiness:** `{s['submission_readiness']}` | **Blockers:** {s['blocker_count']} | "
            f"**MTDC Base:** ${s['mtdc_base_usd']:,.2f} | **Indirect Requested vs Allowed:** "
            f"${s['indirect_fa_requested_usd']:,.2f} / ${s['max_allowed_indirect_usd']:,.2f}",
            "",
            "| Scope | ID | Issue | Amount / Metric |",
            "| :--- | :--- | :--- | ---: |",
        ]
    )
    for bf in result["budget_findings"]:
        lines.append(f"| Budget | `{bf['line_id']}` | {bf['issue']} | ${bf['amount_usd']:,.2f} |")
    for pf in result["pi_effort_findings"]:
        lines.append(f"| PI Effort | {pf['pi_name']} | {pf['issue']} | {pf['total_effort_pct']:.1f}% |")
    for af in result["accreditation_artifact_findings"]:
        lines.append(f"| Evidence | `{af['artifact_id']}` | {af['status']} | {af['age_days'] or 'N/A'}d |")
    if s["blocker_count"] == 0:
        lines.append("| All | `OK` | All budget, effort, and evidence checks passed | 0 |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate grant allowability, F&A caps, PI effort, and accreditation freshness.")
    parser.add_argument("--input", required=True, type=Path, help="Path to grant & accreditation packet JSON")
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
