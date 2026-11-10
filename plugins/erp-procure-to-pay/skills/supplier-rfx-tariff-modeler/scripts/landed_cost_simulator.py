#!/usr/bin/env python3
"""Models supplier RFx bids on Total Landed Cost including tariffs, duties, financing, and quality penalties."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "annual_cost_of_capital_pct": 8.0,
    "defect_cost_per_unit_usd": 45.0,
    "max_single_source_share_pct": 70.0,
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
    tariff_shock_pct: float | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    demand = max(1.0, float(data.get("annual_demand_units") or 10000))
    shock_pct = float(tariff_shock_pct if tariff_shock_pct is not None else data.get("tariff_shock_pct", 0.0))
    shocked_countries = {str(c).upper() for c in data.get("tariff_shock_countries", [])}
    coc_pct = float(cfg.get("annual_cost_of_capital_pct", 8.0)) / 100.0
    defect_cost = float(cfg.get("defect_cost_per_unit_usd", 45.0))

    bids = data.get("bids", [])
    models: list[dict[str, Any]] = []

    for b in bids:
        sid = str(b.get("supplier_id") or "SUP-1")
        sname = str(b.get("supplier_name") or sid)
        origin = str(b.get("origin_country") or "US").upper()
        moq = int(b.get("moq_units") or 0)
        fob = float(b.get("unit_fob_usd") or 0.0)
        freight = float(b.get("freight_per_unit_usd") or 0.0)
        ins_pct = float(b.get("insurance_pct") or 0.5) / 100.0
        base_tariff = float(b.get("base_tariff_pct") or 0.0)
        extra_duty = float(b.get("additional_duty_pct") or 0.0)
        applied_shock = shock_pct if (not shocked_countries or origin in shocked_countries) else 0.0
        total_duty_pct = (base_tariff + extra_duty + applied_shock) / 100.0

        payment_days = int(b.get("payment_days") or 30)
        lead_days = int(b.get("lead_time_days") or 30)
        ppm = float(b.get("quality_defect_ppm") or 500.0)

        duty_per_unit = fob * total_duty_pct
        ins_per_unit = (fob + freight) * ins_pct
        financing_adj_per_unit = fob * coc_pct * ((30 - payment_days) / 365.0)
        quality_risk_per_unit = (ppm / 1_000_000.0) * defect_cost
        landed_unit = fob + freight + ins_per_unit + duty_per_unit + financing_adj_per_unit + quality_risk_per_unit
        annual_total = landed_unit * demand
        moq_ok = moq <= demand

        models.append(
            {
                "supplier_id": sid,
                "supplier_name": sname,
                "origin_country": origin,
                "moq_feasible": moq_ok,
                "unit_fob_usd": round(fob, 4),
                "duty_per_unit_usd": round(duty_per_unit, 4),
                "effective_tariff_pct": round(total_duty_pct * 100.0, 2),
                "landed_unit_cost_usd": round(landed_unit, 4),
                "annual_landed_cost_usd": round(annual_total, 2),
                "lead_time_days": lead_days,
                "quality_defect_ppm": ppm,
                "payment_days": payment_days,
            }
        )

    models.sort(key=lambda m: (not m["moq_feasible"], m["annual_landed_cost_usd"]))
    for rank, m in enumerate(models, 1):
        m["cost_rank"] = rank

    best = models[0] if models else None
    spread = round(models[-1]["annual_landed_cost_usd"] - best["annual_landed_cost_usd"], 2) if len(models) > 1 else 0.0

    return {
        "skill": "supplier-rfx-tariff-modeler",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "annual_demand_units": demand,
            "tariff_shock_applied_pct": shock_pct,
            "bids_evaluated": len(models),
            "lowest_landed_supplier": best["supplier_name"] if best else "None",
            "lowest_annual_landed_usd": best["annual_landed_cost_usd"] if best else 0.0,
            "annual_savings_vs_worst_usd": spread,
        },
        "landed_cost_models": models,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Supplier RFx Total Landed Cost & Tariff Sensitivity Model",
            "",
            f"- **Annual Demand:** {s['annual_demand_units']:,.0f} units | **Tariff Shock:** +{s['tariff_shock_applied_pct']:.1f}%",
            f"- **Lowest Landed Supplier:** {s['lowest_landed_supplier']} (${s['lowest_annual_landed_usd']:,.2f}/yr; "
            f"Saves ${s['annual_savings_vs_worst_usd']:,.2f} vs highest)",
            "",
            "| Rank | Supplier | Origin | FOB | Tariff % | Landed/Unit | Annual Landed Cost | Lead (d) |",
            "| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for m in result["landed_cost_models"]:
        lines.append(
            f"| {m['cost_rank']} | `{m['supplier_id']}` {m['supplier_name']} | {m['origin_country']} | "
            f"${m['unit_fob_usd']:,.2f} | {m['effective_tariff_pct']:.1f}% | ${m['landed_unit_cost_usd']:,.2f} | "
            f"${m['annual_landed_cost_usd']:,.2f} | {m['lead_time_days']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate supplier RFx landed cost under tariff and payment scenarios.")
    parser.add_argument("--input", required=True, type=Path, help="Path to RFx bids JSON")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--tariff-shock-pct", type=float, help="Optional incremental tariff shock percentage")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, tariff_shock_pct=args.tariff_shock_pct)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
