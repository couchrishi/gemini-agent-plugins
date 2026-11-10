#!/usr/bin/env python3
"""Scores Change Requests across blast radius, rollback plan, freeze windows, and CI history."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
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
        return {"changes": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="change-risk-cab-review", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"changes": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"changes": loaded}
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


def _as_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"true", "1", "yes", "y"}


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    _cfg, org_configured, banner = load_config(config)
    changes = data.get("changes") or data.get("records") or []
    freeze_windows = _as_list(data.get("freeze_windows"))
    metadata = _as_dict(data.get("metadata"))

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Change queue was truncated by ITSM connector.")

    parsed_freezes: list[tuple[str, dt.datetime, dt.datetime]] = []
    for fw in freeze_windows:
        fs = _parse_dt(fw.get("start_time"))
        fe = _parse_dt(fw.get("end_time"))
        if fs and fe:
            parsed_freezes.append((str(fw.get("name") or "Blackout Window"), fs, fe))

    scored: list[dict[str, Any]] = []
    high_or_emergency = 0
    freeze_collisions = 0

    for idx, chg in enumerate(changes):
        cid = str(chg.get("change_id") or f"CHG-{idx + 1}")
        ci = str(chg.get("cmdb_ci") or "unknown")
        tier = str(chg.get("service_tier") or "tier2").lower()
        users_impacted = int(_to_float(chg.get("estimated_users_impacted"), 0))
        has_rollback = _as_bool(chg.get("has_tested_rollback", False))
        reversible = _as_bool(chg.get("reversible_migration", True))
        staging_ok = _as_bool(chg.get("staging_validated", False))
        canary_ok = _as_bool(chg.get("canary_enabled", False))
        ci_fail_rate = _to_float(chg.get("ci_failure_rate_90d"), 0.0)

        # 1. Blast radius (max 30)
        blast_pts = 5
        if tier in {"tier0", "core_erp", "payments", "auth"} or users_impacted >= 1000:
            blast_pts = 30
        elif tier == "tier1" or users_impacted >= 200:
            blast_pts = 18

        # 2. Rollback plan & reversibility (max 25)
        rollback_pts = 0
        if not has_rollback:
            rollback_pts += 15
        if not reversible:
            rollback_pts += 10

        # 3. Freeze window collision (max 20)
        p_start = _parse_dt(chg.get("planned_start"))
        p_end = _parse_dt(chg.get("planned_end"))
        matched_freeze = None
        if p_start and p_end:
            for fname, fs, fe in parsed_freezes:
                if p_start < fe and p_end > fs:
                    matched_freeze = fname
                    break
        freeze_pts = 20 if matched_freeze else 0
        if matched_freeze:
            freeze_collisions += 1

        # 4. Historical CI failure rate (max 15)
        history_pts = 15 if ci_fail_rate > 0.10 else (8 if ci_fail_rate > 0.04 else 0)

        # 5. Test & canary coverage (max 10)
        test_pts = 0
        if not staging_ok:
            test_pts += 6
        if not canary_ok:
            test_pts += 4

        total_score = blast_pts + rollback_pts + freeze_pts + history_pts + test_pts
        if total_score >= 80:
            cab_tier = "Emergency / Executive VP + SRE Lead Sign-Off"
            high_or_emergency += 1
        elif total_score >= 60:
            cab_tier = "High / Weekly CAB Approval"
            high_or_emergency += 1
        elif total_score >= 30:
            cab_tier = "Normal / Peer + Manager Review"
        else:
            cab_tier = "Standard / Auto-Approve Eligible"

        scored.append(
            {
                "change_id": cid,
                "title": str(chg.get("title") or cid),
                "cmdb_ci": ci,
                "risk_score": total_score,
                "cab_tier": cab_tier,
                "freeze_collision": bool(matched_freeze),
                "freeze_window_name": matched_freeze,
                "has_tested_rollback": has_rollback,
                "factor_breakdown": {
                    "blast_radius": blast_pts,
                    "rollback_gap": rollback_pts,
                    "freeze_collision": freeze_pts,
                    "ci_history": history_pts,
                    "test_canary_gap": test_pts,
                },
            }
        )

    scored.sort(key=lambda r: r["risk_score"], reverse=True)

    return {
        "skill": "change-risk-cab-review",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "change_count": len(scored),
            "high_or_emergency_count": high_or_emergency,
            "freeze_collision_count": freeze_collisions,
            "max_risk_score": scored[0]["risk_score"] if scored else 0,
        },
        "scored_changes": scored,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(scored), existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# CAB Change Risk Review",
            "",
            f"- **Changes Scored:** {s['change_count']} | **High/Emergency:** {s['high_or_emergency_count']} | **Freeze Collisions:** {s['freeze_collision_count']}",
            "",
            "| Change ID | CI | Score | CAB Routing Tier | Freeze Collision | Tested Rollback |",
            "| :--- | :--- | ---: | :--- | :---: | :---: |",
        ]
    )
    for r in result["scored_changes"]:
        lines.append(
            f"| `{r['change_id']}` | {r['cmdb_ci']} | {r['risk_score']} | {r['cab_tier']} | "
            f"`{r['freeze_collision']}` | `{r['has_tested_rollback']}` |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score Change Requests for CAB review.")
    parser.add_argument("--input", required=True, type=Path, help="Path to changes JSON or CSV")
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
