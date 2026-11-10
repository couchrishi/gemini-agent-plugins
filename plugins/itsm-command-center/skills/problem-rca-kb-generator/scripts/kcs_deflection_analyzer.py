#!/usr/bin/env python3
"""Mines resolved tickets for repeat Problem candidates, MTTR, L1 deflection savings, and KCS checks."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "cost_per_l1_ticket_usd": 28.0,
    "expected_kcs_deflection_rate": 0.35,
}
REQUIRED_KCS_SECTIONS = ("environment", "symptoms", "root_cause", "resolution_steps", "verification_check")


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


def load_payload(input_arg: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"tickets": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"tickets": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"tickets": data}
    return data


def _parse_dt(val: Any) -> dt.datetime | None:
    if not val:
        return None
    norm = str(val).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(norm)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    tickets = data.get("tickets") or data.get("records") or []
    kcs_drafts = data.get("kcs_drafts", [])
    sample_window_days = max(1, int(data.get("sample_window_days", 90)))
    unit_cost = float(cfg.get("cost_per_l1_ticket_usd", 28.0))
    deflection_rate = float(cfg.get("expected_kcs_deflection_rate", 0.35))
    metadata = data.get("metadata", {})

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Resolved ticket sample truncated; annualized figures scaled cautiously.")

    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    open_unresolved_count = 0
    canceled_count = 0

    for t in tickets:
        state = str(t.get("state") or "").lower()
        if state in {"8", "canceled", "cancelled"}:
            canceled_count += 1
            continue
        opened = _parse_dt(t.get("opened_at"))
        resolved = _parse_dt(t.get("resolved_at"))
        if resolved is None:
            # Never treat unresolved null timestamp as 0h MTTR
            open_unresolved_count += 1
            continue
        mttr_hours = max(0.0, (resolved - opened).total_seconds() / 3600.0) if opened else float(t.get("mttr_hours", 0.0))
        cat = str(t.get("category") or "General")
        sig = str(t.get("root_cause_signature") or t.get("short_description") or "unspecified").strip().lower()
        grouped[(cat, sig)].append(mttr_hours)

    annual_factor = 365.0 / sample_window_days
    candidates: list[dict[str, Any]] = []
    total_savings = 0.0
    for (cat, sig), durations in grouped.items():
        if len(durations) < 2 and len(tickets) > 3:
            continue
        durations_sorted = sorted(durations)
        mean_mttr = round(sum(durations_sorted) / len(durations_sorted), 2)
        p90_idx = min(len(durations_sorted) - 1, max(0, math.ceil(0.9 * len(durations_sorted)) - 1))
        p90_mttr = round(durations_sorted[p90_idx], 2)
        annual_vol = round(len(durations_sorted) * annual_factor, 1)
        deflected = round(annual_vol * deflection_rate, 1)
        savings = round(deflected * unit_cost, 2)
        total_savings += savings
        candidates.append(
            {
                "category": cat,
                "root_cause_signature": sig,
                "ticket_count": len(durations_sorted),
                "mean_mttr_hours": mean_mttr,
                "p90_mttr_hours": p90_mttr,
                "estimated_annual_tickets": annual_vol,
                "estimated_annual_deflected": deflected,
                "estimated_annual_savings_usd": savings,
            }
        )

    candidates.sort(key=lambda c: c["estimated_annual_savings_usd"], reverse=True)

    kcs_validations: list[dict[str, Any]] = []
    for draft in kcs_drafts:
        missing = [sec for sec in REQUIRED_KCS_SECTIONS if not str(draft.get(sec) or "").strip()]
        kcs_validations.append(
            {
                "article_id": draft.get("article_id"),
                "title": draft.get("title"),
                "kcs_completeness_passed": len(missing) == 0,
                "missing_sections": missing,
            }
        )

    return {
        "skill": "problem-rca-kb-generator",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "total_tickets_scanned": len(tickets),
            "open_unresolved_excluded": open_unresolved_count,
            "canceled_excluded": canceled_count,
            "problem_candidate_count": len(candidates),
            "total_estimated_annual_savings_usd": round(total_savings, 2),
            "kcs_drafts_checked": len(kcs_validations),
        },
        "problem_candidates": candidates,
        "kcs_validations": kcs_validations,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Problem Candidate & KCS Deflection Analysis",
            "",
            f"- **Tickets Scanned:** {s['total_tickets_scanned']} (Excluded open: {s['open_unresolved_excluded']}, canceled: {s['canceled_excluded']})",
            f"- **Problem Candidates:** {s['problem_candidate_count']} | **Estimated Annual L1 Savings:** ${s['total_estimated_annual_savings_usd']:,.2f}",
            "",
            "| Category | Root Cause Signature | Count | Mean MTTR (h) | Annual Savings (USD) |",
            "| :--- | :--- | ---: | ---: | ---: |",
        ]
    )
    for c in result["problem_candidates"]:
        lines.append(
            f"| {c['category']} | {c['root_cause_signature']} | {c['ticket_count']} | "
            f"{c['mean_mttr_hours']:.2f} | ${c['estimated_annual_savings_usd']:,.2f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Identify Problem RCA candidates and KCS deflection ROI.")
    parser.add_argument("--input", required=True, type=Path, help="Path to resolved tickets JSON or CSV")
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
