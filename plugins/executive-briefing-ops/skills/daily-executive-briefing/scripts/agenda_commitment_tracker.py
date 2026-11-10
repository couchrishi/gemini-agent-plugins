#!/usr/bin/env python3
"""Reconciles executive calendar events, priority threads, and action trackers into prep blocks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_prep_buffer_minutes": 15,
    "overdue_action_escalation_days": 3,
}

INJECTION_RE = re.compile(r"(ignore\s+(all\s+)?previous\s+instructions|system\s+override)", re.IGNORECASE)


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


def _parse_dt(val: str) -> dt.datetime:
    norm = str(val).strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(norm)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    events = data.get("events", [])
    threads = data.get("priority_threads", [])
    commitments = data.get("commitments", [])
    metadata = data.get("metadata", {})
    ref_date_str = str(data.get("briefing_date") or "2026-11-10")
    ref_date = dt.date.fromisoformat(ref_date_str[:10])

    min_buffer = int(cfg.get("min_prep_buffer_minutes", 15))
    esc_days = int(cfg.get("overdue_action_escalation_days", 3))

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append(
            f"TRUNCATION_WARNING: Calendar/mail feed truncated ({metadata.get('fetched', len(events))} of {metadata.get('total_available', 'unknown')})."
        )

    parsed_events: list[dict[str, Any]] = []
    missing_prereads: list[dict[str, Any]] = []
    for idx, ev in enumerate(events):
        if str(ev.get("response_status", "accepted")).lower() == "declined":
            continue
        start = _parse_dt(ev["start_time"])
        end = _parse_dt(ev["end_time"])
        eid = str(ev.get("event_id") or f"EVT-{idx + 1}")
        title = str(ev.get("title") or eid)
        prereads = list(ev.get("preread_links", []))
        is_exec_or_external = bool(ev.get("is_external") or ev.get("requires_preread"))
        if is_exec_or_external and not prereads:
            missing_prereads.append({"event_id": eid, "title": title, "start_time": start.isoformat()})
        parsed_events.append(
            {
                "event_id": eid,
                "title": title,
                "start": start,
                "end": end,
                "duration_min": int((end - start).total_seconds() // 60),
                "is_external": bool(ev.get("is_external", False)),
                "preread_count": len(prereads),
                "attendee_count": int(ev.get("attendee_count", 1)),
            }
        )

    parsed_events.sort(key=lambda e: (e["start"], e["end"]))

    conflicts: list[dict[str, Any]] = []
    buffer_gaps: list[dict[str, Any]] = []
    total_booked_min = sum(e["duration_min"] for e in parsed_events)
    for i in range(len(parsed_events)):
        a = parsed_events[i]
        for j in range(i + 1, len(parsed_events)):
            b = parsed_events[j]
            if b["start"] < a["end"]:
                overlap_min = int((min(a["end"], b["end"]) - b["start"]).total_seconds() // 60)
                conflicts.append(
                    {
                        "event_a": a["event_id"],
                        "title_a": a["title"],
                        "event_b": b["event_id"],
                        "title_b": b["title"],
                        "overlap_minutes": overlap_min,
                    }
                )
        if i + 1 < len(parsed_events):
            nxt = parsed_events[i + 1]
            gap_min = int((nxt["start"] - a["end"]).total_seconds() // 60)
            if 0 <= gap_min < min_buffer and (a["is_external"] or nxt["is_external"]):
                buffer_gaps.append(
                    {
                        "prior_event": a["title"],
                        "next_event": nxt["title"],
                        "gap_minutes": gap_min,
                        "required_buffer_minutes": min_buffer,
                    }
                )

    overdue_items: list[dict[str, Any]] = []
    due_today_items: list[dict[str, Any]] = []
    for idx, c in enumerate(commitments):
        status = str(c.get("status") or "open").lower()
        if status in {"done", "closed", "completed"}:
            continue
        due_str = c.get("due_date")
        item = {
            "commitment_id": str(c.get("id") or f"ACT-{idx + 1}"),
            "owner": str(c.get("owner") or "UNASSIGNED"),
            "task": str(c.get("task") or ""),
            "due_date": due_str or "UNSPECIFIED",
        }
        if not due_str:
            item["days_overdue"] = None
            overdue_items.append(item)
            continue
        due = dt.date.fromisoformat(str(due_str)[:10])
        diff = (ref_date - due).days
        if diff > 0:
            item["days_overdue"] = diff
            item["escalated"] = diff >= esc_days
            overdue_items.append(item)
        elif diff == 0:
            due_today_items.append(item)

    overdue_items.sort(key=lambda x: (x["days_overdue"] is not None, x.get("days_overdue") or 0), reverse=True)

    flagged_threads: list[dict[str, Any]] = []
    urgent_threads: list[dict[str, Any]] = []
    for t in threads:
        body = str(t.get("snippet") or t.get("body") or "")
        if INJECTION_RE.search(body):
            flagged_threads.append({"thread_id": t.get("id"), "subject": t.get("subject"), "reason": "IPI_PATTERN"})
            continue
        if t.get("awaiting_exec_reply") or str(t.get("priority", "")).lower() in {"high", "urgent"}:
            urgent_threads.append(
                {
                    "thread_id": t.get("id"),
                    "subject": t.get("subject"),
                    "sender": t.get("sender"),
                    "hours_unanswered": t.get("hours_unanswered", 0),
                }
            )

    agenda_blocks = [
        {
            "event_id": e["event_id"],
            "title": e["title"],
            "start_time": e["start"].isoformat(),
            "end_time": e["end"].isoformat(),
            "duration_minutes": e["duration_min"],
            "is_external": e["is_external"],
            "preread_count": e["preread_count"],
        }
        for e in parsed_events
    ]

    return {
        "skill": "daily-executive-briefing",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "briefing_date": ref_date.isoformat(),
            "active_meeting_count": len(parsed_events),
            "total_booked_minutes": total_booked_min,
            "double_booking_count": len(conflicts),
            "insufficient_prep_buffer_count": len(buffer_gaps),
            "missing_preread_count": len(missing_prereads),
            "overdue_commitment_count": len(overdue_items),
            "due_today_count": len(due_today_items),
            "urgent_thread_count": len(urgent_threads),
            "injection_quarantine_count": len(flagged_threads),
        },
        "agenda_blocks": agenda_blocks,
        "double_bookings": conflicts,
        "buffer_gaps": buffer_gaps,
        "missing_prereads": missing_prereads,
        "overdue_commitments": overdue_items,
        "due_today_commitments": due_today_items,
        "urgent_threads": urgent_threads,
        "quarantined_threads": flagged_threads,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Daily Executive Briefing ({s['briefing_date']})",
            "",
            f"- **Meetings:** {s['active_meeting_count']} ({s['total_booked_minutes']} mins total)",
            f"- **Double-Bookings:** {s['double_booking_count']} | **Missing Pre-Reads:** {s['missing_preread_count']}",
            f"- **Overdue Commitments:** {s['overdue_commitment_count']} | **Urgent Threads:** {s['urgent_thread_count']}",
            "",
        ]
    )
    if result["double_bookings"]:
        lines.extend(["## Calendar Conflicts", ""])
        for c in result["double_bookings"]:
            lines.append(f"- `{c['title_a']}` overlaps `{c['title_b']}` by **{c['overlap_minutes']} min**")
    if result["overdue_commitments"]:
        lines.extend(["", "## Overdue Commitments", ""])
        for item in result["overdue_commitments"]:
            lines.append(
                f"- `{item['commitment_id']}` ({item['owner']}): {item['task']} (Due `{item['due_date']}`, Overdue `{item['days_overdue']}`d)"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build daily executive briefing pack.")
    parser.add_argument("--input", required=True, type=Path, help="Path to calendar/threads/commitments JSON")
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
