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


def _to_float(val: Any, default: Any = 0.0) -> float:
    num = _to_opt_float(val)
    if num is not None:
        return num
    d = _to_opt_float(default)
    return d if d is not None else 0.0


def _to_opt_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        num = float(val)
        return None if (num != num or abs(num) == float("inf")) else num
    s = str(val).strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    for ch in (",", "$", "€", "£", "¥", "%"):
        s = s.replace(ch, "")
    s = s.strip()
    if not s:
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    if num != num or abs(num) == float("inf"):
        return None
    return -num if neg else num


def _to_int(val: Any, default: Any = 0) -> int:
    num = _to_opt_float(val)
    if num is None:
        num = _to_opt_float(default)
    if num is None:
        return 0
    try:
        return int(round(num))
    except (ValueError, TypeError, OverflowError):
        return 0


def _to_opt_int(val: Any) -> int | None:
    num = _to_opt_float(val)
    if num is None:
        return None
    try:
        return int(round(num))
    except (ValueError, TypeError, OverflowError):
        return None


def _safe_date(val: Any) -> Any:
    import datetime as _dt
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val.date()
    if isinstance(val, _dt.date):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _safe_datetime(val: Any) -> Any:
    import datetime as _dt
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val if val.tzinfo else val.replace(tzinfo=_dt.timezone.utc)
    if isinstance(val, _dt.date):
        return _dt.datetime(val.year, val.month, val.day, tzinfo=_dt.timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _strip_null_items(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_strip_null_items(x) for x in obj if x is not None]
    if isinstance(obj, dict):
        return {k: _strip_null_items(v) for k, v in obj.items()}
    return obj


def _as_list(val: Any, default: list[Any] | None = None) -> list[Any]:
    if isinstance(val, list):
        return [x for x in val if x is not None]
    if val is None:
        return list(default) if default is not None else []
    if isinstance(val, (tuple, set)):
        return [x for x in val if x is not None]
    return list(default) if default is not None else []


def _as_dict_list(val: Any) -> list[dict[str, Any]]:
    return [item for item in _as_list(val) if isinstance(item, dict)]


def _as_dict(val: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    return dict(default) if default is not None else {}


def _collect_truncation_warnings(
    data: dict[str, Any],
    *,
    count: int | None = None,
    existing: list[str] | None = None,
) -> list[str]:
    warnings = [str(w) for w in (existing or []) if w]
    meta = _as_dict(data.get("metadata"))
    trunc = bool(data.get("truncated")) or bool(meta.get("truncated"))
    if (
        data.get("done") is False
        or meta.get("done") is False
        or bool(data.get("next_page_token") or data.get("nextPageToken"))
        or bool(meta.get("next_page_token") or meta.get("nextPageToken"))
    ):
        trunc = True
    total_avail = data.get("total_available")
    if total_avail is None:
        total_avail = data.get("totalSize")
    if total_avail is None:
        total_avail = meta.get("total_available")
    if total_avail is None:
        total_avail = meta.get("totalSize")
    avail_int = _to_opt_int(total_avail)
    if avail_int is not None and count is not None and avail_int > count:
        trunc = True
    if trunc and not warnings:
        if avail_int is not None and count is not None:
            warnings.append(
                f"TRUNCATION_WARNING: Returned {count} of {avail_int} available records; totals and counts represent a partial dataset only."
            )
        else:
            warnings.append(
                "TRUNCATION_WARNING: Upstream feed reported truncated or paginated output; totals and counts represent a partial dataset only."
            )
    return warnings


def _load_enterprise_io() -> Any | None:
    try:
        from scripts import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    try:
        import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    eio_path = Path(__file__).resolve().parent / "enterprise_io.py"
    if eio_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("enterprise_io", eio_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


_ENTERPRISE_IO = _load_enterprise_io()


def _to_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"true", "yes", "y", "1", "on"}:
        return True
    if s in {"false", "no", "n", "0", "off", ""}:
        return False if s else default
    return bool(s)


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            _loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(_loaded, dict):
                cfg.update(_loaded)
    org_cfg = _to_bool(cfg.get("org_configured"), False)
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(
    input_arg: str | Path | dict[str, Any] | list[dict[str, Any]],
    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            return _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="meeting-to-execution-pack",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"segments": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="meeting-to-execution-pack", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() in {".txt", ".md"}:
        return {"raw_transcript": p.read_text(encoding="utf-8"), "meeting_title": p.stem}
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"segments": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"segments": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _normalize_task_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="meeting-to-execution-pack")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "meeting-to-execution-pack",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    segments = list(_as_list(data.get("segments")))
    raw_text = str(data.get("raw_transcript") or "")
    prior_open = list(_as_list(data.get("prior_open_commitments")))
    metadata = _as_dict(data.get("metadata"))

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
        prev_count = _to_int(p.get("carryover_count"), 1)
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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(actions), existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract structured execution pack from meeting transcript.")
    parser.add_argument("--input", required=True, type=Path, help="Path to transcript JSON/TXT/MD")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="meeting-to-execution-pack",
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        out = json.dumps(diag, indent=2, default=str)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0
    result = analyze(args.input, config=args.config, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
