#!/usr/bin/env python3
"""Builds multimodal campaign deliverable matrices, identifies funnel/audience gaps, and validates launch readiness."""

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
    "required_funnel_stages": ["Awareness", "Consideration", "Conversion"],
    "min_production_buffer_days": 5,
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
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    campaign_name = str(data.get("campaign_name") or "Q4 Integrated Campaign")
    budget_cap = float(data.get("total_budget_usd") or 0.0)
    launch_dt = _parse_date(data.get("launch_date")) or date(2026, 12, 1)
    audiences = [str(a) for a in data.get("target_audiences", [])]
    channels = [str(c) for c in data.get("channels", [])]
    req_stages = [str(s) for s in cfg.get("required_funnel_stages", DEFAULT_CONFIG["required_funnel_stages"])]
    buffer_days = int(cfg.get("min_production_buffer_days", 5))

    deliverables = data.get("deliverables", [])
    covered_cells: set[tuple[str, str]] = set()
    covered_aud_stage: set[tuple[str, str]] = set()
    planned_spend = 0.0
    late_assets: list[dict[str, Any]] = []
    ready_cnt = 0

    for d in deliverables:
        did = str(d.get("asset_id") or "DELIV-1")
        aud = str(d.get("audience") or "")
        ch = str(d.get("channel") or "")
        stg = str(d.get("funnel_stage") or "")
        cost = float(d.get("estimated_cost_usd") or 0.0)
        status = str(d.get("status") or "PLANNED").upper()
        due_dt = _parse_date(d.get("due_date"))

        planned_spend += cost
        if aud and ch:
            covered_cells.add((aud, ch))
        if aud and stg:
            covered_aud_stage.add((aud, stg))
        if status == "APPROVED":
            ready_cnt += 1
        if due_dt is not None and (launch_dt - due_dt).days < buffer_days:
            late_assets.append(
                {
                    "asset_id": did,
                    "due_date": due_dt.isoformat(),
                    "buffer_days_remaining": (launch_dt - due_dt).days,
                }
            )

    missing_channel_cells = [
        {"audience": a, "channel": c}
        for a in audiences
        for c in channels
        if (a, c) not in covered_cells
    ]
    missing_funnel_cells = [
        {"audience": a, "funnel_stage": st}
        for a in audiences
        for st in req_stages
        if (a, st) not in covered_aud_stage
    ]

    budget_delta = planned_spend - budget_cap if budget_cap > 0 else 0.0
    over_budget = budget_cap > 0 and planned_spend > budget_cap

    if over_budget or late_assets or missing_channel_cells:
        readiness = "LAUNCH_AT_RISK_GAPS_PRESENT"
    elif missing_funnel_cells:
        readiness = "PARTIAL_FUNNEL_COVERAGE"
    else:
        readiness = "BRIEF_LOCKED_FOR_PRODUCTION"

    return {
        "skill": "multimodal-campaign-brief",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "campaign_name": campaign_name,
        "launch_date": launch_dt.isoformat(),
        "summary": {
            "deliverable_count": len(deliverables),
            "approved_deliverables": ready_cnt,
            "total_budget_usd": round(budget_cap, 2),
            "planned_spend_usd": round(planned_spend, 2),
            "budget_variance_usd": round(budget_delta, 2),
            "over_budget": over_budget,
            "missing_audience_channel_cells": len(missing_channel_cells),
            "missing_funnel_stage_cells": len(missing_funnel_cells),
            "late_critical_path_assets": len(late_assets),
            "campaign_readiness": readiness,
        },
        "missing_channel_cells": missing_channel_cells,
        "missing_funnel_cells": missing_funnel_cells,
        "late_assets": late_assets,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Multimodal Campaign Matrix — {result['campaign_name']} (Launch {result['launch_date']})",
            "",
            f"- **Readiness:** `{s['campaign_readiness']}` | **Deliverables:** {s['deliverable_count']} (Approved: {s['approved_deliverables']})",
            f"- **Planned Spend:** ${s['planned_spend_usd']:,.2f} vs **Budget:** ${s['total_budget_usd']:,.2f} "
            f"(Var: ${s['budget_variance_usd']:+,.2f})",
            f"- **Matrix Gaps:** {s['missing_audience_channel_cells']} Audience×Channel | "
            f"{s['missing_funnel_stage_cells']} Funnel Stage | **Late Assets (< buffer):** {s['late_critical_path_assets']}",
        ]
    )
    if result["missing_channel_cells"]:
        lines.extend(["", "## Missing Audience × Channel Coverage"])
        for g in result["missing_channel_cells"]:
            lines.append(f"- `{g['audience']}` × `{g['channel']}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate campaign brief asset matrix, budget, and launch buffers.")
    parser.add_argument("--input", required=True, type=Path, help="Path to campaign brief JSON")
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
