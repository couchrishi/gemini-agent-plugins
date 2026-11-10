#!/usr/bin/env python3
"""Builds personalized 30/60/90-day onboarding plans and detects stalled provisioning or compliance gates."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "mandatory_day1_gates": ["identity_sso_provisioning", "laptop_hardware_shipment", "security_policy_ack"],
    "stall_overdue_threshold": 1,
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
    mandatory_gates = [str(g) for g in cfg.get("mandatory_day1_gates", DEFAULT_CONFIG["mandatory_day1_gates"])]
    stall_thresh = int(cfg.get("stall_overdue_threshold", 1))

    hires = data.get("hires") or ([data] if "employee_id" in data else [])
    plans: list[dict[str, Any]] = []

    for hire in hires:
        eid = str(hire.get("employee_id") or "EMP-1")
        name = str(hire.get("employee_name") or eid)
        dept = str(hire.get("department") or "General")
        start_dt = _parse_date(hire.get("start_date")) or as_of
        tasks = hire.get("tasks", [])

        task_status_map = {str(t.get("task_id")): str(t.get("status") or "PENDING").upper() for t in tasks}
        present_task_ids = set(task_status_map.keys())
        missing_mandatory = sorted(set(mandatory_gates) - present_task_ids)

        overdue_tasks: list[dict[str, Any]] = []
        blocked_tasks: list[str] = []
        phase_counts = {"day_1": {"total": 0, "done": 0}, "day_30": {"total": 0, "done": 0}, "day_60": {"total": 0, "done": 0}, "day_90": {"total": 0, "done": 0}}
        completed = 0

        for t in tasks:
            tid = str(t.get("task_id") or "TASK")
            title = str(t.get("title") or tid)
            owner = str(t.get("owner_team") or "HR")
            status = str(t.get("status") or "PENDING").upper()
            offset_days = int(t.get("due_day_offset", 30))
            due_dt = start_dt + timedelta(days=offset_days)

            if offset_days <= 1:
                phase = "day_1"
            elif offset_days <= 30:
                phase = "day_30"
            elif offset_days <= 60:
                phase = "day_60"
            else:
                phase = "day_90"
            phase_counts[phase]["total"] += 1
            if status == "COMPLETED":
                completed += 1
                phase_counts[phase]["done"] += 1
            elif due_dt < as_of:
                overdue_tasks.append(
                    {
                        "task_id": tid,
                        "title": title,
                        "owner_team": owner,
                        "due_date": due_dt.isoformat(),
                        "days_overdue": (as_of - due_dt).days,
                    }
                )

            deps = [str(d) for d in t.get("blocked_by", [])]
            incomplete_deps = [d for d in deps if task_status_map.get(d) != "COMPLETED"]
            if status != "COMPLETED" and incomplete_deps:
                blocked_tasks.append(f"{tid} blocked by {', '.join(incomplete_deps)}")

        total_tasks = len(tasks)
        completion_pct = (completed / total_tasks * 100.0) if total_tasks > 0 else 0.0
        stalled = len(overdue_tasks) >= stall_thresh or len(missing_mandatory) > 0

        if missing_mandatory:
            health = "AT_RISK_MISSING_DAY1_GATES"
        elif overdue_tasks:
            health = "STALLED_OVERDUE_TASKS"
        elif total_tasks == 0:
            health = "UNPROVISIONED"
        elif completion_pct >= 100.0:
            health = "COMPLETED"
        else:
            health = "ON_TRACK"

        plans.append(
            {
                "employee_id": eid,
                "employee_name": name,
                "department": dept,
                "start_date": start_dt.isoformat(),
                "days_since_start": (as_of - start_dt).days,
                "total_tasks": total_tasks,
                "completed_tasks": completed,
                "completion_pct": round(completion_pct, 1),
                "missing_mandatory_gates": missing_mandatory,
                "overdue_tasks": overdue_tasks,
                "blocked_dependencies": blocked_tasks,
                "phase_breakdown": phase_counts,
                "onboarding_health": health,
                "stalled": stalled,
            }
        )

    return {
        "skill": "employee-onboarding-navigator",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "hires_tracked": len(plans),
            "stalled_or_at_risk_count": sum(1 for p in plans if p["stalled"]),
            "total_overdue_tasks": sum(len(p["overdue_tasks"]) for p in plans),
            "missing_day1_gate_hires": sum(1 for p in plans if p["missing_mandatory_gates"]),
        },
        "onboarding_plans": plans,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# 30/60/90 Employee Onboarding Readiness Tracker (As Of {result['as_of_date']})",
            "",
            f"- **Hires Tracked:** {s['hires_tracked']} | **Stalled/At-Risk:** {s['stalled_or_at_risk_count']} | "
            f"**Total Overdue Tasks:** {s['total_overdue_tasks']} | **Missing Day-1 Gates:** {s['missing_day1_gate_hires']}",
            "",
            "| Hire | Dept | Start Date | Completion | Overdue | Missing Gates | Health |",
            "| :--- | :--- | :--- | ---: | ---: | :--- | :--- |",
        ]
    )
    for p in result["onboarding_plans"]:
        miss = ", ".join(p["missing_mandatory_gates"]) or "None"
        lines.append(
            f"| `{p['employee_id']}` {p['employee_name']} | {p['department']} | {p['start_date']} | "
            f"{p['completion_pct']:.1f}% | {len(p['overdue_tasks'])} | {miss} | `{p['onboarding_health']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 30/60/90 onboarding plans and flag stalled gates.")
    parser.add_argument("--input", required=True, type=Path, help="Path to hires & onboarding tasks JSON")
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
