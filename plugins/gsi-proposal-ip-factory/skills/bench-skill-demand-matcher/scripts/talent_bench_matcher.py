#!/usr/bin/env python3
"""Matches open consulting project demands against bench talent skills, availability, and target margin."""

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
    "min_skill_overlap_pct": 60.0,
    "max_start_delay_days": 14,
}


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
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    _loaded = json.loads(Path(input_arg).read_text(encoding="utf-8"))
    return _loaded if isinstance(_loaded, dict) else {}


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return _safe_date(s)


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)

    min_overlap = _to_float(cfg.get("min_skill_overlap_pct"), 60.0)
    max_delay = _to_int(cfg.get("max_start_delay_days"), 14)

    demands = _as_list(data.get("demands"))
    consultants = _as_list(data.get("consultants"))

    role_matches: list[dict[str, Any]] = []
    unfilled_count = 0

    for d in demands:
        rid = str(d.get("role_id") or "ROLE-1")
        proj = str(d.get("project_name") or "Engagement")
        req_skills = {str(s).lower().strip() for s in _as_list(d.get("required_skills"))}
        pref_loc = str(d.get("location_pref") or "").lower().strip()
        need_dt = _parse_date(d.get("start_date"))
        target_bill = _to_float(d.get("target_bill_rate_hourly"), 0.0)

        candidates: list[dict[str, Any]] = []
        for c in consultants:
            c_skills = {str(s).lower().strip() for s in _as_list(c.get("skills"))}
            overlap = (len(req_skills & c_skills) / len(req_skills) * 100.0) if req_skills else 100.0
            avail_dt = _parse_date(c.get("available_from"))
            delay_days = max(0, (avail_dt - need_dt).days) if (avail_dt and need_dt) else 0
            c_loc = str(c.get("location") or "").lower().strip()
            loc_bonus = 10.0 if (not pref_loc or pref_loc == c_loc or pref_loc == "any") else 0.0
            cost_hr = _to_float(c.get("cost_rate_hourly"), 0.0)
            margin_pct = ((target_bill - cost_hr) / target_bill * 100.0) if target_bill > 0 else 0.0

            if overlap < min_overlap or delay_days > max_delay:
                continue

            composite = round(overlap * 0.7 + margin_pct * 0.2 + loc_bonus - delay_days, 2)
            candidates.append(
                {
                    "consultant_id": str(c.get("consultant_id")),
                    "name": str(c.get("name") or c.get("consultant_id")),
                    "grade": str(c.get("grade") or ""),
                    "location": str(c.get("location") or ""),
                    "skill_match_pct": round(overlap, 1),
                    "start_delay_days": delay_days,
                    "estimated_margin_pct": round(margin_pct, 1),
                    "composite_fit_score": composite,
                }
            )

        candidates.sort(key=lambda x: -x["composite_fit_score"])
        status = "MATCHED_INTERNAL_BENCH" if candidates else "EXTERNAL_SUBCONTRACT_REQUIRED"
        if not candidates:
            unfilled_count += 1

        role_matches.append(
            {
                "role_id": rid,
                "project_name": proj,
                "required_skills": sorted(req_skills),
                "fill_status": status,
                "shortlisted_candidates": candidates[:3],
            }
        )

    return {
        "skill": "bench-skill-demand-matcher",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "demands_evaluated": len(demands),
            "consultants_screened": len(consultants),
            "filled_internally_count": len(demands) - unfilled_count,
            "external_subcontract_required_count": unfilled_count,
        },
        "role_matches": role_matches,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(role_matches)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Bench Talent & Project Demand Match Report",
            "",
            f"- **Open Demands:** {s['demands_evaluated']} | **Internal Match:** {s['filled_internally_count']} | "
            f"**Subcontract Gaps:** {s['external_subcontract_required_count']}",
            "",
            "| Role ID | Project | Status | Top Candidate | Match % | Margin % |",
            "| :--- | :--- | :--- | :--- | ---: | ---: |",
        ]
    )
    for rm in result["role_matches"]:
        top = rm["shortlisted_candidates"][0] if rm["shortlisted_candidates"] else None
        cand_name = f"{top['name']} (`{top['consultant_id']}`)" if top else "None"
        m_pct = f"{top['skill_match_pct']:.1f}%" if top else "—"
        gm_pct = f"{top['estimated_margin_pct']:.1f}%" if top else "—"
        lines.append(f"| `{rm['role_id']}` | {rm['project_name']} | `{rm['fill_status']}` | {cand_name} | {m_pct} | {gm_pct} |")
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match consulting demand seats to bench consultants.")
    parser.add_argument("--input", required=True, type=Path, help="Path to demands and bench JSON")
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
