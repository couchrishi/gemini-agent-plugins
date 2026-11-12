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
                skill_id="merchandising-assortment-planner",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"campaigns": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="merchandising-assortment-planner", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"campaigns": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"campaigns": loaded}
    return loaded if isinstance(loaded, dict) else {}


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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="merchandising-assortment-planner")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "merchandising-assortment-planner",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    campaigns = data.get("campaigns") or data.get("promotions") or []
    min_roi = _to_float(cfg.get("min_acceptable_promo_roi"), 0.15)
    min_lift = _to_float(cfg.get("min_incremental_lift_pct"), 10.0)

    trunc_warnings: list[str] = []
    if data.get("truncated"):
        trunc_warnings.append("Promotion dataset truncated; portfolio margin attribution excludes omitted SKUs.")

    evaluations: list[dict[str, Any]] = []
    for camp in campaigns:
        cid = str(camp.get("campaign_id") or "PROMO-1")
        name = str(camp.get("campaign_name") or cid)
        base_days = max(1, (_to_int(camp.get("baseline_days")) or 28))
        promo_days = max(1, (_to_int(camp.get("promo_days")) or 7))

        # Chain-denominator hygiene: normalize baseline to promo duration via daily velocity
        base_units_total = _to_float(camp.get("baseline_units"), 0.0)
        base_rev_total = _to_float(camp.get("baseline_revenue_usd"), 0.0)
        base_gm_total = _to_float(camp.get("baseline_gross_margin_usd"), 0.0)

        norm_base_units = (base_units_total / base_days) * promo_days
        norm_base_rev = (base_rev_total / base_days) * promo_days
        norm_base_gm = (base_gm_total / base_days) * promo_days

        promo_units = _to_float(camp.get("promo_units"), 0.0)
        promo_rev = _to_float(camp.get("promo_revenue_usd"), 0.0)
        promo_gm_raw = _to_float(camp.get("promo_gross_margin_usd"), 0.0)

        cannibal_gm_loss = _to_float(camp.get("sibling_cannibalization_gm_loss_usd"), 0.0)
        halo_gm_gain = _to_float(camp.get("basket_halo_gm_gain_usd"), 0.0)
        vendor_coop = _to_float(camp.get("vendor_funding_rebate_usd"), 0.0)
        promo_media_display_cost = _to_float(camp.get("promo_execution_cost_usd"), 0.0)
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze retail promo lift, halo/cannibalization, and net GM ROI.")
    parser.add_argument("--input", required=True, type=Path, help="Path to promotional telemetry JSON")
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
            skill_id="merchandising-assortment-planner",
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
