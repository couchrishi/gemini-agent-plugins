#!/usr/bin/env python3
"""Reconciles marketplace merchant GMV, commission rates, promo subsidies, FX, and PSP settlements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "default_commission_rate_pct": 15.0,
    "payment_processing_fee_pct": 2.9,
    "settlement_variance_tolerance_usd": 5.0,
    "negative_balance_clawback_alert_usd": 100.0,
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


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    merchants = data.get("merchant_payouts") or data.get("settlements") or []
    def_comm = float(cfg.get("default_commission_rate_pct", 15.0))
    psp_fee_pct = float(cfg.get("payment_processing_fee_pct", 2.9))
    var_tol = float(cfg.get("settlement_variance_tolerance_usd", 5.0))
    clawback_alert = float(cfg.get("negative_balance_clawback_alert_usd", 100.0))

    reconciled: list[dict[str, Any]] = []
    for m in merchants:
        mid = str(m.get("merchant_id") or "MRC-1")
        mname = str(m.get("merchant_name") or mid)
        gmv = float(m.get("gross_gmv_local") or 0.0)
        comm_pct = float(m.get("contract_commission_pct", def_comm))
        platform_promo_credit = float(m.get("platform_funded_promo_credit_local") or 0.0)
        merchant_promo_ded = float(m.get("merchant_funded_promo_deduction_local") or 0.0)
        refunds = float(m.get("refunds_and_chargebacks_local") or 0.0)
        tax_withheld = float(m.get("tax_withholding_local") or 0.0)
        fx_rate = float(m.get("fx_rate_to_settlement") or 1.0)
        bank_settled = float(m.get("actual_psp_settled_amount") or 0.0)

        commission_fee = gmv * (comm_pct / 100.0)
        processing_fee = gmv * (psp_fee_pct / 100.0)
        expected_net_local = gmv - commission_fee - processing_fee - merchant_promo_ded + platform_promo_credit - refunds - tax_withheld
        expected_settled = round(expected_net_local * fx_rate, 2)
        variance = round(bank_settled - expected_settled, 2)

        if expected_settled < -clawback_alert:
            status = "NEGATIVE_CLAWBACK_RISK"
        elif abs(variance) > var_tol:
            status = "SETTLEMENT_VARIANCE_EXCEPTION"
        else:
            status = "RECONCILED_OK"

        reconciled.append(
            {
                "merchant_id": mid,
                "merchant_name": mname,
                "gross_gmv_local": round(gmv, 2),
                "commission_fee_local": round(commission_fee, 2),
                "processing_fee_local": round(processing_fee, 2),
                "fx_rate_to_settlement": fx_rate,
                "expected_net_settlement": expected_settled,
                "actual_psp_settled": round(bank_settled, 2),
                "settlement_variance": variance,
                "status": status,
                "hitl_hold_required": status != "RECONCILED_OK",
            }
        )

    reconciled.sort(key=lambda x: -abs(x["settlement_variance"]))
    return {
        "skill": "commission-payout-reconciler",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "merchants_reconciled": len(reconciled),
            "exception_count": sum(1 for r in reconciled if r["status"] != "RECONCILED_OK"),
            "negative_clawback_count": sum(1 for r in reconciled if r["status"] == "NEGATIVE_CLAWBACK_RISK"),
            "total_expected_payout": round(sum(r["expected_net_settlement"] for r in reconciled), 2),
            "net_settlement_variance": round(sum(r["settlement_variance"] for r in reconciled), 2),
        },
        "merchant_reconciliations": reconciled,
        "truncation_warnings": ["PSP settlement report truncated; cash reconciliation incomplete."] if data.get("truncated") else [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Marketplace Commission & Merchant Payout Reconciliation",
            "",
            f"- **Merchants:** {s['merchants_reconciled']} | **Exceptions:** {s['exception_count']} | "
            f"**Clawback Risk:** {s['negative_clawback_count']} | **Net Variance:** ${s['net_settlement_variance']:,.2f}",
            "",
            "| Merchant | Gross GMV | Expected Net | Actual PSP | Variance | Status |",
            "| :--- | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for r in result["merchant_reconciliations"]:
        lines.append(
            f"| `{r['merchant_id']}` {r['merchant_name']} | ${r['gross_gmv_local']:,.2f} | "
            f"${r['expected_net_settlement']:,.2f} | ${r['actual_psp_settled']:,.2f} | "
            f"${r['settlement_variance']:+,.2f} | `{r['status']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile marketplace commissions, FX, and merchant PSP payouts.")
    parser.add_argument("--input", required=True, type=Path, help="Path to merchant settlement JSON")
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
