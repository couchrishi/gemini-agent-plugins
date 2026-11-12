#!/usr/bin/env python3
"""Performs AP PO/GR/Invoice 3-way matching with SAP TCURX decimal scaling, SHKZG credits, and duplicate/fraud holds."""

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
    "default_currency": "USD",
    "price_tolerance_pct": 0.02,
    "price_tolerance_abs": 500.0,
    "qty_tolerance_pct": 0.0,
    "duplicate_date_window_days": 3,
}

DEFAULT_DECIMALS = {
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "CLP": 0,
    "ISK": 0,
    "KWD": 3,
    "BHD": 3,
    "OMR": 3,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "SGD": 2,
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


def _read_table(
    path: Path,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
) -> list[dict[str, Any]]:
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.read_enterprise_table(
            path,
            sheet=sheet,
            column_map=column_map,
            fallback_keys=("rows", "items", "records", "invoices", "purchase_orders", "goods_receipts"),
        )
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return loaded
    if isinstance(loaded, dict):
        for k in ("rows", "items", "records", "invoices", "purchase_orders", "goods_receipts"):
            if isinstance(loaded.get(k), list):
                return loaded[k]
    return []


def load_payload(
    input_arg: str | Path | dict[str, Any] | None = None,
    *,
    po_path: str | Path | None = None,
    gr_path: str | Path | None = None,
    invoice_path: str | Path | None = None,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if input_arg is None:
        data: dict[str, Any] = {}
    elif isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            data = _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="ap-three-way-match",
                column_map=column_map,
                sheet_map=sheet_map,
            )
        elif isinstance(input_arg, dict):
            data = dict(input_arg)
        else:
            data = {"invoices": input_arg}
    elif _ENTERPRISE_IO is not None:
        data = _ENTERPRISE_IO.load_enterprise_payload(
            input_arg,
            skill_id="ap-three-way-match",
            sheet=sheet,
            column_map=column_map,
            sheet_map=sheet_map,
        )
    else:
        data = json.loads(Path(input_arg).read_text(encoding="utf-8"))
    if po_path is not None:
        data["purchase_orders"] = _read_table(Path(po_path), sheet=sheet, column_map=column_map)
    if gr_path is not None:
        data["goods_receipts"] = _read_table(Path(gr_path), sheet=sheet, column_map=column_map)
    if invoice_path is not None:
        data["invoices"] = _read_table(Path(invoice_path), sheet=sheet, column_map=column_map)
    if _ENTERPRISE_IO is not None and (po_path is not None or gr_path is not None or invoice_path is not None):
        data = _ENTERPRISE_IO._rollup_nested_records(data, skill_id="ap-three-way-match")
    return data

def _normalize_amount(
    raw_amount: float,
    currency: str,
    *,
    sap_raw_encoding: bool,
    shkzg: str | None,
    decimals_map: dict[str, int],
    fx_rates: dict[str, float],
) -> tuple[float, float]:
    """Return (actual_local_amount, usd_equivalent) after TCURX decimal shift and SHKZG sign normalization."""
    curr = currency.upper().strip() or "USD"
    decimals = _to_int(decimals_map.get(curr), DEFAULT_DECIMALS.get(curr, 2))
    scaled = raw_amount * (10 ** (2 - decimals)) if sap_raw_encoding else raw_amount
    sign = -1.0 if (shkzg or "").strip().upper() == "H" else 1.0
    local_amt = scaled * sign
    rate_to_usd = _to_float(fx_rates.get(curr), 1.0)
    return local_amt, local_amt * rate_to_usd


def analyze(
    payload: str | Path | dict[str, Any] | None = None,
    config: str | Path | dict[str, Any] | None = None,
    *,
    po_path: str | Path | None = None,
    gr_path: str | Path | None = None,
    invoice_path: str | Path | None = None,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, po_path=po_path, gr_path=gr_path, invoice_path=invoice_path, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="ap-three-way-match")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "ap-three-way-match",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload if payload is not None else (invoice_path if invoice_path is not None else data),
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    fx_rates = {str(k).upper(): (_to_opt_float(v) if _to_opt_float(v) is not None else 1.0) for k, v in _as_dict(data.get("fx_rates"), {"USD": 1.0}).items()}
    decimals_map = {str(k).upper(): (_to_opt_int(v) if _to_opt_int(v) is not None else 2) for k, v in _as_dict(data.get("decimal_places")).items()}
    price_tol_pct = _to_float(cfg.get("price_tolerance_pct"), 0.02)
    price_tol_abs = _to_float(cfg.get("price_tolerance_abs"), 500.0)
    qty_tol_pct = _to_float(cfg.get("qty_tolerance_pct"), 0.0)
    dup_window_days = _to_int(cfg.get("duplicate_date_window_days"), 3)

    po_index: dict[tuple[str, str], dict[str, Any]] = {}
    for po in _as_list(data.get("purchase_orders")):
        key = (str(po.get("po_number", "")).strip(), str(po.get("line_item", "10")).strip())
        curr = str(po.get("currency") or "USD").upper()
        _, unit_usd = _normalize_amount(
            _to_float(po.get("unit_price"), 0.0),
            curr,
            sap_raw_encoding=_to_bool(po.get("sap_raw_encoding"), False),
            shkzg=po.get("shkzg"),
            decimals_map=decimals_map,
            fx_rates=fx_rates,
        )
        po_index[key] = {
            "po_number": key[0],
            "line_item": key[1],
            "vendor_id": str(po.get("vendor_id") or "").strip(),
            "ordered_qty": _to_float(po.get("ordered_qty"), 0.0),
            "po_unit_price_usd": unit_usd,
            "currency": curr,
        }

    gr_index: dict[tuple[str, str], float] = {}
    for gr in _as_list(data.get("goods_receipts")):
        key = (str(gr.get("po_number", "")).strip(), str(gr.get("line_item", "10")).strip())
        qty = _to_float(gr.get("received_qty"), 0.0)
        if str(gr.get("shkzg") or "").strip().upper() == "H":
            qty = -abs(qty)
        gr_index[key] = gr_index.get(key, 0.0) + qty

    # Pre-scan invoices for exact and fuzzy duplicates
    seen_exact: dict[tuple[str, str], list[str]] = {}
    seen_fuzzy: list[tuple[str, str, float, date | None]] = []
    normalized_invoices: list[dict[str, Any]] = []

    for idx, inv in enumerate(_as_list(data.get("invoices"))):
        inv_id = str(inv.get("invoice_id") or f"INV-{idx + 1}")
        inv_num = str(inv.get("invoice_number") or inv_id).strip()
        vendor_id = str(inv.get("vendor_id") or "UNKNOWN").strip()
        curr = str(inv.get("currency") or "USD").upper()
        shkzg = inv.get("shkzg")
        raw_encoding = _to_bool(inv.get("sap_raw_encoding"), False)
        qty = _to_float(inv.get("invoiced_qty"), 0.0)
        raw_unit = _to_float(inv.get("unit_price"), 0.0)
        raw_tax = _to_float(inv.get("tax_amount"), 0.0)

        local_unit, unit_usd = _normalize_amount(
            raw_unit,
            curr,
            sap_raw_encoding=raw_encoding,
            shkzg=shkzg,
            decimals_map=decimals_map,
            fx_rates=fx_rates,
        )
        local_tax, tax_usd = _normalize_amount(
            raw_tax,
            curr,
            sap_raw_encoding=raw_encoding,
            shkzg=shkzg,
            decimals_map=decimals_map,
            fx_rates=fx_rates,
        )
        line_total_usd = (qty * unit_usd) + tax_usd
        is_credit = (str(inv.get("doc_type") or "").upper() == "CREDIT_MEMO") or (str(shkzg or "").upper() == "H")

        dt_str = str(inv.get("invoice_date") or "").strip()
        inv_dt = _safe_date(dt_str)

        if not is_credit:
            seen_exact.setdefault((vendor_id, inv_num.upper()), []).append(inv_id)
            seen_fuzzy.append((inv_id, vendor_id, round(line_total_usd, 2), inv_dt))

        normalized_invoices.append(
            {
                "raw": inv,
                "inv_id": inv_id,
                "inv_num": inv_num,
                "vendor_id": vendor_id,
                "currency": curr,
                "shkzg": shkzg,
                "is_credit": is_credit,
                "qty": qty,
                "local_unit_price": local_unit,
                "unit_usd": unit_usd,
                "tax_usd": tax_usd,
                "line_total_usd": line_total_usd,
                "inv_date": inv_dt,
            }
        )

    matches: list[dict[str, Any]] = []
    for item in normalized_invoices:
        raw = item["raw"]
        inv_id = item["inv_id"]
        vendor_id = item["vendor_id"]
        po_key = (str(raw.get("po_number", "")).strip(), str(raw.get("line_item", "10")).strip())
        exceptions: list[str] = []

        if item["is_credit"]:
            matches.append(
                {
                    "invoice_id": inv_id,
                    "vendor_id": vendor_id,
                    "po_number": po_key[0],
                    "currency": item["currency"],
                    "normalized_amount_usd": round(item["line_total_usd"], 2),
                    "match_status": "CREDIT_MEMO_POSTED",
                    "exceptions": ["SAP SHKZG='H' credit memo normalized cleanly."],
                    "payment_hold": False,
                }
            )
            continue

        # Fraud / Bank Change Hold
        if _to_bool(raw.get("bank_account_changed"), False):
            exceptions.append("FRAUD_HOLD_BANK_CHANGE: Unverified vendor remittance/bank modification request.")

        # Duplicate detection (exact + fuzzy date window)
        exact_dups = _as_list(seen_exact.get((vendor_id, item["inv_num"].upper())))
        if len(exact_dups) > 1 and exact_dups[0] != inv_id:
            exceptions.append(f"DUPLICATE_SUSPECT_EXACT: Matches {exact_dups[0]} on vendor+invoice_number.")
        else:
            for other_id, o_vend, o_amt, o_dt in seen_fuzzy:
                if other_id == inv_id or o_vend != vendor_id:
                    continue
                if abs(o_amt - round(item["line_total_usd"], 2)) < 0.05:
                    if item["inv_date"] and o_dt and abs((item["inv_date"] - o_dt).days) <= dup_window_days:
                        exceptions.append(
                            f"DUPLICATE_SUSPECT_FUZZY: Same vendor/amount within {dup_window_days}d of {other_id}."
                        )
                        break

        po_rec = po_index.get(po_key)
        gr_qty = gr_index.get(po_key)
        price_variance_usd = 0.0
        qty_variance = 0.0

        if not po_rec:
            exceptions.append("MISSING_PO: No matching purchase order line found.")
        else:
            if po_rec["vendor_id"] and po_rec["vendor_id"] != vendor_id:
                exceptions.append(f"VENDOR_MISMATCH: Invoice vendor {vendor_id} != PO vendor {po_rec['vendor_id']}.")
            if gr_qty is None:
                exceptions.append("MISSING_GRN: No goods receipt posted for PO line (absent is not clean).")
            else:
                max_allowed_qty = min(po_rec["ordered_qty"], gr_qty) * (1.0 + qty_tol_pct)
                qty_variance = item["qty"] - min(po_rec["ordered_qty"], gr_qty)
                if item["qty"] > max_allowed_qty + 1e-6:
                    exceptions.append(
                        f"QTY_VARIANCE: Invoiced {item['qty']} exceeds received/ordered {min(po_rec['ordered_qty'], gr_qty)}."
                    )

            unit_diff = abs(item["unit_usd"] - po_rec["po_unit_price_usd"])
            price_variance_usd = (item["unit_usd"] - po_rec["po_unit_price_usd"]) * item["qty"]
            pct_diff = (unit_diff / po_rec["po_unit_price_usd"]) if po_rec["po_unit_price_usd"] > 0 else 0.0
            if pct_diff > price_tol_pct or abs(price_variance_usd) > price_tol_abs:
                exceptions.append(
                    f"PRICE_VARIANCE: Delta ${price_variance_usd:,.2f} ({pct_diff * 100:.2f}%) breaches "
                    f"tolerance ({price_tol_pct * 100:.1f}% / ${price_tol_abs:,.0f})."
                )

        if any(e.startswith("FRAUD_HOLD") for e in exceptions):
            status = "FRAUD_HOLD"
        elif any(e.startswith("DUPLICATE_SUSPECT") for e in exceptions):
            status = "DUPLICATE_BLOCK"
        elif exceptions:
            status = "EXCEPTION_HOLD"
        else:
            status = "MATCHED_READY_FOR_HITL"

        matches.append(
            {
                "invoice_id": inv_id,
                "vendor_id": vendor_id,
                "po_number": po_key[0],
                "currency": item["currency"],
                "normalized_amount_usd": round(item["line_total_usd"], 2),
                "price_variance_usd": round(price_variance_usd, 2),
                "qty_variance": round(qty_variance, 2),
                "match_status": status,
                "exceptions": exceptions,
                "payment_hold": status != "MATCHED_READY_FOR_HITL",
            }
        )

    held = [m for m in matches if m["payment_hold"]]
    return {
        "skill": "ap-three-way-match",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "invoices_evaluated": len(matches),
            "matched_count": sum(1 for m in matches if m["match_status"] == "MATCHED_READY_FOR_HITL"),
            "credit_memo_count": sum(1 for m in matches if m["match_status"] == "CREDIT_MEMO_POSTED"),
            "exception_hold_count": len(held),
            "fraud_or_duplicate_holds": sum(
                1 for m in matches if m["match_status"] in {"FRAUD_HOLD", "DUPLICATE_BLOCK"}
            ),
            "held_value_usd": round(sum(m["normalized_amount_usd"] for m in held), 2),
            "matched_value_usd": round(
                sum(m["normalized_amount_usd"] for m in matches if m["match_status"] == "MATCHED_READY_FOR_HITL"), 2
            ),
        },
        "reconciliation_results": matches,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(matches)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# AP 3-Way Match Reconciliation Report",
            "",
            f"- **Invoices Evaluated:** {s['invoices_evaluated']} | **Matched:** {s['matched_count']} | "
            f"**Held Exceptions:** {s['exception_hold_count']} (Fraud/Duplicate: {s['fraud_or_duplicate_holds']})",
            f"- **Matched Value:** ${s['matched_value_usd']:,.2f} | **Held Value:** ${s['held_value_usd']:,.2f}",
            "",
            "| Invoice | Vendor | PO | Currency | Amount (USD) | Status | Exceptions |",
            "| :--- | :--- | :--- | :--- | ---: | :--- | :--- |",
        ]
    )
    for m in result["reconciliation_results"]:
        ex_str = "; ".join(m["exceptions"]) or "Clean 3-way match"
        lines.append(
            f"| `{m['invoice_id']}` | `{m['vendor_id']}` | `{m['po_number']}` | {m['currency']} | "
            f"${m['normalized_amount_usd']:,.2f} | `{m['match_status']}` | {ex_str} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile PO, Goods Receipt, and Vendor Invoices (3-way match).")
    parser.add_argument("--input", type=Path, help="Combined JSON payload with purchase_orders, goods_receipts, invoices")
    parser.add_argument("--po", type=Path, help="Optional separate PO JSON/CSV file")
    parser.add_argument("--gr", type=Path, help="Optional separate Goods Receipt JSON/CSV file")
    parser.add_argument("--invoice", type=Path, help="Optional separate Invoice JSON/CSV file")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.input is None and args.invoice is None and args.po is None and args.gr is None:
        parser.error("Provide either --input or --po/--gr/--invoice files.")
    if args.inspect and _ENTERPRISE_IO is not None:
        if args.input is not None:
            inspect_target: Any = args.input
        else:
            inspect_target = {}
            if args.po is not None:
                inspect_target["purchase_orders"] = _read_table(args.po, sheet=args.sheet, column_map=args.column_map)
            if args.gr is not None:
                inspect_target["goods_receipts"] = _read_table(args.gr, sheet=args.sheet, column_map=args.column_map)
            if args.invoice is not None:
                inspect_target["invoices"] = _read_table(args.invoice, sheet=args.sheet, column_map=args.column_map)
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            inspect_target,
            skill_id="ap-three-way-match",
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        out = json.dumps(diag, indent=2, default=str)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0
    if not args.inspect and args.input is None and args.invoice is None:
        parser.error("Provide either --input or --po/--gr/--invoice files.")
    result = analyze(args.input, config=args.config, po_path=args.po, gr_path=args.gr, invoice_path=args.invoice, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
