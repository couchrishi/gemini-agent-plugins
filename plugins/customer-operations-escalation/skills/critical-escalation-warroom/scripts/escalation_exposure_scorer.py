#!/usr/bin/env python3
"""Scores VIP customer escalations by ARR at risk, renewal proximity, outage impact, and ticket backlog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "war_room_score_threshold": 70.0,
    "vip_arr_threshold_usd": 250000.0,
    "imminent_renewal_days": 90,
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

    war_thresh = float(cfg.get("war_room_score_threshold", 70.0))
    vip_arr = float(cfg.get("vip_arr_threshold_usd", 250000.0))
    ren_window = int(cfg.get("imminent_renewal_days", 90))

    items = data.get("escalations", [])
    scored: list[dict[str, Any]] = []

    for e in items:
        eid = str(e.get("escalation_id") or "ESC-1")
        acct = str(e.get("account_name") or "Unknown Account")
        arr = float(e.get("arr_usd") or 0.0)
        ren_days = e.get("renewal_days")
        sev1 = int(e.get("open_sev1_tickets") or 0)
        sev2 = int(e.get("open_sev2_tickets") or 0)
        sla_breaches = int(e.get("sla_breached_count") or 0)
        outage_hrs = float(e.get("outage_hours_30d") or 0.0)
        comp_threat = bool(e.get("competitor_threat", False))

        score = 0.0
        drivers: list[str] = []
        if sev1 > 0:
            pts = min(30.0, sev1 * 18.0)
            score += pts
            drivers.append(f"{sev1} active Sev1 tickets (+{pts:.0f})")
        if sev2 > 0:
            pts = min(15.0, sev2 * 5.0)
            score += pts
        if sla_breaches > 0:
            pts = min(20.0, sla_breaches * 8.0)
            score += pts
            drivers.append(f"{sla_breaches} SLA breaches")
        if arr >= vip_arr:
            score += 15.0
            drivers.append(f"VIP ARR >= ${vip_arr:,.0f}")
        if ren_days is not None and int(ren_days) <= ren_window:
            score += 15.0
            drivers.append(f"Renewal in {ren_days}d")
        if outage_hrs >= 2.0:
            score += min(10.0, outage_hrs * 2.0)
            drivers.append(f"{outage_hrs:.1f}h downtime in 30d")
        if comp_threat:
            score += 10.0
            drivers.append("Active competitor evaluation")

        score = min(100.0, round(score, 1))
        if score >= war_thresh:
            tier = "WAR_ROOM_SEV0_EXEC"
        elif score >= 40.0:
            tier = "HIGH_TOUCH_TAM"
        else:
            tier = "STANDARD_QUEUE"

        scored.append(
            {
                "escalation_id": eid,
                "account_name": acct,
                "arr_usd": round(arr, 2),
                "renewal_days": ren_days,
                "exposure_score": score,
                "escalation_tier": tier,
                "drivers": drivers,
            }
        )

    scored.sort(key=lambda x: (-x["exposure_score"], -x["arr_usd"]))
    war_room = [x for x in scored if x["escalation_tier"] == "WAR_ROOM_SEV0_EXEC"]

    return {
        "skill": "critical-escalation-warroom",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "escalations_scored": len(scored),
            "war_room_count": len(war_room),
            "arr_at_war_room_risk_usd": round(sum(x["arr_usd"] for x in war_room), 2),
            "total_escalated_arr_usd": round(sum(x["arr_usd"] for x in scored), 2),
        },
        "scored_escalations": scored,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Critical Customer Escalation War-Room Triage",
            "",
            f"- **Escalations Scored:** {s['escalations_scored']} | **War-Room Exec:** {s['war_room_count']} | "
            f"**War-Room ARR at Risk:** ${s['arr_at_war_room_risk_usd']:,.2f}",
            "",
            "| Escalation | Account | ARR | Renewal (d) | Exposure Score | Tier | Primary Drivers |",
            "| :--- | :--- | ---: | ---: | ---: | :--- | :--- |",
        ]
    )
    for x in result["scored_escalations"]:
        lines.append(
            f"| `{x['escalation_id']}` | {x['account_name']} | ${x['arr_usd']:,.2f} | "
            f"{x['renewal_days'] if x['renewal_days'] is not None else '—'} | "
            f"**{x['exposure_score']:.1f}** | `{x['escalation_tier']}` | {', '.join(x['drivers']) or 'None'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score VIP escalations by churn exposure, ARR, and SLA breaches.")
    parser.add_argument("--input", required=True, type=Path, help="Path to escalations JSON")
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
