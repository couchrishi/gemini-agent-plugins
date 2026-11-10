#!/usr/bin/env python3
"""Aggregates account commercial milestones, escalations, touchpoints, and renewal countdowns."""

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
    "renewal_critical_window_days": 90,
    "touchpoint_stale_days": 30,
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


def load_payload(input_arg: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"accounts": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"accounts": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, (dict, list)):
        return {}
    if isinstance(data, list):
        return {"accounts": data}
    return data


def _parse_date(val: Any) -> dt.date | None:
    if not val:
        return None
    try:
        return dt.date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)
    accounts = data.get("accounts") or ([data["account"]] if "account" in data else _as_list(data.get("records")))
    as_of = _parse_date(data.get("as_of_date")) or dt.date(2026, 11, 10)
    metadata = _as_dict(data.get("metadata"))
    renewal_window = _to_int(cfg.get("renewal_critical_window_days"), 90)
    touch_stale_days = _to_int(cfg.get("touchpoint_stale_days"), 30)

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Account or escalation dataset truncated.")
    if metadata.get("missing_feeds"):
        warnings.append(
            f"UNVERIFIED_INSUFFICIENT_SCOPE: Missing feeds ({', '.join(str(x) for x in _as_list(metadata.get('missing_feeds')))}); health signals incomplete."
        )

    dossiers: list[dict[str, Any]] = []
    red_count = 0
    amber_count = 0
    total_arr_at_risk = 0.0

    for idx, acc in enumerate(accounts):
        aid = str(acc.get("account_id") or f"ACC-{idx + 1}")
        name = str(acc.get("account_name") or aid)
        arr = _to_float(acc.get("arr_usd"), 0.0)
        renewal_dt = _parse_date(acc.get("renewal_date"))
        last_touch_dt = _parse_date(acc.get("last_exec_touchpoint"))
        open_p1 = _to_int(acc.get("open_p1_count"), 0)
        open_p2 = _to_int(acc.get("open_p2_count"), 0)
        nps = _to_opt_float(acc.get("nps_score"))
        open_milestones = list(_as_list(acc.get("open_milestones")))

        days_to_renewal = (renewal_dt - as_of).days if renewal_dt else None
        days_since_touch = (as_of - last_touch_dt).days if last_touch_dt else None

        score = 100
        drivers: list[str] = []
        if open_p1 > 0:
            penalty = min(40, open_p1 * 22)
            score -= penalty
            drivers.append(f"{open_p1} open P1 escalation(s)")
        if open_p2 > 0:
            penalty = min(20, open_p2 * 8)
            score -= penalty
            drivers.append(f"{open_p2} open P2 ticket(s)")
        if days_since_touch is None or days_since_touch > touch_stale_days:
            score -= 15
            drivers.append(
                "Missing exec touchpoint date"
                if days_since_touch is None
                else f"Exec touchpoint stale ({days_since_touch}d > {touch_stale_days}d)"
            )
        if nps is not None and nps < 20:
            score -= 15
            drivers.append(f"Low NPS ({nps})")
        if days_to_renewal is not None and days_to_renewal <= renewal_window and score < 85:
            score -= 10
            drivers.append(f"Renewal within {days_to_renewal}d while elevated risk")
        overdue_ms = [m for m in open_milestones if str(m.get("status", "")).lower() == "overdue"]
        if overdue_ms:
            score -= min(15, len(overdue_ms) * 7)
            drivers.append(f"{len(overdue_ms)} overdue milestone(s)")

        score = max(0, score)
        if score < 60 or open_p1 >= 2:
            rag = "RED"
            red_count += 1
            total_arr_at_risk += arr
        elif score < 80 or open_p1 == 1:
            rag = "AMBER"
            amber_count += 1
            total_arr_at_risk += arr
        else:
            rag = "GREEN"

        dossiers.append(
            {
                "account_id": aid,
                "account_name": name,
                "arr_usd": round(arr, 2),
                "renewal_date": renewal_dt.isoformat() if renewal_dt else "UNKNOWN",
                "days_to_renewal": days_to_renewal,
                "days_since_exec_touchpoint": days_since_touch,
                "open_p1_count": open_p1,
                "open_p2_count": open_p2,
                "health_score": score,
                "rag_status": rag,
                "risk_drivers": drivers,
            }
        )

    dossiers.sort(key=lambda d: (d["health_score"], -d["arr_usd"]))

    return {
        "skill": "stakeholder-account-prep",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "account_count": len(dossiers),
            "red_account_count": red_count,
            "amber_account_count": amber_count,
            "green_account_count": len(dossiers) - red_count - amber_count,
            "arr_at_risk_usd": round(total_arr_at_risk, 2),
        },
        "dossiers": dossiers,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(accounts), existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Stakeholder Account Prep Dossier",
            "",
            f"- **Accounts Analyzed:** {s['account_count']} (RED: {s['red_account_count']}, AMBER: {s['amber_account_count']}, GREEN: {s['green_account_count']})",
            f"- **ARR at Risk (RED+AMBER):** ${s['arr_at_risk_usd']:,.2f}",
            "",
            "| Account | ARR (USD) | Renewal (d) | P1/P2 | Health | Status | Key Drivers |",
            "| :--- | ---: | ---: | :---: | ---: | :---: | :--- |",
        ]
    )
    for d in result["dossiers"]:
        drivers = "; ".join(d["risk_drivers"]) or "Healthy"
        lines.append(
            f"| {d['account_name']} | ${d['arr_usd']:,.0f} | {d['days_to_renewal']} | "
            f"{d['open_p1_count']}/{d['open_p2_count']} | {d['health_score']} | `{d['rag_status']}` | {drivers} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesize executive stakeholder account health dossiers.")
    parser.add_argument("--input", required=True, type=Path, help="Path to account signals JSON or CSV")
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
