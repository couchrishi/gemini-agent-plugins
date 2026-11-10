#!/usr/bin/env python3
"""Evaluates commercial credit DSCR, Net Leverage, Interest Coverage, and stress-test covenant breaches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_dscr": 1.25,
    "max_net_leverage": 3.5,
    "min_interest_coverage": 2.5,
    "min_current_ratio": 1.15,
    "stress_rate_shock_bps": 200,
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


def _compute_scenario(
    name: str,
    ebitda: float,
    interest: float,
    amort: float,
    net_debt: float,
    current_ratio: float | None,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    debt_service = interest + amort
    dscr = (ebitda / debt_service) if debt_service > 0 else 99.0
    net_lev = (net_debt / ebitda) if ebitda > 0 else 99.0
    int_cov = (ebitda / interest) if interest > 0 else 99.0

    min_dscr = float(cfg.get("min_dscr", 1.25))
    max_lev = float(cfg.get("max_net_leverage", 3.5))
    min_ic = float(cfg.get("min_interest_coverage", 2.5))
    min_cr = float(cfg.get("min_current_ratio", 1.15))

    breaches: list[str] = []
    watches: list[str] = []
    if dscr < 1.10:
        breaches.append(f"DSCR {dscr:.2f}x < 1.10x breach")
    elif dscr < min_dscr:
        watches.append(f"DSCR {dscr:.2f}x < {min_dscr:.2f}x covenant")
    if net_lev > 4.25:
        breaches.append(f"Net Leverage {net_lev:.2f}x > 4.25x breach")
    elif net_lev > max_lev:
        watches.append(f"Net Leverage {net_lev:.2f}x > {max_lev:.2f}x covenant")
    if int_cov < min_ic:
        breaches.append(f"Interest Coverage {int_cov:.2f}x < {min_ic:.2f}x")
    if current_ratio is not None and current_ratio < min_cr:
        watches.append(f"Current Ratio {current_ratio:.2f}x < {min_cr:.2f}x")

    status = "COVENANT_BREACH" if breaches else ("WATCH_ALERT" if watches else "COVENANT_COMPLIANT")
    return {
        "scenario": name,
        "ebitda_usd": round(ebitda, 2),
        "debt_service_usd": round(debt_service, 2),
        "dscr": round(dscr, 2),
        "net_leverage": round(net_lev, 2),
        "interest_coverage": round(int_cov, 2),
        "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
        "status": status,
        "breaches": breaches,
        "watches": watches,
    }


def _eval_borrower(b: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    bid = str(b.get("borrower_id") or "BORR-1")
    name = str(b.get("borrower_name") or bid)
    rev = float(b.get("revenue_usd") or 0.0)
    ebitda = float(b.get("ebitda_usd") or 0.0)
    total_debt = float(b.get("total_debt_usd") or 0.0)
    cash = float(b.get("cash_usd") or 0.0)
    net_debt = max(0.0, total_debt - cash)
    interest = float(b.get("interest_expense_usd") or 0.0)
    amort = float(b.get("principal_amortization_usd") or 0.0)
    floating_debt = float(b.get("floating_debt_usd", total_debt * 0.5))
    ca = b.get("current_assets_usd")
    cl = b.get("current_liabilities_usd")
    cr = (float(ca) / float(cl)) if (ca is not None and cl and float(cl) > 0) else None
    shock_bps = float(cfg.get("stress_rate_shock_bps", 200))

    # Operating leverage multiplier assumption: 1.5x EBITDA sensitivity to top-line revenue drops
    op_margin = (ebitda / rev) if rev > 0 else 0.15
    ebitda_mild = max(0.0, ebitda - (rev * 0.10 * max(op_margin * 1.5, 0.15)))
    ebitda_severe = max(0.0, ebitda - (rev * 0.20 * max(op_margin * 1.5, 0.20)))
    added_int = floating_debt * (shock_bps / 10000.0)

    base = _compute_scenario("Base Case", ebitda, interest, amort, net_debt, cr, cfg)
    mild = _compute_scenario(f"-10% Rev / +{int(shock_bps/2)}bps", ebitda_mild, interest + added_int * 0.5, amort, net_debt, cr, cfg)
    severe = _compute_scenario(f"-20% Rev / +{int(shock_bps)}bps", ebitda_severe, interest + added_int, amort, net_debt, cr, cfg)

    overall = "DECLINE_OR_RESTRUCTURE" if base["status"] == "COVENANT_BREACH" else (
        "CREDIT_COMMITTEE_CONDITIONS" if severe["status"] == "COVENANT_BREACH" or base["status"] == "WATCH_ALERT"
        else "ELIGIBLE_FOR_CREDIT_SIGN_OFF"
    )
    return {
        "borrower_id": bid,
        "borrower_name": name,
        "net_debt_usd": round(net_debt, 2),
        "scenarios": [base, mild, severe],
        "underwriting_recommendation": overall,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    borrowers = data.get("borrowers") or ([data] if "ebitda_usd" in data else [])
    evaluated = [_eval_borrower(b, cfg) for b in borrowers]

    return {
        "skill": "commercial-credit-memo-analyst",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "borrowers_evaluated": len(evaluated),
            "base_breach_count": sum(1 for e in evaluated if e["scenarios"][0]["status"] == "COVENANT_BREACH"),
            "stress_breach_count": sum(1 for e in evaluated if e["scenarios"][-1]["status"] == "COVENANT_BREACH"),
            "clean_pass_count": sum(1 for e in evaluated if e["underwriting_recommendation"] == "ELIGIBLE_FOR_CREDIT_SIGN_OFF"),
        },
        "credit_evaluations": evaluated,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Commercial Credit Covenant & Stress Underwriting Memo",
            "",
            f"- **Borrowers Evaluated:** {s['borrowers_evaluated']} | **Base Covenant Breaches:** {s['base_breach_count']} | "
            f"**Severe Stress Breaches:** {s['stress_breach_count']}",
            "",
            "| Borrower | Scenario | DSCR | Net Leverage | Int Cov | Status | Notes |",
            "| :--- | :--- | ---: | ---: | ---: | :--- | :--- |",
        ]
    )
    for b in result["credit_evaluations"]:
        for sc in b["scenarios"]:
            notes = "; ".join(sc["breaches"] + sc["watches"]) or "Meets covenants"
            lines.append(
                f"| `{b['borrower_id']}` {b['borrower_name']} | {sc['scenario']} | {sc['dscr']:.2f}x | "
                f"{sc['net_leverage']:.2f}x | {sc['interest_coverage']:.2f}x | `{sc['status']}` | {notes} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze commercial borrower covenants and stress shocks.")
    parser.add_argument("--input", required=True, type=Path, help="Path to borrower financials JSON")
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
