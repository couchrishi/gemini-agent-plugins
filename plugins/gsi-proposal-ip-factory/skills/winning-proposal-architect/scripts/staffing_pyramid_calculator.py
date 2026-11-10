#!/usr/bin/env python3
"""Models GSI staffing pyramids, onshore/offshore leverage ratios, blended bill rates, and gross margins."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_sow_gross_margin_pct": 30.0,
    "critical_margin_floor_pct": 20.0,
    "target_offshore_leverage_pct": 55.0,
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

    min_margin = float(cfg.get("min_sow_gross_margin_pct", 30.0))
    crit_margin = float(cfg.get("critical_margin_floor_pct", 20.0))
    target_offshore = float(cfg.get("target_offshore_leverage_pct", 55.0))

    total_hours = 0.0
    offshore_hours = 0.0
    total_revenue = 0.0
    total_cost = 0.0
    phase_summaries: list[dict[str, Any]] = []

    for ph in data.get("phases", []):
        pname = str(ph.get("phase_name") or "Delivery Phase")
        weeks = float(ph.get("duration_weeks") or 1.0)
        p_hours = 0.0
        p_off_hours = 0.0
        p_rev = 0.0
        p_cost = 0.0

        for r in ph.get("roles", []):
            fte = float(r.get("fte_count") or 1.0)
            hrs_wk = float(r.get("hours_per_week") or 40.0)
            loc = str(r.get("delivery_location") or "onshore").lower().strip()
            bill = float(r.get("bill_rate_hourly") or 0.0)
            cost = float(r.get("cost_rate_hourly") or 0.0)

            role_hrs = weeks * fte * hrs_wk
            role_rev = role_hrs * bill
            role_cost = role_hrs * cost
            p_hours += role_hrs
            if loc in {"offshore", "nearshore"}:
                p_off_hours += role_hrs
            p_rev += role_rev
            p_cost += role_cost

        p_gm_pct = ((p_rev - p_cost) / p_rev * 100.0) if p_rev > 0 else 0.0
        phase_summaries.append(
            {
                "phase_name": pname,
                "duration_weeks": weeks,
                "total_hours": round(p_hours, 1),
                "offshore_leverage_pct": round((p_off_hours / p_hours * 100.0) if p_hours > 0 else 0.0, 1),
                "revenue_usd": round(p_rev, 2),
                "cost_usd": round(p_cost, 2),
                "gross_margin_pct": round(p_gm_pct, 2),
            }
        )
        total_hours += p_hours
        offshore_hours += p_off_hours
        total_revenue += p_rev
        total_cost += p_cost

    gm_usd = total_revenue - total_cost
    gm_pct = (gm_usd / total_revenue * 100.0) if total_revenue > 0 else 0.0
    offshore_pct = (offshore_hours / total_hours * 100.0) if total_hours > 0 else 0.0
    blended_rate = (total_revenue / total_hours) if total_hours > 0 else 0.0

    if gm_pct < crit_margin:
        margin_gate = "CRITICAL_BELOW_20_BLOCKED"
    elif gm_pct < min_margin:
        margin_gate = "FINANCE_DESK_EXCEPTION_REQUIRED"
    else:
        margin_gate = "WITHIN_MARGIN_TARGET"

    return {
        "skill": "winning-proposal-architect",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "total_effort_hours": round(total_hours, 1),
            "offshore_leverage_pct": round(offshore_pct, 2),
            "below_offshore_target": offshore_pct < target_offshore,
            "total_revenue_usd": round(total_revenue, 2),
            "total_cost_usd": round(total_cost, 2),
            "gross_profit_usd": round(gm_usd, 2),
            "blended_gross_margin_pct": round(gm_pct, 2),
            "blended_bill_rate_hourly": round(blended_rate, 2),
            "margin_gate": margin_gate,
        },
        "phase_breakdown": phase_summaries,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# GSI Delivery Staffing Pyramid & Commercial Margin Model",
            "",
            f"- **Total Revenue:** ${s['total_revenue_usd']:,.2f} | **Loaded Cost:** ${s['total_cost_usd']:,.2f} | "
            f"**Gross Margin:** {s['blended_gross_margin_pct']:.2f}% (`{s['margin_gate']}`)",
            f"- **Total Effort:** {s['total_effort_hours']:,.1f} hrs | **Blended Rate:** ${s['blended_bill_rate_hourly']:,.2f}/hr | "
            f"**Offshore Leverage:** {s['offshore_leverage_pct']:.1f}%",
            "",
            "| Phase | Weeks | Hours | Offshore % | Revenue | Cost | Margin % |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for p in result["phase_breakdown"]:
        lines.append(
            f"| {p['phase_name']} | {p['duration_weeks']:.1f} | {p['total_hours']:,.1f} | "
            f"{p['offshore_leverage_pct']:.1f}% | ${p['revenue_usd']:,.2f} | ${p['cost_usd']:,.2f} | "
            f"{p['gross_margin_pct']:.2f}% |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute GSI delivery staffing pyramid, leverage, and margin.")
    parser.add_argument("--input", required=True, type=Path, help="Path to proposal staffing JSON")
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
