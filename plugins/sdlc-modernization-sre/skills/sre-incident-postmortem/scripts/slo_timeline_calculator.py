#!/usr/bin/env python3
"""Computes SLO error-budget burn rate, TTD/TTM/TTR postmortem intervals, and action-item SLAs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "default_slo_availability_pct": 99.9,
    "postmortem_action_sla_days": 14,
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
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    incidents = data.get("incidents") or ([data["incident"]] if "incident" in data else [data] if "detected_at" in data else [])
    action_items = list(data.get("action_items", []))
    slo_pct = float(data.get("slo_target_pct", cfg.get("default_slo_availability_pct", 99.9)))
    window_days = max(1, int(data.get("window_days", 30)))
    as_of = _parse_dt(data.get("as_of_time")) or dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)
    action_sla_days = int(cfg.get("postmortem_action_sla_days", 14))

    total_window_min = window_days * 24.0 * 60.0
    error_budget_min = total_window_min * (1.0 - slo_pct / 100.0)

    timeline_results: list[dict[str, Any]] = []
    total_bad_min = 0.0
    for idx, inc in enumerate(incidents):
        iid = str(inc.get("incident_id") or f"INC-{idx + 1}")
        started = _parse_dt(inc.get("started_at"))
        detected = _parse_dt(inc.get("detected_at"))
        mitigated = _parse_dt(inc.get("mitigated_at"))
        resolved = _parse_dt(inc.get("resolved_at"))
        impact_factor = float(inc.get("impact_weight", 1.0))

        ttd = round(max(0.0, (detected - started).total_seconds() / 60.0), 2) if (started and detected) else None
        ttm = round(max(0.0, (mitigated - detected).total_seconds() / 60.0), 2) if (detected and mitigated) else None
        ttr = round(max(0.0, (resolved - detected).total_seconds() / 60.0), 2) if (detected and resolved) else None

        end_point = mitigated or resolved or as_of
        start_point = started or detected or as_of
        raw_outage_min = max(0.0, (end_point - start_point).total_seconds() / 60.0)
        weighted_bad_min = round(raw_outage_min * impact_factor, 2)
        total_bad_min += weighted_bad_min

        timeline_results.append(
            {
                "incident_id": iid,
                "service": inc.get("service", "core"),
                "ttd_minutes": ttd,
                "ttm_minutes": ttm,
                "ttr_minutes": ttr,
                "raw_outage_minutes": round(raw_outage_min, 2),
                "impact_weight": impact_factor,
                "error_budget_minutes_burned": weighted_bad_min,
            }
        )

    burn_pct = round((total_bad_min / error_budget_min) * 100.0, 2) if error_budget_min > 0 else 0.0
    achieved_avail = round((1.0 - total_bad_min / total_window_min) * 100.0, 4)

    overdue_actions = 0
    unverified_actions = 0
    evaluated_actions: list[dict[str, Any]] = []
    for idx, act in enumerate(action_items):
        aid = str(act.get("action_id") or f"AI-{idx + 1}")
        status = str(act.get("status") or "open").lower()
        due = _parse_dt(act.get("due_date"))
        if status in {"done", "closed", "completed"}:
            sla_state = "COMPLETED"
        elif due is None:
            unverified_actions += 1
            sla_state = "MISSING_DUE_DATE"
        elif as_of > due:
            overdue_actions += 1
            sla_state = "OVERDUE"
        else:
            sla_state = "ON_TRACK"
        evaluated_actions.append(
            {
                "action_id": aid,
                "owner": act.get("owner", "UNASSIGNED"),
                "title": act.get("title"),
                "status": status,
                "sla_state": sla_state,
                "target_sla_days": action_sla_days,
            }
        )

    return {
        "skill": "sre-incident-postmortem",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "slo_target_pct": slo_pct,
            "window_days": window_days,
            "monthly_error_budget_minutes": round(error_budget_min, 2),
            "total_minutes_burned": round(total_bad_min, 2),
            "error_budget_consumed_pct": burn_pct,
            "achieved_availability_pct": achieved_avail,
            "slo_breached": achieved_avail < slo_pct,
            "incident_count": len(timeline_results),
            "overdue_action_count": overdue_actions,
            "missing_due_date_action_count": unverified_actions,
        },
        "incident_timelines": timeline_results,
        "action_items": evaluated_actions,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# SRE Postmortem Timeline & SLO Burn Report",
            "",
            f"- **SLO Target:** {s['slo_target_pct']}% ({s['monthly_error_budget_minutes']}m budget / {s['window_days']}d)",
            f"- **Burned:** {s['total_minutes_burned']}m ({s['error_budget_consumed_pct']}%) | **Achieved Availability:** {s['achieved_availability_pct']}% (Breached: `{s['slo_breached']}`)",
            f"- **Postmortem Actions:** Overdue={s['overdue_action_count']}, Missing Due Date={s['missing_due_date_action_count']}",
            "",
            "| Incident | Service | TTD (m) | TTM (m) | TTR (m) | Burned (m) |",
            "| :--- | :--- | ---: | ---: | ---: | ---: |",
        ]
    )
    for t in result["incident_timelines"]:
        lines.append(
            f"| `{t['incident_id']}` | {t['service']} | {t['ttd_minutes']} | {t['ttm_minutes']} | "
            f"{t['ttr_minutes']} | {t['error_budget_minutes_burned']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calculate SRE postmortem TTD/TTM/TTR and SLO burn rate.")
    parser.add_argument("--input", required=True, type=Path, help="Path to postmortem timeline JSON")
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
