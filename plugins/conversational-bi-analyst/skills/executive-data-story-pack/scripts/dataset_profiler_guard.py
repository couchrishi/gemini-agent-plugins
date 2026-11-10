#!/usr/bin/env python3
"""Profiles tabular datasets in RAM for completeness, quantiles, outliers, and A2UI Canvas payloads."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "max_null_rate_warn_pct": 15.0,
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
        return {"rows": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"rows": list(csv.DictReader(fh)), "title": p.stem}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, (dict, list)):
        return {}
    if isinstance(data, list):
        return {"rows": data}
    return data


def _try_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    s = str(val).strip().replace(",", "").replace("$", "")
    if not s or s.lower() in {"null", "none", "na", "n/a", "#n/a", "#ref!"}:
        return None
    try:
        num = _to_float(s)
        return num if math.isfinite(num) else None
    except ValueError:
        return None


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)
    rows = data.get("rows") or data.get("records") or []
    metadata = _as_dict(data.get("metadata"))
    null_warn_pct = _to_float(cfg.get("max_null_rate_warn_pct"), 15.0)

    total_available = _to_int(metadata.get("total_available"), len(rows))
    row_ceiling = _to_opt_int(metadata.get("row_limit_ceiling"))
    truncated = bool(
        metadata.get("truncated")
        or total_available > len(rows)
        or (row_ceiling is not None and len(rows) >= int(row_ceiling))
    )
    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"TRUNCATION_WARNING: Dataset contains {len(rows)} rows (total_available={total_available}); do not extrapolate totals."
        )

    columns: list[str] = []
    seen_cols: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_cols:
                seen_cols.add(k)
                columns.append(k)

    profiles: list[dict[str, Any]] = []
    high_null_columns: list[str] = []
    formula_error_cells = 0

    for col in columns:
        vals = [r.get(col) for r in rows]
        nulls = 0
        non_null_strs: list[str] = []
        nums: list[float] = []
        for v in vals:
            s = "" if v is None else str(v).strip()
            if s.upper() in {"#N/A", "#REF!", "#VALUE!", "#DIV/0!", "###"}:
                formula_error_cells += 1
            if v is None or s == "" or s.lower() in {"null", "none", "na", "n/a"}:
                nulls += 1
                continue
            non_null_strs.append(s)
            f = _try_float(v)
            if f is not None:
                nums.append(f)

        row_cnt = len(rows)
        null_pct = round((nulls / row_cnt) * 100.0, 2) if row_cnt else 0.0
        if null_pct > null_warn_pct:
            high_null_columns.append(col)

        is_numeric = bool(nums) and len(nums) == len(non_null_strs)
        col_prof: dict[str, Any] = {
            "column": col,
            "inferred_type": "numeric" if is_numeric else "categorical",
            "non_null_count": len(non_null_strs),
            "null_count": nulls,
            "null_rate_pct": null_pct,
            "distinct_count": len(set(non_null_strs)),
        }
        if is_numeric:
            snums = sorted(nums)
            q25 = _quantile(snums, 0.25)
            q50 = _quantile(snums, 0.50)
            q75 = _quantile(snums, 0.75)
            iqr = q75 - q25
            lo_fence = q25 - 1.5 * iqr
            hi_fence = q75 + 1.5 * iqr
            outliers = [x for x in snums if x < lo_fence or x > hi_fence]
            col_prof.update(
                {
                    "sum": round(sum(snums), 4),
                    "mean": round(sum(snums) / len(snums), 4),
                    "min": round(snums[0], 4),
                    "p25": round(q25, 4),
                    "median": round(q50, 4),
                    "p75": round(q75, 4),
                    "p95": round(_quantile(snums, 0.95), 4),
                    "max": round(snums[-1], 4),
                    "iqr_outlier_count": len(outliers),
                }
            )
        profiles.append(col_prof)

    # Emit compact verified A2UI payload for top categorical + primary numeric column
    cat_cols = [p["column"] for p in profiles if p["inferred_type"] == "categorical"]
    num_cols = [p["column"] for p in profiles if p["inferred_type"] == "numeric"]
    a2ui_chart = None
    if cat_cols and num_cols:
        dim = cat_cols[0]
        metric = num_cols[0]
        agg: dict[str, float] = {}
        for r in rows:
            key = str(r.get(dim) or "UNSPECIFIED")
            val = _try_float(r.get(metric))
            if val is not None:
                agg[key] = agg.get(key, 0.0) + val
        top_bars = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:10]
        a2ui_chart = {
            "component": "bar_chart",
            "title": f"{metric} by {dim}",
            "dimension": dim,
            "metric": metric,
            "series": [{"label": k, "value": round(v, 2)} for k, v in top_bars],
        }

    return {
        "skill": "executive-data-story-pack",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "title": data.get("title", "Dataset Profile"),
            "row_count": len(rows),
            "column_count": len(columns),
            "truncated": truncated,
            "high_null_column_count": len(high_null_columns),
            "high_null_columns": high_null_columns,
            "formula_error_cells": formula_error_cells,
        },
        "column_profiles": profiles,
        "a2ui_chart_payload": a2ui_chart,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(rows), existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Executive Data Story Profile: {s['title']}",
            "",
            f"- **Rows:** {s['row_count']} | **Columns:** {s['column_count']} | **Truncated:** `{s['truncated']}`",
            f"- **High-Null Columns:** {s['high_null_column_count']} | **Formula Error Cells:** {s['formula_error_cells']}",
            "",
            "| Column | Type | Null % | Distinct | Mean / Median | P95 | Outliers |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for c in result["column_profiles"]:
        mm = f"{c.get('mean', '—')} / {c.get('median', '—')}" if c["inferred_type"] == "numeric" else "—"
        p95 = f"{c.get('p95', '—')}"
        out_c = f"{c.get('iqr_outlier_count', '—')}"
        lines.append(
            f"| `{c['column']}` | {c['inferred_type']} | {c['null_rate_pct']:.1f}% | {c['distinct_count']} | {mm} | {p95} | {out_c} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile tabular dataset in RAM and generate A2UI payload.")
    parser.add_argument("--input", required=True, type=Path, help="Path to CSV or JSON dataset")
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
