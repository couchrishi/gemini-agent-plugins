#!/usr/bin/env python3
"""Extracts owner-assigned commitments, decisions, blockers, and carryovers from meeting transcripts."""

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
    "overdue_action_escalation_days": 3,
}

ACTION_TAG_RE = re.compile(r"^(?:ACTION|TODO|FOLLOW[- ]UP)\s*:\s*(.+)$", re.IGNORECASE)
DECISION_TAG_RE = re.compile(r"^(?:DECISION|AGREED|APPROVED)\s*:\s*(.+)$", re.IGNORECASE)
BLOCKER_TAG_RE = re.compile(r"^(?:BLOCKER|RISK|ESCALATION)\s*:\s*(.+)$", re.IGNORECASE)
COMMITMENT_PHRASE_RE = re.compile(
    r"\b(will|shall|needs to|to send|to circulate|to finalize|owns?|take(?:s)? action)\b",
    re.IGNORECASE,
)
DUE_DATE_RE = re.compile(r"\bby\s+(\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2,8}\s+\d{1,2}|EOD|EOW|Friday|Monday)\b", re.IGNORECASE)
SPEAKER_LINE_RE = re.compile(r"^\[?(?:\d{1,2}:\d{2}(?::\d{2})?)\]?\s*([A-Z][A-Za-z .'-]{1,40})\s*:\s*(.+)$")


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
    p = Path(input_arg)
    if p.suffix.lower() in {".txt", ".md"}:
        return {"raw_transcript": p.read_text(encoding="utf-8"), "meeting_title": p.stem}
    return json.loads(p.read_text(encoding="utf-8"))


def _normalize_task_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    _cfg, org_configured, banner = load_config(config)
    segments = list(data.get("segments", []))
    raw_text = data.get("raw_transcript", "")
    prior_open = list(data.get("prior_open_commitments", []))
    metadata = data.get("metadata", {})

    if not segments and raw_text:
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = SPEAKER_LINE_RE.match(line)
            if m:
                segments.append({"speaker": m.group(1).strip(), "text": m.group(2).strip()})
            else:
                segments.append({"speaker": "UNATTRIBUTED", "text": line})

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Meeting transcript was truncated by connector.")
    unattributed_count = sum(1 for s in segments if str(s.get("speaker", "")).upper() in {"", "UNATTRIBUTED", "UNKNOWN"})
    if segments and unattributed_count == len(segments):
        warnings.append("ATTRIBUTION_WARNING: Transcript lacks speaker labels; owners require manual verification.")

    actions: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    unassigned_action_count = 0

    for idx, seg in enumerate(segments):
        speaker = str(seg.get("speaker") or "UNATTRIBUTED").strip()
        text = str(seg.get("text") or "").strip()
        if not text:
            continue

        d_match = DECISION_TAG_RE.match(text)
        if d_match:
            decisions.append(
                {
                    "decision_id": f"DEC-{len(decisions) + 1}",
                    "speaker": speaker,
                    "decision": d_match.group(1).strip(),
                    "segment_index": idx,
                }
            )
            continue

        b_match = BLOCKER_TAG_RE.match(text)
        if b_match:
            blockers.append(
                {
                    "blocker_id": f"BLK-{len(blockers) + 1}",
                    "owner": speaker,
                    "blocker": b_match.group(1).strip(),
                    "segment_index": idx,
                }
            )
            continue

        a_match = ACTION_TAG_RE.match(text)
        is_action = bool(a_match) or bool(COMMITMENT_PHRASE_RE.search(text))
        if is_action:
            body = a_match.group(1).strip() if a_match else text
            explicit_owner = seg.get("owner")
            if not explicit_owner:
                # Look for "Owner:" prefix inside ACTION line or default to speaker if named
                owner_m = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:to|will|-|:)\s+(.+)$", body)
                if owner_m:
                    explicit_owner = owner_m.group(1).strip()
                    body = owner_m.group(2).strip()
                elif speaker.upper() != "UNATTRIBUTED":
                    explicit_owner = speaker
                else:
                    explicit_owner = "UNASSIGNED"
            if explicit_owner == "UNASSIGNED":
                unassigned_action_count += 1
            due_m = DUE_DATE_RE.search(body)
            actions.append(
                {
                    "action_id": f"ACT-{len(actions) + 1}",
                    "owner": explicit_owner,
                    "task": body,
                    "due_hint": due_m.group(1) if due_m else str(seg.get("due_date") or "UNSPECIFIED"),
                    "segment_index": idx,
                }
            )

    # Reconcile against prior open commitments to detect repeat carryovers
    current_keys = {_normalize_task_key(a["task"]) for a in actions}
    carryovers: list[dict[str, Any]] = []
    for p in prior_open:
        if str(p.get("status", "open")).lower() in {"done", "closed"}:
            continue
        p_key = _normalize_task_key(str(p.get("task") or ""))
        repeated = any(p_key and (p_key in ck or ck in p_key) for ck in current_keys)
        prev_count = int(p.get("carryover_count", 1))
        carryovers.append(
            {
                "prior_id": str(p.get("id") or ""),
                "owner": str(p.get("owner") or "UNASSIGNED"),
                "task": str(p.get("task") or ""),
                "carryover_count": prev_count + 1 if repeated else prev_count,
                "re_raised_in_meeting": repeated,
            }
        )

    return {
        "skill": "meeting-to-execution-pack",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "meeting_title": data.get("meeting_title", "Executive Meeting"),
        "summary": {
            "segment_count": len(segments),
            "action_count": len(actions),
            "unassigned_action_count": unassigned_action_count,
            "decision_count": len(decisions),
            "blocker_count": len(blockers),
            "prior_carryover_count": len(carryovers),
        },
        "actions": actions,
        "decisions": decisions,
        "blockers": blockers,
        "carryovers": carryovers,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Execution Pack: {result['meeting_title']}",
            "",
            f"- **Actions:** {s['action_count']} (Unassigned: {s['unassigned_action_count']})",
            f"- **Decisions:** {s['decision_count']} | **Blockers:** {s['blocker_count']} | **Prior Carryovers:** {s['prior_carryover_count']}",
            "",
            "## Owner Commitments",
            "",
            "| ID | Owner | Task | Due Hint |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )
    for a in result["actions"]:
        lines.append(f"| `{a['action_id']}` | {a['owner']} | {a['task']} | `{a['due_hint']}` |")
    if result["decisions"]:
        lines.extend(["", "## Decision Log", ""])
        for d in result["decisions"]:
            lines.append(f"- `{d['decision_id']}` ({d['speaker']}): {d['decision']}")
    if result["blockers"]:
        lines.extend(["", "## Unresolved Blockers", ""])
        for b in result["blockers"]:
            lines.append(f"- `{b['blocker_id']}` ({b['owner']}): {b['blocker']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract structured execution pack from meeting transcript.")
    parser.add_argument("--input", required=True, type=Path, help="Path to transcript JSON/TXT/MD")
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
