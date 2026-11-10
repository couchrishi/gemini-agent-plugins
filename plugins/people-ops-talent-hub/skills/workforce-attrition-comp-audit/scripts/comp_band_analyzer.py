#!/usr/bin/env python3
"""Audits effective-dated HRIS pay & attrition rows with CWK isolation, pay normalization, and privacy floors."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "compa_ratio_min": 0.85,
    "compa_ratio_max": 1.15,
    "compa_ratio_underpaid_alert": 0.8,
    "compa_ratio_overpaid_alert": 1.25,
    "min_privacy_cell_size": 5,
    "annual_working_hours": 2080,
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
        return {"workers": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="workforce-attrition-comp-audit", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"workers": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"workers": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return _safe_date(s)


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)

    fx_rates = {str(k).upper(): (_to_opt_float(v) if _to_opt_float(v) is not None else 1.0) for k, v in _as_dict(data.get("fx_rates"), {"USD": 1.0}).items()}
    annual_hours = _to_float(cfg.get("annual_working_hours"), 2080)
    underpaid_thresh = _to_float(cfg.get("compa_ratio_underpaid_alert"), 0.8)
    overpaid_thresh = _to_float(cfg.get("compa_ratio_overpaid_alert"), 1.25)
    min_cell = _to_int(cfg.get("min_privacy_cell_size"), 5)

    # Deduplicate effective-dated HRIS snapshots: pick latest effective_date <= as_of
    raw_workers = _as_list(data.get("workers"))
    deduped: dict[str, tuple[date, dict[str, Any]]] = {}
    future_rows_skipped = 0
    historical_rows_collapsed = 0

    for row in raw_workers:
        wid = str(row.get("worker_id") or "").strip()
        if not wid:
            continue
        eff_dt = _parse_date(row.get("effective_date")) or as_of
        if eff_dt > as_of:
            future_rows_skipped += 1
            continue
        if wid in deduped:
            historical_rows_collapsed += 1
            if eff_dt > deduped[wid][0]:
                deduped[wid] = (eff_dt, row)
        else:
            deduped[wid] = (eff_dt, row)

    band_midpoints = {
        str(b.get("job_level")).upper(): mid
        for b in _as_dict_list(data.get("comp_bands"))
        for mid in [_to_opt_float(b.get("midpoint_usd"))]
        if b.get("job_level") is not None and mid is not None
    }

    fte_records: list[dict[str, Any]] = []
    cwk_records: list[dict[str, Any]] = []
    dept_groups: dict[str, dict[str, Any]] = {}

    for _dt, w in sorted(deduped.values(), key=lambda pair: str(pair[1].get("worker_id"))):
        wid = str(w.get("worker_id"))
        wtype = str(w.get("worker_type") or "FTE").upper().strip()
        dept = str(w.get("department") or "General")
        level = str(w.get("job_level") or "L3").upper().strip()
        status = str(w.get("employment_status") or "ACTIVE").upper().strip()
        freq = str(w.get("pay_frequency") or "ANNUAL").upper().strip()
        curr = str(w.get("currency") or "USD").upper().strip()
        raw_pay = w.get("base_pay") if w.get("base_pay") is not None else w.get("base_pay_amount")
        base_pay = _to_float(raw_pay, 0.0)
        rate_usd = _to_float(fx_rates.get(curr), 1.0)

        if freq == "HOURLY":
            annual_local = base_pay * annual_hours
        elif freq == "MONTHLY":
            annual_local = base_pay * 12.0
        else:
            annual_local = base_pay
        annual_usd = annual_local * rate_usd

        if wtype != "FTE":
            cwk_records.append(
                {
                    "worker_id": wid,
                    "worker_type": wtype,
                    "department": dept,
                    "annualized_rate_usd": round(annual_usd, 2),
                }
            )
            continue

        midpoint = (_to_float(w.get("band_midpoint_usd")) or band_midpoints.get(level, 0.0))
        compa = (annual_usd / midpoint) if midpoint > 0 else None
        outlier = None
        if compa is not None:
            if compa < underpaid_thresh:
                outlier = "BELOW_BAND_COMPRESSION"
            elif compa > overpaid_thresh:
                outlier = "ABOVE_BAND_CEILING"

        rec = {
            "worker_id": wid,
            "department": dept,
            "job_level": level,
            "employment_status": status,
            "annualized_base_usd": round(annual_usd, 2),
            "band_midpoint_usd": round(midpoint, 2) if midpoint > 0 else None,
            "compa_ratio": round(compa, 3) if compa is not None else None,
            "comp_outlier_flag": outlier,
        }
        fte_records.append(rec)

        is_terminated = status.startswith("TERMINATED")
        g = dept_groups.setdefault(dept, {"fte_total": 0, "active": 0, "terminated": 0, "compa_ratios": []})
        g["fte_total"] += 1
        if is_terminated:
            g["terminated"] += 1
        else:
            g["active"] += 1
        if compa is not None and not is_terminated:
            g["compa_ratios"].append(compa)

    dept_rollups: list[dict[str, Any]] = []
    suppressed_count = 0
    for dept, g in sorted(dept_groups.items()):
        n = g["fte_total"]
        comp_n = len(g["compa_ratios"])
        suppressed = (n < min_cell) or (comp_n < min_cell)
        if suppressed:
            suppressed_count += 1
            avg_compa = None
        else:
            avg_compa = round(sum(g["compa_ratios"]) / comp_n, 3) if comp_n > 0 else None
        attrition_pct = None if (n < min_cell) else (round((g["terminated"] / n * 100.0), 2) if n > 0 else 0.0)

        dept_rollups.append(
            {
                "department": dept,
                "fte_headcount": n,
                "active_fte": g["active"],
                "suppressed_for_privacy": suppressed,
                "avg_compa_ratio": avg_compa,
                "attrition_pct": attrition_pct,
            }
        )

    active_ftes = [r for r in fte_records if not r["employment_status"].startswith("TERMINATED")]
    outliers = [r for r in active_ftes if r["comp_outlier_flag"]]
    all_compas = [r["compa_ratio"] for r in active_ftes if r["compa_ratio"] is not None]

    return {
        "skill": "workforce-attrition-comp-audit",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "raw_rows_processed": len(raw_workers),
            "historical_snapshots_collapsed": historical_rows_collapsed,
            "future_effective_rows_excluded": future_rows_skipped,
            "unique_fte_count": len(fte_records),
            "active_fte_count": len(active_ftes),
            "contingent_worker_isolated_count": len(cwk_records),
            "overall_active_avg_compa_ratio": round(sum(all_compas) / len(all_compas), 3) if all_compas else None,
            "comp_outlier_count": len(outliers),
            "privacy_suppressed_departments": suppressed_count,
        },
        "department_rollups": dept_rollups,
        "comp_outliers": outliers,
        "isolated_contingent_workers": cwk_records,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Workforce Compensation & Attrition Audit (As Of {result['as_of_date']})",
            "",
            f"- **Unique FTEs:** {s['unique_fte_count']} (Active: {s['active_fte_count']}) | "
            f"**CWK Contractors Isolated:** {s['contingent_worker_isolated_count']} | "
            f"**Historical Snapshots Collapsed:** {s['historical_snapshots_collapsed']}",
            f"- **Overall Active Avg Compa-Ratio:** {s['overall_active_avg_compa_ratio'] or 'N/A'} | "
            f"**Outliers:** {s['comp_outlier_count']} | **Privacy-Suppressed Depts (n < 5):** {s['privacy_suppressed_departments']}",
            "",
            "| Department | FTE Count | Avg Compa-Ratio | Attrition % | Privacy Suppressed |",
            "| :--- | ---: | ---: | ---: | :--- |",
        ]
    )
    for d in result["department_rollups"]:
        comp_s = f"{d['avg_compa_ratio']:.3f}" if d["avg_compa_ratio"] is not None else "REDACTED (n<5)"
        att_s = f"{d['attrition_pct']:.1f}%" if d["attrition_pct"] is not None else "REDACTED (n<5)"
        lines.append(
            f"| {d['department']} | {d['fte_headcount']} | {comp_s} | {att_s} | {'YES' if d['suppressed_for_privacy'] else 'No'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Workday compa-ratios and attrition with privacy/CWK guards.")
    parser.add_argument("--input", required=True, type=Path, help="Path to effective-dated workers JSON or CSV")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--as-of", type=str, help="Reference ISO date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, as_of_date=args.as_of, sheet=args.sheet)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
