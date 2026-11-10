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


def _load_enterprise_io() -> Any | None:
    try:
        from scripts import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    try:
        import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    eio_path = Path(__file__).resolve().parent / "enterprise_io.py"
    if eio_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("enterprise_io", eio_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


_ENTERPRISE_IO = _load_enterprise_io()


def _to_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"true", "yes", "y", "1", "on"}:
        return True
    if s in {"false", "no", "n", "0", "off", ""}:
        return False if s else default
    return bool(s)


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
    org_cfg = _to_bool(cfg.get("org_configured"), False)
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(
    input_arg: str | Path | dict[str, Any] | list[dict[str, Any]],
    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"merchant_payouts": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="commission-payout-reconciler", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"merchant_payouts": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"merchant_payouts": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)

    merchants = data.get("merchant_payouts") or data.get("settlements") or []
    def_comm = _to_float(cfg.get("default_commission_rate_pct"), 15.0)
    psp_fee_pct = _to_float(cfg.get("payment_processing_fee_pct"), 2.9)
    var_tol = _to_float(cfg.get("settlement_variance_tolerance_usd"), 5.0)
    clawback_alert = _to_float(cfg.get("negative_balance_clawback_alert_usd"), 100.0)

    reconciled: list[dict[str, Any]] = []
    for m in merchants:
        mid = str(m.get("merchant_id") or "MRC-1")
        mname = str(m.get("merchant_name") or mid)
        gmv = _to_float(m.get("gross_gmv_local"), 0.0)
        comm_pct = _to_float(m.get("contract_commission_pct"), def_comm)
        platform_promo_credit = _to_float(m.get("platform_funded_promo_credit_local"), 0.0)
        merchant_promo_ded = _to_float(m.get("merchant_funded_promo_deduction_local"), 0.0)
        refunds = _to_float(m.get("refunds_and_chargebacks_local"), 0.0)
        tax_withheld = _to_float(m.get("tax_withholding_local"), 0.0)
        fx_rate = (_to_float(m.get("fx_rate_to_settlement")) or 1.0)
        bank_settled = _to_float(m.get("actual_psp_settled_amount"), 0.0)

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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(reconciled), existing=["PSP settlement report truncated; cash reconciliation incomplete."] if data.get("truncated") else []),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile marketplace commissions, FX, and merchant PSP payouts.")
    parser.add_argument("--input", required=True, type=Path, help="Path to merchant settlement JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, sheet=args.sheet)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
