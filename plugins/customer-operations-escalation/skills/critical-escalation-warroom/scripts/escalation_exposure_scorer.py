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
        return {"escalations": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="critical-escalation-warroom", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"escalations": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"escalations": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)

    war_thresh = _to_float(cfg.get("war_room_score_threshold"), 70.0)
    vip_arr = _to_float(cfg.get("vip_arr_threshold_usd"), 250000.0)
    ren_window = _to_int(cfg.get("imminent_renewal_days"), 90)

    items = _as_list(data.get("escalations"))
    scored: list[dict[str, Any]] = []

    for e in items:
        eid = str(e.get("escalation_id") or "ESC-1")
        acct = str(e.get("account_name") or "Unknown Account")
        arr = _to_float(e.get("arr_usd"), 0.0)
        ren_days = _to_opt_int(e.get("renewal_days"))
        sev1 = _to_int(e.get("open_sev1_tickets"), 0)
        sev2 = _to_int(e.get("open_sev2_tickets"), 0)
        sla_breaches = _to_int(e.get("sla_breached_count"), 0)
        outage_hrs = _to_float(e.get("outage_hours_30d"), 0.0)
        comp_threat = _to_bool(e.get("competitor_threat"), False)

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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(items)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score VIP escalations by churn exposure, ARR, and SLA breaches.")
    parser.add_argument("--input", required=True, type=Path, help="Path to escalations JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
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
