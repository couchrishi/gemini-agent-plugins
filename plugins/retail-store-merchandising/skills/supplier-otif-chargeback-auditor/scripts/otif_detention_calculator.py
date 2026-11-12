#!/usr/bin/env python3
"""Computes supplier OTIF (On-Time In-Full), exclusion rules, chargebacks, and detention fees."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "target_otif_pct": 95.0,
    "in_full_tolerance_pct": 98.0,
    "on_time_grace_minutes": 30,
    "late_chargeback_pct": 3.0,
    "short_ship_chargeback_pct": 5.0,
    "free_dwell_minutes": 120,
    "detention_rate_per_hour_usd": 75.0,
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
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            return _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="supplier-otif-chargeback-auditor",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"po_deliveries": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="supplier-otif-chargeback-auditor", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"po_deliveries": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"po_deliveries": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_iso(ts: Any) -> datetime | None:
    return _safe_datetime(ts)


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="supplier-otif-chargeback-auditor")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "supplier-otif-chargeback-auditor",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    deliveries = data.get("po_deliveries") or data.get("deliveries") or []
    grace_mins = _to_int(cfg.get("on_time_grace_minutes"), 30)
    in_full_thresh = _to_float(cfg.get("in_full_tolerance_pct"), 98.0)
    late_cb_pct = _to_float(cfg.get("late_chargeback_pct"), 3.0)
    short_cb_pct = _to_float(cfg.get("short_ship_chargeback_pct"), 5.0)
    free_dwell = _to_int(cfg.get("free_dwell_minutes"), 120)
    det_rate = _to_float(cfg.get("detention_rate_per_hour_usd"), 75.0)
    target_otif = _to_float(cfg.get("target_otif_pct"), 95.0)

    vendor_rollup: dict[str, dict[str, Any]] = {}
    evaluated_pos: list[dict[str, Any]] = []
    trunc_warnings: list[str] = []
    if data.get("truncated"):
        trunc_warnings.append("WMS dock receipt feed truncated; supplier OTIF and chargeback totals are partial.")

    for po in deliveries:
        po_id = str(po.get("po_number") or "PO-1")
        vid = str(po.get("vendor_id") or "VEND-1")
        vname = str(po.get("vendor_name") or vid)
        po_val = _to_float(po.get("po_value_usd"), 0.0)
        ordered = _to_int(po.get("ordered_units"), 0)
        received = _to_int(po.get("received_units"), 0)
        short_val = max(0.0, (_to_float(po.get("short_shipped_value_usd")) or max(0, ordered - received) * (po_val / ordered if ordered else 0.0)))

        appt_dt = _parse_iso(po.get("appointment_time"))
        arr_dt = _parse_iso(po.get("arrival_time"))
        dep_dt = _parse_iso(po.get("departure_time"))

        excl_reason = str(po.get("exclusion_reason") or "").strip()
        late_minutes = 0
        dwell_minutes = _to_int(po.get("dwell_minutes"), 0)
        if appt_dt and arr_dt:
            late_minutes = int((arr_dt - appt_dt).total_seconds() // 60)
        if arr_dt and dep_dt and not po.get("dwell_minutes"):
            dwell_minutes = max(0, int((dep_dt - arr_dt).total_seconds() // 60))

        on_time = (late_minutes <= grace_mins) or (excl_reason in {"WEATHER_FORCE_MAJEURE", "BUYER_RESCHEDULED"})
        fill_pct = (received / ordered * 100.0) if ordered > 0 else 100.0
        in_full = (fill_pct >= in_full_thresh) or (excl_reason == "BUYER_CANCELED_LINE")
        otif_pass = on_time and in_full

        late_cb = round(po_val * (late_cb_pct / 100.0), 2) if not on_time else 0.0
        short_cb = round(short_val * (short_cb_pct / 100.0), 2) if not in_full else 0.0

        # Standard routing rule: late carriers forfeit free-time detention eligibility
        detention_fee = 0.0
        if on_time and dwell_minutes > free_dwell:
            billable_hours = (dwell_minutes - free_dwell) / 60.0
            detention_fee = round(billable_hours * det_rate, 2)

        v = vendor_rollup.setdefault(
            vid,
            {
                "vendor_id": vid,
                "vendor_name": vname,
                "po_count": 0,
                "otif_pass_count": 0,
                "total_po_value_usd": 0.0,
                "chargeback_usd": 0.0,
                "detention_exposure_usd": 0.0,
            },
        )
        v["po_count"] += 1
        if otif_pass:
            v["otif_pass_count"] += 1
        v["total_po_value_usd"] = round(v["total_po_value_usd"] + po_val, 2)
        v["chargeback_usd"] = round(v["chargeback_usd"] + late_cb + short_cb, 2)
        v["detention_exposure_usd"] = round(v["detention_exposure_usd"] + detention_fee, 2)

        evaluated_pos.append(
            {
                "po_number": po_id,
                "vendor_id": vid,
                "on_time": on_time,
                "late_minutes": late_minutes,
                "fill_pct": round(fill_pct, 2),
                "in_full": in_full,
                "otif_pass": otif_pass,
                "exclusion_reason": excl_reason or None,
                "late_chargeback_usd": late_cb,
                "short_chargeback_usd": short_cb,
                "detention_fee_usd": detention_fee,
            }
        )

    vendors_out: list[dict[str, Any]] = []
    for v in vendor_rollup.values():
        otif_pct = round(v["otif_pass_count"] / v["po_count"] * 100.0, 2) if v["po_count"] else 0.0
        v["otif_pct"] = otif_pct
        v["meets_sla"] = otif_pct >= target_otif
        v["net_recovery_usd"] = round(v["chargeback_usd"] - v["detention_exposure_usd"], 2)
        vendors_out.append(v)

    vendors_out.sort(key=lambda x: -x["chargeback_usd"])
    total_cb = round(sum(v["chargeback_usd"] for v in vendors_out), 2)
    total_det = round(sum(v["detention_exposure_usd"] for v in vendors_out), 2)
    overall_otif = round(
        sum(1 for p in evaluated_pos if p["otif_pass"]) / len(evaluated_pos) * 100.0, 2
    ) if evaluated_pos else 0.0

    return {
        "skill": "supplier-otif-chargeback-auditor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "po_deliveries_audited": len(evaluated_pos),
            "overall_otif_pct": overall_otif,
            "target_otif_pct": target_otif,
            "total_chargebacks_usd": total_cb,
            "total_detention_exposure_usd": total_det,
            "net_vendor_recovery_usd": round(total_cb - total_det, 2),
        },
        "vendor_scorecards": vendors_out,
        "po_details": evaluated_pos,
        "truncation_warnings": _collect_truncation_warnings(data, count=None, existing=trunc_warnings),
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
            "# Supplier OTIF, Chargeback & Detention Settlement Audit",
            "",
            f"- **Deliveries Audited:** {s['po_deliveries_audited']} | **Overall OTIF:** {s['overall_otif_pct']:.1f}% (Target {s['target_otif_pct']:.1f}%) | "
            f"**Total Chargebacks:** ${s['total_chargebacks_usd']:,.2f} | **Detention Exposure:** ${s['total_detention_exposure_usd']:,.2f}",
            "",
            "| Vendor | POs | OTIF % | Chargebacks | Detention Payable | Net Recovery | SLA |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for v in result["vendor_scorecards"]:
        lines.append(
            f"| `{v['vendor_id']}` {v['vendor_name']} | {v['po_count']} | {v['otif_pct']:.1f}% | "
            f"${v['chargeback_usd']:,.2f} | ${v['detention_exposure_usd']:,.2f} | ${v['net_recovery_usd']:,.2f} | "
            f"{'PASS' if v['meets_sla'] else 'BREACH'} |"
        )
    lines.extend(["", "Draft debit memos require HITL vendor-ops sign-off before posting to ERP AP."])
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit supplier OTIF compliance, chargebacks, and carrier detention.")
    parser.add_argument("--input", required=True, type=Path, help="Path to PO dock delivery JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="supplier-otif-chargeback-auditor",
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
    result = analyze(args.input, config=args.config, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
