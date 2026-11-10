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


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"segments": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"segments": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"segments": data}
    return data


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    segments = data.get("segments") or data.get("records") or []
    z_thresh = float(cfg.get("zscore_anomaly_threshold", 2.0))
    mat_amt = float(cfg.get("materiality_amount_threshold", 25000.0))
    min_n = int(cfg.get("min_sample_size_guard", 30))

    metadata = data.get("metadata", {})
    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Segment table truncated; bridge does not cover full population.")

    parsed: list[dict[str, Any]] = []
    for idx, seg in enumerate(segments):
        name = str(seg.get("segment") or seg.get("name") or f"SEG-{idx + 1}")
        q0 = float(seg.get("prior_volume", 0.0))
        q1 = float(seg.get("current_volume", 0.0))
        if seg.get("prior_rate") is not None:
            p0 = float(seg["prior_rate"])
            r0 = q0 * p0
        else:
            r0 = float(seg.get("prior_revenue", 0.0))
            p0 = (r0 / q0) if q0 > 0 else 0.0

        if seg.get("current_rate") is not None:
            p1 = float(seg["current_rate"])
            r1 = q1 * p1
        else:
            r1 = float(seg.get("current_revenue", 0.0))
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
                "sample_size": int(seg.get("sample_size", q1)),
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
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
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
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute Volume-Mix-Rate KPI bridge and z-score anomalies.")
    parser.add_argument("--input", required=True, type=Path, help="Path to segments JSON or CSV")
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
