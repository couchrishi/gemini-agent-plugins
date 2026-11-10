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
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    _loaded = json.loads(Path(input_arg).read_text(encoding="utf-8"))
    return _loaded if isinstance(_loaded, dict) else {}


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

    min_dscr = _to_float(cfg.get("min_dscr"), 1.25)
    max_lev = _to_float(cfg.get("max_net_leverage"), 3.5)
    min_ic = _to_float(cfg.get("min_interest_coverage"), 2.5)
    min_cr = _to_float(cfg.get("min_current_ratio"), 1.15)

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
    rev = _to_float(b.get("revenue_usd"), 0.0)
    ebitda = _to_float(b.get("ebitda_usd"), 0.0)
    total_debt = _to_float(b.get("total_debt_usd"), 0.0)
    cash = _to_float(b.get("cash_usd"), 0.0)
    net_debt = max(0.0, total_debt - cash)
    interest = _to_float(b.get("interest_expense_usd"), 0.0)
    amort = _to_float(b.get("principal_amortization_usd"), 0.0)
    floating_debt = _to_float(b.get("floating_debt_usd"), total_debt * 0.5)
    ca = _to_opt_float(b.get("current_assets_usd"))
    cl = _to_opt_float(b.get("current_liabilities_usd"))
    cr = (float(ca) / float(cl)) if (ca is not None and cl and float(cl) > 0) else None
    shock_bps = _to_float(cfg.get("stress_rate_shock_bps"), 200)

    # Operating leverage multiplier assumption: 1.5x EBITDA sensitivity to top-line revenue drops
    op_margin = (ebitda / rev) if rev > 0 else 0.15
    ebitda_mild = max(0.0, ebitda - (rev * 0.10 * max(op_margin * 1.5, 0.15)))
    ebitda_severe = max(0.0, ebitda - (rev * 0.20 * max(op_margin * 1.5, 0.20)))
    added_int = floating_debt * (shock_bps / 10000.0)

    base = _compute_scenario("Base Case", ebitda, interest, amort, net_debt, cr, cfg)
    mild = _compute_scenario(f"-10% Rev / +{int(shock_bps/2)}bps", ebitda_mild, interest + added_int * 0.5, amort, net_debt, cr, cfg)
    severe = _compute_scenario(f"-20% Rev / +{_to_int(shock_bps)}bps", ebitda_severe, interest + added_int, amort, net_debt, cr, cfg)

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
    data = _strip_null_items(load_payload(payload))
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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
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
