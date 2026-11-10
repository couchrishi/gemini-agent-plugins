#!/usr/bin/env python3
"""Computes P&L Actual vs Budget/Forecast variance bridges with hierarchy tie-outs and FX isolation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "default_currency": "USD",
    "materiality_amount_threshold": 25000.0,
    "materiality_pct_threshold": 10.0,
    "hierarchy_tolerance_amount": 1.0,
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
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8", newline="") as fh:
            return {"lines": list(csv.DictReader(fh))}
    _loaded = json.loads(p.read_text(encoding="utf-8"))
    return _loaded if isinstance(_loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)

    mat_amt = _to_float(cfg.get("materiality_amount_threshold"), 25000.0)
    mat_pct = _to_float(cfg.get("materiality_pct_threshold"), 10.0)
    hier_tol = _to_float(cfg.get("hierarchy_tolerance_amount"), 1.0)

    raw_lines = _as_list(data.get("lines"))
    summary_rows: dict[str, dict[str, Any]] = {}
    leaf_rows: list[dict[str, Any]] = []
    leaf_sum_by_parent: dict[str, dict[str, float]] = {}

    for row in raw_lines:
        rtype = str(row.get("row_type") or "leaf").lower().strip()
        acct_id = str(row.get("account_id") or "ACCT-1")
        parent_id = str(row.get("parent_account") or "").strip()
        category = str(row.get("category") or "opex").lower().strip()
        fx_act = (_to_float(row.get("fx_rate_actual")) or 1.0)
        fx_bud = (_to_float(row.get("fx_rate_budget")) or fx_act)
        act_local = _to_float(row.get("actual_local"), row.get("actual_usd", 0.0))
        bud_local = _to_float(row.get("budget_local"), row.get("budget_usd", 0.0))
        fcst_local = _to_float(row.get("forecast_local"), bud_local)

        act_usd = act_local * fx_act
        bud_usd = bud_local * fx_bud
        fcst_usd = fcst_local * fx_act

        if rtype == "summary":
            summary_rows[acct_id] = {
                "account_id": acct_id,
                "account_name": str(row.get("account_name") or acct_id),
                "reported_actual_usd": act_usd,
                "reported_budget_usd": bud_usd,
            }
            continue

        # Leaf row calculations (avoid double-counting summary rows)
        total_var_usd = act_usd - bud_usd
        constant_fx_usd = (act_local - bud_local) * fx_bud
        fx_impact_usd = act_local * (fx_act - fx_bud)
        fcst_var_usd = act_usd - fcst_usd

        # Favorability sign depends on revenue vs cost category
        if category == "revenue":
            favorable = total_var_usd >= 0
            ebitda_impact_usd = total_var_usd
        else:
            favorable = total_var_usd <= 0
            ebitda_impact_usd = -total_var_usd

        var_pct = (total_var_usd / abs(bud_usd) * 100.0) if abs(bud_usd) > 1e-6 else 0.0
        is_material = abs(total_var_usd) >= mat_amt or (abs(var_pct) >= mat_pct and abs(total_var_usd) >= 5000.0)

        leaf_entry = {
            "account_id": acct_id,
            "account_name": str(row.get("account_name") or acct_id),
            "parent_account": parent_id or None,
            "category": category,
            "actual_usd": round(act_usd, 2),
            "budget_usd": round(bud_usd, 2),
            "forecast_usd": round(fcst_usd, 2),
            "variance_vs_budget_usd": round(total_var_usd, 2),
            "variance_vs_budget_pct": round(var_pct, 2),
            "constant_fx_variance_usd": round(constant_fx_usd, 2),
            "fx_translation_impact_usd": round(fx_impact_usd, 2),
            "variance_vs_forecast_usd": round(fcst_var_usd, 2),
            "ebitda_impact_usd": round(ebitda_impact_usd, 2),
            "direction": "FAVORABLE" if favorable else "UNFAVORABLE",
            "material_breach": is_material,
        }
        leaf_rows.append(leaf_entry)
        if parent_id:
            bucket = leaf_sum_by_parent.setdefault(parent_id, {"actual": 0.0, "budget": 0.0})
            bucket["actual"] += act_usd
            bucket["budget"] += bud_usd

    hierarchy_breaks: list[dict[str, Any]] = []
    for pid, srow in summary_rows.items():
        leaf_agg = _as_dict(leaf_sum_by_parent.get(pid), {"actual": 0.0, "budget": 0.0})
        delta_act = abs(srow["reported_actual_usd"] - leaf_agg["actual"])
        delta_bud = abs(srow["reported_budget_usd"] - leaf_agg["budget"])
        if delta_act > hier_tol or delta_bud > hier_tol:
            hierarchy_breaks.append(
                {
                    "summary_account_id": pid,
                    "summary_name": srow["account_name"],
                    "reported_actual_usd": round(srow["reported_actual_usd"], 2),
                    "leaf_sum_actual_usd": round(leaf_agg["actual"], 2),
                    "actual_tieout_delta_usd": round(delta_act, 2),
                    "budget_tieout_delta_usd": round(delta_bud, 2),
                }
            )

    rev_act = sum(r["actual_usd"] for r in leaf_rows if r["category"] == "revenue")
    rev_bud = sum(r["budget_usd"] for r in leaf_rows if r["category"] == "revenue")
    cost_act = sum(r["actual_usd"] for r in leaf_rows if r["category"] != "revenue")
    cost_bud = sum(r["budget_usd"] for r in leaf_rows if r["category"] != "revenue")
    ebitda_act = rev_act - cost_act
    ebitda_bud = rev_bud - cost_bud

    material_drivers = sorted(
        [r for r in leaf_rows if r["material_breach"]],
        key=lambda r: -abs(r["ebitda_impact_usd"]),
    )

    return {
        "skill": "pnl-budget-variance-bridge",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "leaf_line_count": len(leaf_rows),
            "summary_rows_excluded_from_rollup": len(summary_rows),
            "hierarchy_break_count": len(hierarchy_breaks),
            "actual_revenue_usd": round(rev_act, 2),
            "budget_revenue_usd": round(rev_bud, 2),
            "actual_cost_usd": round(cost_act, 2),
            "budget_cost_usd": round(cost_bud, 2),
            "actual_ebitda_usd": round(ebitda_act, 2),
            "budget_ebitda_usd": round(ebitda_bud, 2),
            "net_ebitda_variance_usd": round(ebitda_act - ebitda_bud, 2),
            "material_variance_count": len(material_drivers),
        },
        "hierarchy_tieout_breaks": hierarchy_breaks,
        "variance_lines": leaf_rows,
        "top_material_drivers": material_drivers,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# P&L Budget vs. Actual Constant-Currency Variance Bridge",
            "",
            f"- **Actual Revenue:** ${s['actual_revenue_usd']:,.2f} vs **Budget:** ${s['budget_revenue_usd']:,.2f}",
            f"- **Actual EBITDA:** ${s['actual_ebitda_usd']:,.2f} vs **Budget EBITDA:** ${s['budget_ebitda_usd']:,.2f} "
            f"(**Bridge:** ${s['net_ebitda_variance_usd']:+,.2f})",
            f"- **Leaf Accounts:** {s['leaf_line_count']} | **Parent Summary Rows Isolated:** {s['summary_rows_excluded_from_rollup']} | "
            f"**Hierarchy Tie-Out Breaks:** {s['hierarchy_break_count']}",
            "",
            "| Account | Category | Actual | Budget | Var ($) | Const-FX ($) | FX ($) | Direction | Material |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |",
        ]
    )
    for r in result["variance_lines"]:
        lines.append(
            f"| `{r['account_id']}` {r['account_name']} | {r['category']} | ${r['actual_usd']:,.2f} | "
            f"${r['budget_usd']:,.2f} | ${r['variance_vs_budget_usd']:+,.2f} | "
            f"${r['constant_fx_variance_usd']:+,.2f} | ${r['fx_translation_impact_usd']:+,.2f} | "
            f"{r['direction']} | {'YES' if r['material_breach'] else 'No'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute P&L variance bridge with hierarchy tie-out and FX split.")
    parser.add_argument("--input", required=True, type=Path, help="Path to GL variance JSON or CSV")
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
