#!/usr/bin/env python3
"""Computes zero-residual Volume-Mix-Rate variance decomposition and z-score segment anomalies."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "default_currency": "USD",
    "zscore_anomaly_threshold": 2.0,
    "materiality_amount_threshold": 25000.0,
    "min_sample_size_guard": 30,
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
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            return _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="kpi-anomaly-driver-tree",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"segments": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="kpi-anomaly-driver-tree", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"segments": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"segments": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="kpi-anomaly-driver-tree")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "kpi-anomaly-driver-tree",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    segments = data.get("segments") or data.get("records") or []
    z_thresh = _to_float(cfg.get("zscore_anomaly_threshold"), 2.0)
    mat_amt = _to_float(cfg.get("materiality_amount_threshold"), 25000.0)
    min_n = max(1, _to_int(cfg.get("min_sample_size_guard"), 30))

    metadata = _as_dict(data.get("metadata"))
    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Segment table truncated; bridge does not cover full population.")

    parsed: list[dict[str, Any]] = []
    for idx, seg in enumerate(segments):
        name = str(seg.get("segment") or seg.get("name") or f"SEG-{idx + 1}")
        q0 = _to_float(seg.get("prior_volume"), 0.0)
        q1 = _to_float(seg.get("current_volume"), 0.0)
        if _to_opt_float(seg.get("prior_rate")) is not None:
            p0 = _to_float(seg.get("prior_rate"))
            r0 = q0 * p0
        else:
            r0 = _to_float(seg.get("prior_revenue"), 0.0)
            p0 = (r0 / q0) if q0 > 0 else 0.0

        if _to_opt_float(seg.get("current_rate")) is not None:
            p1 = _to_float(seg.get("current_rate"))
            r1 = q1 * p1
        else:
            r1 = _to_float(seg.get("current_revenue"), 0.0)
            p1 = (r1 / q1) if q1 > 0 else 0.0

        parsed.append(
            {
                "segment": name,
                "q0": q0,
                "q1": q1,
                "p0": p0,
                "p1": p1,
                "r0": r0,
                "r1": r1,
                "sample_size": _to_int(seg.get("sample_size"), q1),
            }
        )

    tot_q0 = sum(s["q0"] for s in parsed)
    tot_q1 = sum(s["q1"] for s in parsed)
    tot_r0 = sum(s["r0"] for s in parsed)
    tot_r1 = sum(s["r1"] for s in parsed)
    total_delta = tot_r1 - tot_r0
    avg_p0 = (tot_r0 / tot_q0) if tot_q0 > 0 else 0.0

    # Zero-residual Price-Volume-Mix identity:
    # Volume = (Q1 - Q0) * P_avg0
    # Mix = sum((share1_i - share0_i) * Q1 * P0_i) = sum(Q1_i * P0_i) - Q1 * P_avg0
    # Rate = sum(Q1_i * (P1_i - P0_i))
    volume_effect = (tot_q1 - tot_q0) * avg_p0
    mix_effect = 0.0
    rate_effect = 0.0

    pct_changes: list[float] = []
    for s in parsed:
        share0 = (s["q0"] / tot_q0) if tot_q0 > 0 else 0.0
        share1 = (s["q1"] / tot_q1) if tot_q1 > 0 else 0.0
        seg_vol = (s["q1"] - s["q0"]) * avg_p0
        seg_mix = (share1 - share0) * tot_q1 * (s["p0"] - avg_p0)
        seg_rate = s["q1"] * (s["p1"] - s["p0"])
        s["share0"] = share0
        s["share1"] = share1
        s["volume_effect"] = seg_vol
        s["mix_effect"] = seg_mix
        s["rate_effect"] = seg_rate
        s["delta"] = s["r1"] - s["r0"]
        pct_chg = ((s["r1"] - s["r0"]) / s["r0"] * 100.0) if s["r0"] > 0 else 0.0
        s["pct_change"] = pct_chg
        pct_changes.append(pct_chg)
        mix_effect += seg_mix
        rate_effect += seg_rate

    mean_pct = statistics.mean(pct_changes) if pct_changes else 0.0
    std_pct = statistics.pstdev(pct_changes) if len(pct_changes) > 1 else 0.0

    segment_rows: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    for s in parsed:
        z = ((s["pct_change"] - mean_pct) / std_pct) if std_pct > 1e-9 else 0.0
        low_sample = s["sample_size"] < min_n
        is_anom = abs(z) >= z_thresh and abs(s["delta"]) >= mat_amt * 0.25
        row = {
            "segment": s["segment"],
            "prior_revenue": round(s["r0"], 2),
            "current_revenue": round(s["r1"], 2),
            "total_delta": round(s["delta"], 2),
            "pct_change": round(s["pct_change"], 2),
            "volume_effect": round(s["volume_effect"], 2),
            "mix_effect": round(s["mix_effect"], 2),
            "rate_effect": round(s["rate_effect"], 2),
            "z_score": round(z, 3),
            "is_anomaly": is_anom,
            "low_sample_caution": low_sample,
        }
        segment_rows.append(row)
        if is_anom:
            anomalies.append(row)

    segment_rows.sort(key=lambda x: abs(x["total_delta"]), reverse=True)
    reconciled_sum = volume_effect + mix_effect + rate_effect
    residual = total_delta - reconciled_sum

    return {
        "skill": "kpi-anomaly-driver-tree",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "segment_count": len(segment_rows),
            "prior_total_revenue": round(tot_r0, 2),
            "current_total_revenue": round(tot_r1, 2),
            "total_delta": round(total_delta, 2),
            "volume_effect": round(volume_effect, 2),
            "mix_effect": round(mix_effect, 2),
            "rate_effect": round(rate_effect, 2),
            "bridge_residual": round(residual, 6),
            "material_variance_flagged": abs(total_delta) >= mat_amt,
            "anomaly_count": len(anomalies),
        },
        "segments": segment_rows,
        "anomalies": anomalies,
        "truncation_warnings": _collect_truncation_warnings(data, count=None, existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Volume-Mix-Rate KPI Bridge & Anomaly Tree",
            "",
            f"- **Prior -> Current:** {s['prior_total_revenue']:,.2f} -> {s['current_total_revenue']:,.2f} (**Delta:** {s['total_delta']:+,.2f})",
            f"- **Bridge Decomposition:** Volume `{s['volume_effect']:+,.2f}` | Mix `{s['mix_effect']:+,.2f}` | Rate `{s['rate_effect']:+,.2f}` (Residual: `{s['bridge_residual']}`)",
            f"- **Z-Score Anomalies:** {s['anomaly_count']}",
            "",
            "| Segment | Prior | Current | Delta | Volume | Mix | Rate | Z-Score | Anomaly |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
        ]
    )
    for row in result["segments"]:
        lines.append(
            f"| {row['segment']} | {row['prior_revenue']:,.2f} | {row['current_revenue']:,.2f} | "
            f"{row['total_delta']:+,.2f} | {row['volume_effect']:+,.2f} | {row['mix_effect']:+,.2f} | "
            f"{row['rate_effect']:+,.2f} | {row['z_score']:+.2f} | `{row['is_anomaly']}` |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute Volume-Mix-Rate KPI bridge and z-score anomalies.")
    parser.add_argument("--input", required=True, type=Path, help="Path to segments JSON or CSV")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="kpi-anomaly-driver-tree",
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        out = json.dumps(diag, indent=2, default=str)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0
    result = analyze(args.input, config=args.config, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
