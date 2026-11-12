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
                skill_id="supplier-rfx-tariff-modeler",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"bids": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="supplier-rfx-tariff-modeler", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"bids": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"bids": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    tariff_shock_pct: float | None = None,

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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="supplier-rfx-tariff-modeler")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "supplier-rfx-tariff-modeler",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    demand = max(1.0, (_to_float(data.get("annual_demand_units")) or 10000))
    shock_pct = _to_float(tariff_shock_pct if tariff_shock_pct is not None else data.get("tariff_shock_pct", 0.0))
    shocked_countries = {str(c).upper() for c in _as_list(data.get("tariff_shock_countries"))}
    coc_pct = _to_float(cfg.get("annual_cost_of_capital_pct"), 8.0) / 100.0
    defect_cost = _to_float(cfg.get("defect_cost_per_unit_usd"), 45.0)

    bids = _as_list(data.get("bids"))
    models: list[dict[str, Any]] = []

    for b in bids:
        sid = str(b.get("supplier_id") or "SUP-1")
        sname = str(b.get("supplier_name") or sid)
        origin = str(b.get("origin_country") or "US").upper()
        moq = _to_int(b.get("moq_units"), 0)
        fob = _to_float(b.get("unit_fob_usd"), 0.0)
        freight = _to_float(b.get("freight_per_unit_usd"), 0.0)
        ins_pct = (_to_float(b.get("insurance_pct")) or 0.5) / 100.0
        base_tariff = _to_float(b.get("base_tariff_pct"), 0.0)
        extra_duty = _to_float(b.get("additional_duty_pct"), 0.0)
        applied_shock = shock_pct if (not shocked_countries or origin in shocked_countries) else 0.0
        total_duty_pct = (base_tariff + extra_duty + applied_shock) / 100.0

        payment_days = (_to_int(b.get("payment_days")) or 30)
        lead_days = (_to_int(b.get("lead_time_days")) or 30)
        ppm = (_to_float(b.get("quality_defect_ppm")) or 500.0)

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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(bids)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate supplier RFx landed cost under tariff and payment scenarios.")
    parser.add_argument("--input", required=True, type=Path, help="Path to RFx bids JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--tariff-shock-pct", type=float, help="Optional incremental tariff shock percentage")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="supplier-rfx-tariff-modeler",
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
    result = analyze(args.input, config=args.config, tariff_shock_pct=args.tariff_shock_pct, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
