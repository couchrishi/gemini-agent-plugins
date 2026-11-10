#!/usr/bin/env python3
"""Lints SOW deliverables and clauses for open-ended scope creep, missing acceptance criteria, and margin breaches."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_sow_gross_margin_pct": 30.0,
    "critical_margin_floor_pct": 20.0,
    "max_acceptance_business_days": 10,
}

SCOPE_CREEP_PATTERNS = [
    (re.compile(r"\ball\s+work\s+required\b", re.I), "Unbounded 'all work required' obligation"),
    (re.compile(r"\bunlimited\s+(revisions|changes|support)\b", re.I), "Unlimited revisions/changes clause"),
    (re.compile(r"\bsole\s+and\s+absolute\s+satisfaction\b", re.I), "Subjective acceptance veto"),
    (re.compile(r"\bno\s+additional\s+cost\s+regardless\b", re.I), "Fixed-fee uncapped change exposure"),
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


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    min_margin = float(cfg.get("min_sow_gross_margin_pct", 30.0))
    crit_margin = float(cfg.get("critical_margin_floor_pct", 20.0))
    max_accept_days = int(cfg.get("max_acceptance_business_days", 10))

    fee = float(data.get("fixed_fee_usd") or 0.0)
    cost = float(data.get("estimated_cost_usd") or 0.0)
    margin_pct = ((fee - cost) / fee * 100.0) if fee > 0 else 0.0
    accept_days = data.get("acceptance_business_days")

    blockers: list[str] = []
    warnings: list[str] = []
    clause_hits: list[dict[str, Any]] = []

    if margin_pct < crit_margin:
        blockers.append(f"SOW gross margin {margin_pct:.1f}% breaches hard {crit_margin:.0f}% floor (Score 9).")
    elif margin_pct < min_margin:
        warnings.append(f"SOW gross margin {margin_pct:.1f}% sits below {min_margin:.0f}% standard target (Score 3).")

    if accept_days is None:
        warnings.append("Milestone acceptance window omitted (deemed acceptance not bounded).")
    elif int(accept_days) > max_accept_days:
        warnings.append(f"Acceptance window {accept_days} business days exceeds {max_accept_days}-day ceiling.")

    for c in data.get("clauses", []):
        cid = str(c.get("clause_id") or "CL")
        txt = str(c.get("text") or "")
        for pat, desc in SCOPE_CREEP_PATTERNS:
            if pat.search(txt):
                blockers.append(f"Clause {cid}: {desc}")
                clause_hits.append({"clause_id": cid, "issue": desc, "severity": 9})

    missing_criteria: list[str] = []
    for d in data.get("deliverables", []):
        did = str(d.get("deliverable_id") or "DELIV")
        if not str(d.get("acceptance_criteria") or "").strip():
            missing_criteria.append(did)
            warnings.append(f"Deliverable {did} lacks objective acceptance criteria.")

    if not data.get("client_dependencies"):
        warnings.append("SOW omits Client Dependencies & Assumptions schedule.")

    gate = "BLOCKED_SCORE_9" if blockers else ("REDLINES_REQUIRED" if warnings else "READY_FOR_EXECUTION")

    return {
        "skill": "sow-scope-margin-auditor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "sow_id": str(data.get("sow_id") or "SOW-1"),
            "fixed_fee_usd": round(fee, 2),
            "estimated_cost_usd": round(cost, 2),
            "gross_margin_pct": round(margin_pct, 2),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "missing_acceptance_criteria_count": len(missing_criteria),
            "sow_gate_status": gate,
        },
        "blockers": blockers,
        "warnings": warnings,
        "clause_risk_hits": clause_hits,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# SOW Scope Creep & Margin Audit — `{s['sow_id']}`",
            "",
            f"- **Fixed Fee:** ${s['fixed_fee_usd']:,.2f} | **Est Cost:** ${s['estimated_cost_usd']:,.2f} | "
            f"**Gross Margin:** {s['gross_margin_pct']:.2f}% | **Gate:** `{s['sow_gate_status']}`",
            f"- **Score-9 Blockers:** {s['blocker_count']} | **Negotiable Warnings:** {s['warning_count']}",
        ]
    )
    if result["blockers"]:
        lines.extend(["", "## Walk-Away Scope/Margin Blockers"])
        lines.extend(f"- {b}" for b in result["blockers"])
    if result["warnings"]:
        lines.extend(["", "## Redline Warnings"])
        lines.extend(f"- {w}" for w in result["warnings"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit SOW clauses for open-ended scope creep and margin breaches.")
    parser.add_argument("--input", required=True, type=Path, help="Path to SOW payload JSON")
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
