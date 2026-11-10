#!/usr/bin/env python3
"""Reconciles SAP GR/IR clearing accounts across goods receipts and invoice receipts with TCURX and aging guards."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "default_currency": "USD",
    "gr_ir_aging_threshold_days": 60,
    "clearing_tolerance_usd": 5.0,
}

DEFAULT_DECIMALS = {"JPY": 0, "KRW": 0, "VND": 0, "CLP": 0, "KWD": 3, "BHD": 3, "USD": 2, "EUR": 2, "GBP": 2}


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


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return date.fromisoformat(s[:10]) if s else None


def _scale_sap(amount: float, currency: str, sap_raw: bool, shkzg: str | None, decimals_map: dict[str, int]) -> float:
    curr = currency.upper().strip() or "USD"
    dec = int(decimals_map.get(curr, DEFAULT_DECIMALS.get(curr, 2)))
    val = amount * (10 ** (2 - dec)) if sap_raw else amount
    if (shkzg or "").strip().upper() == "H":
        val = -val
    return val


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)
    aging_limit = int(cfg.get("gr_ir_aging_threshold_days", 60))
    clear_tol = float(cfg.get("clearing_tolerance_usd", 5.0))

    fx_rates = {str(k).upper(): float(v) for k, v in data.get("fx_rates", {"USD": 1.0}).items()}
    decimals_map = {str(k).upper(): int(v) for k, v in data.get("decimal_places", {}).items()}

    # Aggregate EKBE history rows or combined GR/IR PO lines
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in data.get("gr_ir_postings", []):
        key = (str(row.get("po_number") or "").strip(), str(row.get("line_item") or "10").strip())
        curr = str(row.get("currency") or "USD").upper()
        rate = float(fx_rates.get(curr, 1.0))
        sap_raw = bool(row.get("sap_raw_encoding", False))
        shkzg = row.get("shkzg")
        post_dt = _parse_date(row.get("posting_date"))

        b = buckets.setdefault(
            key,
            {
                "po_number": key[0],
                "line_item": key[1],
                "vendor_id": str(row.get("vendor_id") or "UNKNOWN"),
                "currency": curr,
                "gr_qty": 0.0,
                "ir_qty": 0.0,
                "gr_usd": 0.0,
                "ir_usd": 0.0,
                "earliest_open_date": post_dt,
            },
        )
        if post_dt and (b["earliest_open_date"] is None or post_dt < b["earliest_open_date"]):
            b["earliest_open_date"] = post_dt

        if "posting_type" in row:
            ptype = str(row["posting_type"]).upper().strip()  # WE (GR) or RE (IR)
            raw_amt = float(row.get("amount", 0.0))
            qty = float(row.get("qty", 0.0))
            if (shkzg or "").upper() == "H":
                qty = -abs(qty)
            amt_local = _scale_sap(abs(raw_amt), curr, sap_raw, shkzg, decimals_map)
            amt_usd = amt_local * rate
            if ptype in {"WE", "GR"}:
                b["gr_qty"] += qty
                b["gr_usd"] += amt_usd
            else:
                b["ir_qty"] += qty
                b["ir_usd"] += amt_usd
        else:
            # Direct summarized PO row fallback
            gr_amt = _scale_sap(float(row.get("gr_amount", 0.0)), curr, sap_raw, row.get("gr_shkzg"), decimals_map)
            ir_amt = _scale_sap(float(row.get("ir_amount", 0.0)), curr, sap_raw, row.get("ir_shkzg"), decimals_map)
            b["gr_qty"] += float(row.get("gr_qty", 0.0))
            b["ir_qty"] += float(row.get("ir_qty", 0.0))
            b["gr_usd"] += gr_amt * rate
            b["ir_usd"] += ir_amt * rate

    items: list[dict[str, Any]] = []
    for _key, b in sorted(buckets.items()):
        net_qty = b["gr_qty"] - b["ir_qty"]
        net_usd = b["gr_usd"] - b["ir_usd"]
        age_days = (as_of - b["earliest_open_date"]).days if b["earliest_open_date"] else None
        stale = age_days is not None and age_days > aging_limit and abs(net_usd) > clear_tol

        if abs(net_usd) <= clear_tol and abs(net_qty) <= 1e-6:
            state = "BALANCED_CLEARED"
            action = "Auto-clear via MR11/F.13 (eligible)"
        elif net_qty > 1e-6:
            state = "GR_WITHOUT_IR"
            action = "Maintain accrued GR/IR liability; chase vendor invoice"
        elif net_qty < -1e-6:
            state = "IR_WITHOUT_GR"
            action = "Block AP payment; confirm physical goods receipt or credit memo"
        else:
            state = "PRICE_OR_FX_RESIDUAL"
            action = "Post price/FX variance adjustment after Controller confirmation"

        items.append(
            {
                "po_number": b["po_number"],
                "line_item": b["line_item"],
                "vendor_id": b["vendor_id"],
                "currency": b["currency"],
                "gr_qty": round(b["gr_qty"], 2),
                "ir_qty": round(b["ir_qty"], 2),
                "net_qty": round(net_qty, 2),
                "gr_usd": round(b["gr_usd"], 2),
                "ir_usd": round(b["ir_usd"], 2),
                "net_imbalance_usd": round(net_usd, 2),
                "age_days": age_days,
                "aging_breach": stale,
                "clearing_state": state,
                "recommended_action": action,
            }
        )

    open_items = [x for x in items if x["clearing_state"] != "BALANCED_CLEARED"]
    return {
        "skill": "gr-ir-clearing-orchestrator",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "po_lines_analyzed": len(items),
            "cleared_count": len(items) - len(open_items),
            "open_imbalance_count": len(open_items),
            "gr_without_ir_count": sum(1 for x in items if x["clearing_state"] == "GR_WITHOUT_IR"),
            "ir_without_gr_count": sum(1 for x in items if x["clearing_state"] == "IR_WITHOUT_GR"),
            "aging_breach_count": sum(1 for x in items if x["aging_breach"]),
            "total_abs_imbalance_usd": round(sum(abs(x["net_imbalance_usd"]) for x in open_items), 2),
        },
        "clearing_lines": items,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# SAP GR/IR Clearing Reconciliation (As Of {result['as_of_date']})",
            "",
            f"- **PO Lines:** {s['po_lines_analyzed']} | **Open Imbalances:** {s['open_imbalance_count']} | "
            f"**GR w/o IR:** {s['gr_without_ir_count']} | **IR w/o GR:** {s['ir_without_gr_count']}",
            f"- **Aging Breaches (> limit):** {s['aging_breach_count']} | **Gross Imbalance:** ${s['total_abs_imbalance_usd']:,.2f}",
            "",
            "| PO | Line | Vendor | Net Qty | Net Imbalance (USD) | Age (d) | State | Action |",
            "| :--- | :--- | :--- | ---: | ---: | ---: | :--- | :--- |",
        ]
    )
    for x in result["clearing_lines"]:
        lines.append(
            f"| `{x['po_number']}` | `{x['line_item']}` | `{x['vendor_id']}` | {x['net_qty']:+.2f} | "
            f"${x['net_imbalance_usd']:+,.2f} | {x['age_days'] if x['age_days'] is not None else '—'} | "
            f"`{x['clearing_state']}` | {x['recommended_action']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile SAP GR/IR clearing postings across PO lines.")
    parser.add_argument("--input", required=True, type=Path, help="Path to GR/IR postings JSON")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--as-of", type=str, help="Reference ISO date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, as_of_date=args.as_of)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
