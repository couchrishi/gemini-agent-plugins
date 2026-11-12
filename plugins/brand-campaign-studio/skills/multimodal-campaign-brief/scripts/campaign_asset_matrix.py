#!/usr/bin/env python3
"""Builds multimodal campaign deliverable matrices, identifies funnel/audience gaps, and validates launch readiness."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "required_funnel_stages": ["Awareness", "Consideration", "Conversion"],
    "min_production_buffer_days": 5,
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
                skill_id="multimodal-campaign-brief",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"deliverables": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="multimodal-campaign-brief", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"deliverables": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"deliverables": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return _safe_date(s)


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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="multimodal-campaign-brief")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "multimodal-campaign-brief",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    campaign_name = str(data.get("campaign_name") or "Q4 Integrated Campaign")
    budget_cap = _to_float(data.get("total_budget_usd"), 0.0)
    launch_dt = _parse_date(data.get("launch_date")) or date(2026, 12, 1)
    audiences = [str(a) for a in _as_list(data.get("target_audiences"))]
    channels = [str(c) for c in _as_list(data.get("channels"))]
    req_stages = [str(s) for s in cfg.get("required_funnel_stages", DEFAULT_CONFIG["required_funnel_stages"])]
    buffer_days = _to_int(cfg.get("min_production_buffer_days"), 5)

    deliverables = _as_list(data.get("deliverables"))
    covered_cells: set[tuple[str, str]] = set()
    covered_aud_stage: set[tuple[str, str]] = set()
    planned_spend = 0.0
    late_assets: list[dict[str, Any]] = []
    ready_cnt = 0

    for d in deliverables:
        did = str(d.get("asset_id") or "DELIV-1")
        aud = str(d.get("audience") or "")
        ch = str(d.get("channel") or "")
        stg = str(d.get("funnel_stage") or "")
        cost = _to_float(d.get("estimated_cost_usd"), 0.0)
        status = str(d.get("status") or "PLANNED").upper()
        due_dt = _parse_date(d.get("due_date"))

        planned_spend += cost
        if aud and ch:
            covered_cells.add((aud, ch))
        if aud and stg:
            covered_aud_stage.add((aud, stg))
        if status == "APPROVED":
            ready_cnt += 1
        if due_dt is not None and (launch_dt - due_dt).days < buffer_days:
            late_assets.append(
                {
                    "asset_id": did,
                    "due_date": due_dt.isoformat(),
                    "buffer_days_remaining": (launch_dt - due_dt).days,
                }
            )

    missing_channel_cells = [
        {"audience": a, "channel": c}
        for a in audiences
        for c in channels
        if (a, c) not in covered_cells
    ]
    missing_funnel_cells = [
        {"audience": a, "funnel_stage": st}
        for a in audiences
        for st in req_stages
        if (a, st) not in covered_aud_stage
    ]

    budget_delta = planned_spend - budget_cap if budget_cap > 0 else 0.0
    over_budget = budget_cap > 0 and planned_spend > budget_cap

    if over_budget or late_assets or missing_channel_cells:
        readiness = "LAUNCH_AT_RISK_GAPS_PRESENT"
    elif missing_funnel_cells:
        readiness = "PARTIAL_FUNNEL_COVERAGE"
    else:
        readiness = "BRIEF_LOCKED_FOR_PRODUCTION"

    return {
        "skill": "multimodal-campaign-brief",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "campaign_name": campaign_name,
        "launch_date": launch_dt.isoformat(),
        "summary": {
            "deliverable_count": len(deliverables),
            "approved_deliverables": ready_cnt,
            "total_budget_usd": round(budget_cap, 2),
            "planned_spend_usd": round(planned_spend, 2),
            "budget_variance_usd": round(budget_delta, 2),
            "over_budget": over_budget,
            "missing_audience_channel_cells": len(missing_channel_cells),
            "missing_funnel_stage_cells": len(missing_funnel_cells),
            "late_critical_path_assets": len(late_assets),
            "campaign_readiness": readiness,
        },
        "missing_channel_cells": missing_channel_cells,
        "missing_funnel_cells": missing_funnel_cells,
        "late_assets": late_assets,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(deliverables)),
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
            f"# Multimodal Campaign Matrix — {result['campaign_name']} (Launch {result['launch_date']})",
            "",
            f"- **Readiness:** `{s['campaign_readiness']}` | **Deliverables:** {s['deliverable_count']} (Approved: {s['approved_deliverables']})",
            f"- **Planned Spend:** ${s['planned_spend_usd']:,.2f} vs **Budget:** ${s['total_budget_usd']:,.2f} "
            f"(Var: ${s['budget_variance_usd']:+,.2f})",
            f"- **Matrix Gaps:** {s['missing_audience_channel_cells']} Audience×Channel | "
            f"{s['missing_funnel_stage_cells']} Funnel Stage | **Late Assets (< buffer):** {s['late_critical_path_assets']}",
        ]
    )
    if result["missing_channel_cells"]:
        lines.extend(["", "## Missing Audience × Channel Coverage"])
        for g in result["missing_channel_cells"]:
            lines.append(f"- `{g['audience']}` × `{g['channel']}`")
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate campaign brief asset matrix, budget, and launch buffers.")
    parser.add_argument("--input", required=True, type=Path, help="Path to campaign brief JSON")
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
            skill_id="multimodal-campaign-brief",
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
