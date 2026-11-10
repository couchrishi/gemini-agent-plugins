#!/usr/bin/env python3
"""Evaluates promotional unit lift, cannibalization/halo adjustments, and net incremental promo margin ROI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_acceptable_promo_roi": 0.15,
    "min_incremental_lift_pct": 10.0,
    "default_cannibalization_gm_rate": 0.35,
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

    campaigns = data.get("campaigns") or data.get("promotions") or []
    min_roi = float(cfg.get("min_acceptable_promo_roi", 0.15))
    min_lift = float(cfg.get("min_incremental_lift_pct", 10.0))

    trunc_warnings: list[str] = []
    if data.get("truncated"):
        trunc_warnings.append("Promotion dataset truncated; portfolio margin attribution excludes omitted SKUs.")

    evaluations: list[dict[str, Any]] = []
    for camp in campaigns:
        cid = str(camp.get("campaign_id") or "PROMO-1")
        name = str(camp.get("campaign_name") or cid)
        base_days = max(1, int(camp.get("baseline_days") or 28))
        promo_days = max(1, int(camp.get("promo_days") or 7))

        # Chain-denominator hygiene: normalize baseline to promo duration via daily velocity
        base_units_total = float(camp.get("baseline_units") or 0.0)
        base_rev_total = float(camp.get("baseline_revenue_usd") or 0.0)
        base_gm_total = float(camp.get("baseline_gross_margin_usd") or 0.0)

        norm_base_units = (base_units_total / base_days) * promo_days
        norm_base_rev = (base_rev_total / base_days) * promo_days
        norm_base_gm = (base_gm_total / base_days) * promo_days

        promo_units = float(camp.get("promo_units") or 0.0)
        promo_rev = float(camp.get("promo_revenue_usd") or 0.0)
        promo_gm_raw = float(camp.get("promo_gross_margin_usd") or 0.0)

        cannibal_gm_loss = float(camp.get("sibling_cannibalization_gm_loss_usd") or 0.0)
        halo_gm_gain = float(camp.get("basket_halo_gm_gain_usd") or 0.0)
        vendor_coop = float(camp.get("vendor_funding_rebate_usd") or 0.0)
        promo_media_display_cost = float(camp.get("promo_execution_cost_usd") or 0.0)
        net_promo_spend = max(0.0, promo_media_display_cost - vendor_coop)

        unit_lift_pct = ((promo_units - norm_base_units) / norm_base_units * 100.0) if norm_base_units > 0 else 0.0
        rev_lift_pct = ((promo_rev - norm_base_rev) / norm_base_rev * 100.0) if norm_base_rev > 0 else 0.0

        inc_direct_gm = promo_gm_raw - norm_base_gm
        net_inc_gm = inc_direct_gm + halo_gm_gain - cannibal_gm_loss + vendor_coop - promo_media_display_cost

        denom = promo_media_display_cost if promo_media_display_cost > 0 else max(abs(inc_direct_gm), 1.0)
        roi = net_inc_gm / denom

        if net_inc_gm < 0:
            verdict = "MARGIN_DESTRUCTIVE"
        elif roi < min_roi or unit_lift_pct < min_lift:
            verdict = "SUBSCALE_REWORK_FUNDING"
        else:
            verdict = "PROFITABLE_SCALE"

        evaluations.append(
            {
                "campaign_id": cid,
                "campaign_name": name,
                "baseline_days": base_days,
                "promo_days": promo_days,
                "normalized_baseline_units": round(norm_base_units, 1),
                "promo_units": round(promo_units, 1),
                "unit_lift_pct": round(unit_lift_pct, 2),
                "revenue_lift_pct": round(rev_lift_pct, 2),
                "incremental_direct_gm_usd": round(inc_direct_gm, 2),
                "halo_gm_gain_usd": round(halo_gm_gain, 2),
                "cannibalization_gm_loss_usd": round(cannibal_gm_loss, 2),
                "vendor_funding_rebate_usd": round(vendor_coop, 2),
                "promo_execution_cost_usd": round(promo_media_display_cost, 2),
                "net_promo_spend_usd": round(net_promo_spend, 2),
                "net_incremental_gm_usd": round(net_inc_gm, 2),
                "promo_roi_ratio": round(roi, 3),
                "verdict": verdict,
            }
        )

    evaluations.sort(key=lambda x: -x["net_incremental_gm_usd"])
    return {
        "skill": "merchandising-assortment-planner",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "campaigns_evaluated": len(evaluations),
            "profitable_count": sum(1 for e in evaluations if e["verdict"] == "PROFITABLE_SCALE"),
            "margin_destructive_count": sum(1 for e in evaluations if e["verdict"] == "MARGIN_DESTRUCTIVE"),
            "total_net_incremental_gm_usd": round(sum(e["net_incremental_gm_usd"] for e in evaluations), 2),
        },
        "campaign_evaluations": evaluations,
        "truncation_warnings": trunc_warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Promotional Lift, Cannibalization & Net Margin Attribution",
            "",
            f"- **Campaigns:** {s['campaigns_evaluated']} | **Profitable:** {s['profitable_count']} | "
            f"**Margin Destructive:** {s['margin_destructive_count']} | "
            f"**Portfolio Net Incremental GM:** ${s['total_net_incremental_gm_usd']:,.2f}",
            "",
            "| Campaign | Unit Lift | Direct Inc GM | Halo GM | Cannibalization | Net Inc GM | ROI | Verdict |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for e in result["campaign_evaluations"]:
        lines.append(
            f"| `{e['campaign_id']}` {e['campaign_name']} | {e['unit_lift_pct']:+.1f}% | "
            f"${e['incremental_direct_gm_usd']:,.2f} | ${e['halo_gm_gain_usd']:,.2f} | "
            f"-${e['cannibalization_gm_loss_usd']:,.2f} | ${e['net_incremental_gm_usd']:,.2f} | "
            f"{e['promo_roi_ratio']:.2f}x | `{e['verdict']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze retail promo lift, halo/cannibalization, and net GM ROI.")
    parser.add_argument("--input", required=True, type=Path, help="Path to promotional telemetry JSON")
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
