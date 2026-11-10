#!/usr/bin/env python3
"""Computes supplier OTIF (On-Time In-Full), exclusion rules, chargebacks, and detention fees."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "target_otif_pct": 95.0,
    "in_full_tolerance_pct": 98.0,
    "on_time_grace_minutes": 30,
    "late_chargeback_pct": 3.0,
    "short_ship_chargeback_pct": 5.0,
    "free_dwell_minutes": 120,
    "detention_rate_per_hour_usd": 75.0,
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


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    return json.loads(Path(input_arg).read_text(encoding="utf-8"))


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    deliveries = data.get("po_deliveries") or data.get("deliveries") or []
    grace_mins = int(cfg.get("on_time_grace_minutes", 30))
    in_full_thresh = float(cfg.get("in_full_tolerance_pct", 98.0))
    late_cb_pct = float(cfg.get("late_chargeback_pct", 3.0))
    short_cb_pct = float(cfg.get("short_ship_chargeback_pct", 5.0))
    free_dwell = int(cfg.get("free_dwell_minutes", 120))
    det_rate = float(cfg.get("detention_rate_per_hour_usd", 75.0))
    target_otif = float(cfg.get("target_otif_pct", 95.0))

    vendor_rollup: dict[str, dict[str, Any]] = {}
    evaluated_pos: list[dict[str, Any]] = []
    trunc_warnings: list[str] = []
    if data.get("truncated"):
        trunc_warnings.append("WMS dock receipt feed truncated; supplier OTIF and chargeback totals are partial.")

    for po in deliveries:
        po_id = str(po.get("po_number") or "PO-1")
        vid = str(po.get("vendor_id") or "VEND-1")
        vname = str(po.get("vendor_name") or vid)
        po_val = float(po.get("po_value_usd") or 0.0)
        ordered = int(po.get("ordered_units") or 0)
        received = int(po.get("received_units") or 0)
        short_val = max(0.0, float(po.get("short_shipped_value_usd") or (max(0, ordered - received) * (po_val / ordered if ordered else 0.0))))

        appt_dt = _parse_iso(po.get("appointment_time"))
        arr_dt = _parse_iso(po.get("arrival_time"))
        dep_dt = _parse_iso(po.get("departure_time"))

        excl_reason = str(po.get("exclusion_reason") or "").strip()
        late_minutes = 0
        dwell_minutes = int(po.get("dwell_minutes") or 0)
        if appt_dt and arr_dt:
            late_minutes = int((arr_dt - appt_dt).total_seconds() // 60)
        if arr_dt and dep_dt and not po.get("dwell_minutes"):
            dwell_minutes = max(0, int((dep_dt - arr_dt).total_seconds() // 60))

        on_time = (late_minutes <= grace_mins) or (excl_reason in {"WEATHER_FORCE_MAJEURE", "BUYER_RESCHEDULED"})
        fill_pct = (received / ordered * 100.0) if ordered > 0 else 100.0
        in_full = (fill_pct >= in_full_thresh) or (excl_reason == "BUYER_CANCELED_LINE")
        otif_pass = on_time and in_full

        late_cb = round(po_val * (late_cb_pct / 100.0), 2) if not on_time else 0.0
        short_cb = round(short_val * (short_cb_pct / 100.0), 2) if not in_full else 0.0

        # Standard routing rule: late carriers forfeit free-time detention eligibility
        detention_fee = 0.0
        if on_time and dwell_minutes > free_dwell:
            billable_hours = (dwell_minutes - free_dwell) / 60.0
            detention_fee = round(billable_hours * det_rate, 2)

        v = vendor_rollup.setdefault(
            vid,
            {
                "vendor_id": vid,
                "vendor_name": vname,
                "po_count": 0,
                "otif_pass_count": 0,
                "total_po_value_usd": 0.0,
                "chargeback_usd": 0.0,
                "detention_exposure_usd": 0.0,
            },
        )
        v["po_count"] += 1
        if otif_pass:
            v["otif_pass_count"] += 1
        v["total_po_value_usd"] = round(v["total_po_value_usd"] + po_val, 2)
        v["chargeback_usd"] = round(v["chargeback_usd"] + late_cb + short_cb, 2)
        v["detention_exposure_usd"] = round(v["detention_exposure_usd"] + detention_fee, 2)

        evaluated_pos.append(
            {
                "po_number": po_id,
                "vendor_id": vid,
                "on_time": on_time,
                "late_minutes": late_minutes,
                "fill_pct": round(fill_pct, 2),
                "in_full": in_full,
                "otif_pass": otif_pass,
                "exclusion_reason": excl_reason or None,
                "late_chargeback_usd": late_cb,
                "short_chargeback_usd": short_cb,
                "detention_fee_usd": detention_fee,
            }
        )

    vendors_out: list[dict[str, Any]] = []
    for v in vendor_rollup.values():
        otif_pct = round(v["otif_pass_count"] / v["po_count"] * 100.0, 2) if v["po_count"] else 0.0
        v["otif_pct"] = otif_pct
        v["meets_sla"] = otif_pct >= target_otif
        v["net_recovery_usd"] = round(v["chargeback_usd"] - v["detention_exposure_usd"], 2)
        vendors_out.append(v)

    vendors_out.sort(key=lambda x: -x["chargeback_usd"])
    total_cb = round(sum(v["chargeback_usd"] for v in vendors_out), 2)
    total_det = round(sum(v["detention_exposure_usd"] for v in vendors_out), 2)
    overall_otif = round(
        sum(1 for p in evaluated_pos if p["otif_pass"]) / len(evaluated_pos) * 100.0, 2
    ) if evaluated_pos else 0.0

    return {
        "skill": "supplier-otif-chargeback-auditor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "po_deliveries_audited": len(evaluated_pos),
            "overall_otif_pct": overall_otif,
            "target_otif_pct": target_otif,
            "total_chargebacks_usd": total_cb,
            "total_detention_exposure_usd": total_det,
            "net_vendor_recovery_usd": round(total_cb - total_det, 2),
        },
        "vendor_scorecards": vendors_out,
        "po_details": evaluated_pos,
        "truncation_warnings": trunc_warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Supplier OTIF, Chargeback & Detention Settlement Audit",
            "",
            f"- **Deliveries Audited:** {s['po_deliveries_audited']} | **Overall OTIF:** {s['overall_otif_pct']:.1f}% (Target {s['target_otif_pct']:.1f}%) | "
            f"**Total Chargebacks:** ${s['total_chargebacks_usd']:,.2f} | **Detention Exposure:** ${s['total_detention_exposure_usd']:,.2f}",
            "",
            "| Vendor | POs | OTIF % | Chargebacks | Detention Payable | Net Recovery | SLA |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for v in result["vendor_scorecards"]:
        lines.append(
            f"| `{v['vendor_id']}` {v['vendor_name']} | {v['po_count']} | {v['otif_pct']:.1f}% | "
            f"${v['chargeback_usd']:,.2f} | ${v['detention_exposure_usd']:,.2f} | ${v['net_recovery_usd']:,.2f} | "
            f"{'PASS' if v['meets_sla'] else 'BREACH'} |"
        )
    lines.extend(["", "Draft debit memos require HITL vendor-ops sign-off before posting to ERP AP."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit supplier OTIF compliance, chargebacks, and carrier detention.")
    parser.add_argument("--input", required=True, type=Path, help="Path to PO dock delivery JSON")
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
