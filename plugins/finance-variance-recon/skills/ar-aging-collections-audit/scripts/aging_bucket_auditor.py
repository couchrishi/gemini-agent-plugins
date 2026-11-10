#!/usr/bin/env python3
"""Audits open Accounts Receivable aging buckets with strict isolation of negative credit memos."""

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
    "ar_escalation_90_plus_threshold": 10000.0,
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
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8", newline="") as fh:
            return {"open_items": list(csv.DictReader(fh))}
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return date.fromisoformat(s[:10]) if s else None


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)
    esc_threshold = float(cfg.get("ar_escalation_90_plus_threshold", 10000.0))

    items = data.get("open_items", [])
    trailing_90d_sales = float(data.get("trailing_90d_credit_sales_usd") or 0.0)

    buckets_total = {"Current": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    total_unapplied_credits = 0.0
    customers: dict[str, dict[str, Any]] = {}

    for row in items:
        cid = str(row.get("customer_id") or "CUST-1")
        cname = str(row.get("customer_name") or cid)
        amt = float(row.get("open_amount_usd", 0.0))
        doc_type = str(row.get("doc_type") or "INVOICE").upper().strip()
        due_dt = _parse_date(row.get("due_date"))
        disputed = str(row.get("disputed", False)).lower() in {"true", "1", "yes"}

        cust = customers.setdefault(
            cid,
            {
                "customer_id": cid,
                "customer_name": cname,
                "Current": 0.0,
                "1-30": 0.0,
                "31-60": 0.0,
                "61-90": 0.0,
                "90+": 0.0,
                "gross_positive_ar_usd": 0.0,
                "unapplied_credits_usd": 0.0,
                "disputed_amount_usd": 0.0,
                "net_ar_usd": 0.0,
                "escalation_required": False,
            },
        )

        # Strictly isolate credit memos / negative unapplied cash rows
        if amt < 0 or doc_type in {"CREDIT_MEMO", "UNAPPLIED_CASH"}:
            credit_val = -abs(amt)
            total_unapplied_credits += credit_val
            cust["unapplied_credits_usd"] += credit_val
            cust["net_ar_usd"] += credit_val
            continue

        days_past_due = (as_of - due_dt).days if due_dt else 0
        if days_past_due <= 0:
            bucket = "Current"
        elif days_past_due <= 30:
            bucket = "1-30"
        elif days_past_due <= 60:
            bucket = "31-60"
        elif days_past_due <= 90:
            bucket = "61-90"
        else:
            bucket = "90+"

        buckets_total[bucket] += amt
        cust[bucket] += amt
        cust["gross_positive_ar_usd"] += amt
        cust["net_ar_usd"] += amt
        if disputed:
            cust["disputed_amount_usd"] += amt

    escalation_queue: list[dict[str, Any]] = []
    customer_summaries: list[dict[str, Any]] = []
    for cust in customers.values():
        for k in ("Current", "1-30", "31-60", "61-90", "90+", "gross_positive_ar_usd", "unapplied_credits_usd", "disputed_amount_usd", "net_ar_usd"):
            cust[k] = round(cust[k], 2)
        if cust["90+"] >= esc_threshold:
            cust["escalation_required"] = True
            escalation_queue.append(
                {
                    "customer_id": cust["customer_id"],
                    "customer_name": cust["customer_name"],
                    "overdue_90_plus_usd": cust["90+"],
                    "gross_positive_ar_usd": cust["gross_positive_ar_usd"],
                    "unapplied_credits_usd": cust["unapplied_credits_usd"],
                    "disputed_amount_usd": cust["disputed_amount_usd"],
                    "recommended_action": "CREDIT_RECON_THEN_DUNNING" if cust["unapplied_credits_usd"] < 0 else "FORMAL_DUNNING_HOLD",
                }
            )
        customer_summaries.append(cust)

    customer_summaries.sort(key=lambda c: (-c["90+"], -c["gross_positive_ar_usd"]))
    escalation_queue.sort(key=lambda c: -c["overdue_90_plus_usd"])

    gross_ar = sum(buckets_total.values())
    net_ar = gross_ar + total_unapplied_credits
    dso_days = round((gross_ar / trailing_90d_sales * 90.0), 1) if trailing_90d_sales > 0 else None

    return {
        "skill": "ar-aging-collections-audit",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "customer_count": len(customer_summaries),
            "gross_positive_ar_usd": round(gross_ar, 2),
            "unapplied_credits_usd": round(total_unapplied_credits, 2),
            "net_ar_usd": round(net_ar, 2),
            "bucket_totals_usd": {k: round(v, 2) for k, v in buckets_total.items()},
            "dso_days": dso_days,
            "collections_escalation_count": len(escalation_queue),
        },
        "customer_aging": customer_summaries,
        "collections_escalation_queue": escalation_queue,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    b = s["bucket_totals_usd"]
    dso_str = f"{s['dso_days']:.1f} days" if s["dso_days"] is not None else "N/A (no credit sales input)"
    lines.extend(
        [
            f"# Accounts Receivable Aging & Collections Audit (As Of {result['as_of_date']})",
            "",
            f"- **Gross Positive AR:** ${s['gross_positive_ar_usd']:,.2f} | **Isolated Unapplied Credits:** ${s['unapplied_credits_usd']:,.2f} | "
            f"**Net AR:** ${s['net_ar_usd']:,.2f}",
            f"- **Buckets:** Current ${b['Current']:,.2f} | 1-30d ${b['1-30']:,.2f} | 31-60d ${b['31-60']:,.2f} | "
            f"61-90d ${b['61-90']:,.2f} | **90+d ${b['90+']:,.2f}**",
            f"- **DSO:** {dso_str} | **Escalation Customers (>= threshold):** {s['collections_escalation_count']}",
            "",
            "| Customer | Gross AR | Current | 1-30d | 31-60d | 61-90d | 90+d | Unapplied Credits | Escalate |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for c in result["customer_aging"]:
        lines.append(
            f"| `{c['customer_id']}` {c['customer_name']} | ${c['gross_positive_ar_usd']:,.2f} | "
            f"${c['Current']:,.2f} | ${c['1-30']:,.2f} | ${c['31-60']:,.2f} | ${c['61-90']:,.2f} | "
            f"**${c['90+']:,.2f}** | ${c['unapplied_credits_usd']:,.2f} | {'YES' if c['escalation_required'] else 'No'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit AR aging buckets with strict credit memo isolation.")
    parser.add_argument("--input", required=True, type=Path, help="Path to open AR JSON or CSV")
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
