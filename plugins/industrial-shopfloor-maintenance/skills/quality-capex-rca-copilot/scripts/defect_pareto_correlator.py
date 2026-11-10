#!/usr/bin/env python3
"""Computes manufacturing defect 80/20 Paretos, isolates shift/lot spikes, and checks CapEx payback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "max_capex_payback_years": 2.0,
    "lot_spike_multiplier": 2.0,
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
    max_payback = _to_float(cfg.get("max_capex_payback_years"), 2.0)
    spike_mult = _to_float(cfg.get("lot_spike_multiplier"), 2.0)

    events = _as_list(data.get("events"))
    by_defect: dict[str, dict[str, Any]] = {}
    by_lot: dict[str, float] = {}
    total_scrap_cost = 0.0

    for ev in events:
        dtype = str(ev.get("defect_type") or "UNKNOWN_DEFECT")
        lot = str(ev.get("supplier_lot") or "UNKNOWN_LOT")
        cost = _to_float(ev.get("scrap_cost_usd"), 0.0)
        units = _to_int(ev.get("scrap_units"), 0)
        downtime = _to_float(ev.get("downtime_mins"), 0.0)
        total_scrap_cost += cost

        d = by_defect.setdefault(dtype, {"defect_type": dtype, "event_count": 0, "scrap_units": 0, "scrap_cost_usd": 0.0, "downtime_mins": 0.0})
        d["event_count"] += 1
        d["scrap_units"] += units
        d["scrap_cost_usd"] += cost
        d["downtime_mins"] += downtime
        by_lot[lot] = by_lot.get(lot, 0.0) + cost

    pareto = sorted(by_defect.values(), key=lambda x: -x["scrap_cost_usd"])
    running_pct = 0.0
    for row in pareto:
        share = (row["scrap_cost_usd"] / total_scrap_cost * 100.0) if total_scrap_cost > 0 else 0.0
        running_pct += share
        row["scrap_cost_usd"] = round(row["scrap_cost_usd"], 2)
        row["cost_share_pct"] = round(share, 1)
        row["cumulative_pct"] = round(running_pct, 1)
        row["vital_80_driver"] = (running_pct - share) < 80.0

    avg_lot_cost = (total_scrap_cost / len(by_lot)) if by_lot else 0.0
    anomalous_lots = [
        {"supplier_lot": lot, "scrap_cost_usd": round(c, 2), "ratio_to_avg": round(c / avg_lot_cost, 2)}
        for lot, c in sorted(by_lot.items(), key=lambda kv: -kv[1])
        if avg_lot_cost > 0 and (c / avg_lot_cost) >= spike_mult
    ]

    capex_evals: list[dict[str, Any]] = []
    for prop in _as_list(data.get("capex_proposals")):
        capex_usd = _to_float(prop.get("capex_cost_usd"), 0.0)
        ann_sav = _to_float(prop.get("annual_scrap_savings_usd"), 0.0)
        payback = (capex_usd / ann_sav) if ann_sav > 0 else 99.0
        capex_evals.append(
            {
                "proposal_id": str(prop.get("proposal_id") or "CAPEX-1"),
                "title": str(prop.get("title") or "Engineering Fix"),
                "capex_cost_usd": round(capex_usd, 2),
                "annual_savings_usd": round(ann_sav, 2),
                "payback_years": round(payback, 2),
                "meets_payback_hurdle": payback <= max_payback,
            }
        )

    return {
        "skill": "quality-capex-rca-copilot",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "events_analyzed": len(events),
            "total_scrap_cost_usd": round(total_scrap_cost, 2),
            "vital_80_defect_count": sum(1 for r in pareto if r["vital_80_driver"]),
            "anomalous_lot_count": len(anomalous_lots),
            "approved_capex_count": sum(1 for c in capex_evals if c["meets_payback_hurdle"]),
        },
        "defect_pareto": pareto,
        "anomalous_supplier_lots": anomalous_lots,
        "capex_evaluations": capex_evals,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Quality Defect 80/20 Pareto & CapEx Payback Report",
            "",
            f"- **Scrap Events:** {s['events_analyzed']} | **Total Scrap Cost:** ${s['total_scrap_cost_usd']:,.2f} | "
            f"**Vital 80% Drivers:** {s['vital_80_defect_count']} | **Anomalous Supplier Lots:** {s['anomalous_lot_count']}",
            "",
            "| Defect Type | Events | Units | Scrap Cost | Share % | Cum % | Vital 80% |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for d in result["defect_pareto"]:
        lines.append(
            f"| `{d['defect_type']}` | {d['event_count']} | {d['scrap_units']} | ${d['scrap_cost_usd']:,.2f} | "
            f"{d['cost_share_pct']:.1f}% | {d['cumulative_pct']:.1f}% | {'YES' if d['vital_80_driver'] else 'No'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate manufacturing defect Paretos and evaluate CapEx payback.")
    parser.add_argument("--input", required=True, type=Path, help="Path to quality defects and CapEx JSON")
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
