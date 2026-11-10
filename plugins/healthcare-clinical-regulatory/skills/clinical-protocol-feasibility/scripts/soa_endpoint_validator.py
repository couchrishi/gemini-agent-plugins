#!/usr/bin/env python3
"""Validates clinical trial Schedules of Assessments (SoA) against study endpoints and enrollment feasibility."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_enrollment_coverage_pct": 100.0,
    "max_screen_fail_warn_pct": 35.0,
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


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)

    min_cov = _to_float(cfg.get("min_enrollment_coverage_pct"), 100.0)
    max_sf_warn = _to_float(cfg.get("max_screen_fail_warn_pct"), 35.0)

    visits = _as_list(data.get("visits"))
    endpoints = _as_list(data.get("endpoints"))
    sites = _as_list(data.get("sites"))
    target_n = _to_int(data.get("target_sample_size"), 0)
    enroll_months = (_to_float(data.get("enrollment_window_months")) or 12.0)

    # Check endpoint procedures vs SoA visit schedule windows
    endpoint_gaps: list[dict[str, Any]] = []
    for ep in endpoints:
        eid = str(ep.get("endpoint_id") or "EP-1")
        etype = str(ep.get("endpoint_type") or "PRIMARY").upper()
        t_day = _to_int(ep.get("target_visit_day"), 0)
        req_procs = {str(p).lower().strip() for p in _as_list(ep.get("required_procedures"))}

        matching_visits = [
            v
            for v in visits
            if _to_int(v.get("window_start_day"), 0) <= t_day <= _to_int(v.get("window_end_day"), 0)
        ]
        if not matching_visits:
            endpoint_gaps.append(
                {
                    "endpoint_id": eid,
                    "endpoint_type": etype,
                    "target_visit_day": t_day,
                    "issue": "NO_SOA_VISIT_WINDOW_AT_ENDPOINT_DAY",
                    "missing_procedures": sorted(req_procs),
                }
            )
            continue

        covered_procs: set[str] = set()
        for mv in matching_visits:
            covered_procs.update(str(p).lower().strip() for p in _as_list(mv.get("procedures")))
        missing = sorted(req_procs - covered_procs)
        if missing:
            endpoint_gaps.append(
                {
                    "endpoint_id": eid,
                    "endpoint_type": etype,
                    "target_visit_day": t_day,
                    "issue": "MISSING_ENDPOINT_ASSESSMENT",
                    "missing_procedures": missing,
                }
            )

    # Site enrollment capacity accounting for IRB approval and screen failure rates
    projected_randomized = 0.0
    unapproved_sites = 0
    high_sf_sites: list[str] = []
    for s in sites:
        sid = str(s.get("site_id") or "SITE")
        irb_ok = bool(s.get("irb_approved", True))
        if not irb_ok:
            unapproved_sites += 1
        rate_mo = _to_float(s.get("projected_monthly_screened"), 0.0)
        sf_pct = _to_float(s.get("screen_fail_rate_pct"), 0.0)
        if sf_pct > max_sf_warn:
            high_sf_sites.append(f"{sid} ({sf_pct:.0f}% SF)")
        # Include approved sites cleanly; track active capacity
        if irb_ok:
            projected_randomized += rate_mo * (1.0 - sf_pct / 100.0) * enroll_months

    coverage_pct = (projected_randomized / target_n * 100.0) if target_n > 0 else 100.0
    enrollment_shortfall = max(0, target_n - round(projected_randomized))
    primary_conflict = any(g["endpoint_type"] == "PRIMARY" for g in endpoint_gaps)

    if primary_conflict:
        readiness = "PROTOCOL_AMENDMENT_REQUIRED_PRIMARY_GAP"
    elif endpoint_gaps or coverage_pct < min_cov:
        readiness = "FEASIBILITY_RISK_MITIGATION_REQUIRED"
    else:
        readiness = "PROTOCOL_FEASIBLE"

    return {
        "skill": "clinical-protocol-feasibility",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "protocol_id": str(data.get("protocol_id") or "PROTO-1"),
            "endpoints_checked": len(endpoints),
            "soa_endpoint_gap_count": len(endpoint_gaps),
            "target_sample_size": target_n,
            "projected_randomized_n": round(projected_randomized, 1),
            "enrollment_coverage_pct": round(coverage_pct, 1),
            "enrollment_shortfall": enrollment_shortfall,
            "unapproved_irb_sites": unapproved_sites,
            "high_screen_fail_sites": high_sf_sites,
            "feasibility_status": readiness,
        },
        "soa_endpoint_gaps": endpoint_gaps,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(sites)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Clinical Protocol SoA & Enrollment Feasibility — `{s['protocol_id']}`",
            "",
            f"- **Feasibility Status:** `{s['feasibility_status']}` | **SoA Endpoint Gaps:** {s['soa_endpoint_gap_count']}/{s['endpoints_checked']}",
            f"- **Projected Enrollment:** {s['projected_randomized_n']:.1f} / {s['target_sample_size']} "
            f"({s['enrollment_coverage_pct']:.1f}% coverage; Shortfall: {s['enrollment_shortfall']})",
        ]
    )
    if result["soa_endpoint_gaps"]:
        lines.extend(["", "## Schedule of Assessments vs Endpoint Conflicts"])
        for g in result["soa_endpoint_gaps"]:
            lines.append(
                f"- `{g['endpoint_id']}` ({g['endpoint_type']} Day {g['target_visit_day']}): `{g['issue']}` — missing {g['missing_procedures']}"
            )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate clinical SoA schedules vs endpoints and enrollment targets.")
    parser.add_argument("--input", required=True, type=Path, help="Path to clinical protocol JSON")
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
