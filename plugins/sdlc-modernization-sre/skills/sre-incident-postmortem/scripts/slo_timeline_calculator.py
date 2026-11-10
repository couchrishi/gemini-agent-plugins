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
) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"incidents": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="sre-incident-postmortem", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"incidents": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"incidents": loaded}
    return loaded if isinstance(loaded, dict) else {}


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

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    incidents = data.get("incidents") or ([data["incident"]] if "incident" in data else [data] if "detected_at" in data else [])
    action_items = list(_as_list(data.get("action_items")))
    slo_pct = _to_float(data.get("slo_target_pct"), cfg.get("default_slo_availability_pct", 99.9))
    window_days = max(1, _to_int(data.get("window_days"), 30))
    as_of = _parse_dt(data.get("as_of_time")) or dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)
    action_sla_days = _to_int(cfg.get("postmortem_action_sla_days"), 14)

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
        impact_factor = _to_float(inc.get("impact_weight"), 1.0)

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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(incidents)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calculate SRE postmortem TTD/TTM/TTR and SLO burn rate.")
    parser.add_argument("--input", required=True, type=Path, help="Path to postmortem timeline JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, sheet=args.sheet)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
