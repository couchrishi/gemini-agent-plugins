#!/usr/bin/env python3
"""Validates multi-year SaaS quotes, effective discounts, gross margin floors, and approval tiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "auto_approve_max_discount_pct": 15.0,
    "vp_approve_max_discount_pct": 25.0,
    "deal_desk_max_discount_pct": 35.0,
    "min_gross_margin_floor_pct": 60.0,
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


def _evaluate_quote(q: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    qid = str(q.get("quote_id") or "Q-1")
    customer = str(q.get("customer_name") or "Unknown Account")
    term_months = max(1, int(q.get("term_months", 12)))
    term_years = term_months / 12.0
    payment_days = int(q.get("payment_terms_days", 30))
    billing_freq = str(q.get("billing_frequency", "annual")).lower()
    sla_credit_cap_pct = float(q.get("sla_credit_cap_pct", 10.0))
    has_tfc = bool(q.get("termination_for_convenience", False))

    ramp_years = q.get("ramp_years", [])
    list_tcv = 0.0
    net_tcv = 0.0
    total_cogs = 0.0
    year1_acv = 0.0

    if ramp_years:
        for idx, yr in enumerate(ramp_years):
            y_list = float(yr.get("list_price_usd", 0.0))
            y_net = float(yr.get("net_price_usd", 0.0))
            y_cogs = float(yr.get("cogs_usd", 0.0))
            list_tcv += y_list
            net_tcv += y_net
            total_cogs += y_cogs
            if idx == 0:
                year1_acv = y_net
    else:
        for item in q.get("line_items", []):
            qty = float(item.get("quantity", 1))
            unit_list = float(item.get("unit_list_price_annual", 0.0))
            unit_net = float(item.get("unit_net_price_annual", unit_list))
            unit_cogs = float(item.get("unit_cogs_annual", 0.0))
            list_tcv += qty * unit_list * term_years
            net_tcv += qty * unit_net * term_years
            total_cogs += qty * unit_cogs * term_years
        year1_acv = net_tcv / term_years

    blended_acv = net_tcv / term_years
    net_discount_pct = ((list_tcv - net_tcv) / list_tcv * 100.0) if list_tcv > 0 else 0.0
    gross_margin_pct = ((net_tcv - total_cogs) / net_tcv * 100.0) if net_tcv > 0 else 0.0

    non_standard_flags: list[str] = []
    if payment_days > 60:
        non_standard_flags.append(f"Extended payment terms: Net {payment_days} (> Net 60)")
    elif payment_days > 45:
        non_standard_flags.append(f"Elevated payment terms: Net {payment_days}")
    if billing_freq not in {"annual", "upfront"}:
        non_standard_flags.append(f"Non-annual billing cadence: {billing_freq}")
    if has_tfc:
        non_standard_flags.append("Termination for convenience clause present")
    if sla_credit_cap_pct > 10.0:
        non_standard_flags.append(f"Elevated SLA service credit cap: {sla_credit_cap_pct}%")
    if ramp_years and year1_acv < blended_acv * 0.65:
        non_standard_flags.append(f"Back-end loaded ramp (Year-1 ACV ${year1_acv:,.0f} vs Blended ${blended_acv:,.0f})")

    tier0_max = float(cfg.get("auto_approve_max_discount_pct", 15.0))
    tier1_max = float(cfg.get("vp_approve_max_discount_pct", 25.0))
    tier2_max = float(cfg.get("deal_desk_max_discount_pct", 35.0))
    margin_floor = float(cfg.get("min_gross_margin_floor_pct", 60.0))

    margin_breach = gross_margin_pct < margin_floor
    if net_discount_pct > tier2_max or margin_breach or payment_days > 60 or has_tfc or sla_credit_cap_pct > 10.0:
        tier = "Tier 3: CFO / Executive Desk"
    elif net_discount_pct > tier1_max or payment_days > 45 or billing_freq != "annual" or (ramp_years and len(ramp_years) > 1):
        tier = "Tier 2: Deal Desk & Finance"
    elif net_discount_pct > tier0_max or payment_days > 30:
        tier = "Tier 1: Regional Sales VP"
    else:
        tier = "Tier 0: Auto-Approved"

    return {
        "quote_id": qid,
        "customer_name": customer,
        "term_months": term_months,
        "list_tcv_usd": round(list_tcv, 2),
        "net_tcv_usd": round(net_tcv, 2),
        "year1_acv_usd": round(year1_acv, 2),
        "blended_acv_usd": round(blended_acv, 2),
        "total_cogs_usd": round(total_cogs, 2),
        "net_effective_discount_pct": round(net_discount_pct, 2),
        "blended_gross_margin_pct": round(gross_margin_pct, 2),
        "margin_floor_breached": margin_breach,
        "non_standard_flags": non_standard_flags,
        "approval_tier": tier,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    quotes = data.get("quotes") or ([data["quote"]] if "quote" in data else [data] if "quote_id" in data else [])
    evaluated = [_evaluate_quote(q, cfg) for q in quotes]
    tier3_count = sum(1 for e in evaluated if e["approval_tier"].startswith("Tier 3"))
    margin_breaches = sum(1 for e in evaluated if e["margin_floor_breached"])

    return {
        "skill": "deal-desk-quote-guard",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "quote_count": len(evaluated),
            "tier3_escalation_count": tier3_count,
            "margin_floor_breach_count": margin_breaches,
            "total_net_tcv_usd": round(sum(e["net_tcv_usd"] for e in evaluated), 2),
        },
        "evaluated_quotes": evaluated,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Deal Desk Quote & Margin Guard",
            "",
            f"- **Quotes Evaluated:** {s['quote_count']} | **Total Net TCV:** ${s['total_net_tcv_usd']:,.2f}",
            f"- **Tier-3 Escalations:** {s['tier3_escalation_count']} | **Margin Floor Breaches:** {s['margin_floor_breach_count']}",
            "",
            "| Quote | Customer | Net TCV | Y1 ACV | Blended ACV | Discount % | Gross Margin % | Approval Tier |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for e in result["evaluated_quotes"]:
        lines.append(
            f"| `{e['quote_id']}` | {e['customer_name']} | ${e['net_tcv_usd']:,.2f} | ${e['year1_acv_usd']:,.2f} | "
            f"${e['blended_acv_usd']:,.2f} | {e['net_effective_discount_pct']:.1f}% | "
            f"{e['blended_gross_margin_pct']:.1f}% | {e['approval_tier']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SaaS deal discounts, ramps, and gross margin floors.")
    parser.add_argument("--input", required=True, type=Path, help="Path to quote JSON")
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
