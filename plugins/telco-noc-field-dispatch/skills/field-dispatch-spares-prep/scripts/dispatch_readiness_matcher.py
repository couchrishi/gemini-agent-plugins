#!/usr/bin/env python3
"""Validates field technician certifications, depot/van spare parts availability, and dispatch readiness."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "enforce_safety_cert_expiry": True,
    "require_all_spares_reserved": True,
    "min_sla_buffer_hours": 1.0,
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
                skill_id="field-dispatch-spares-prep",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"work_orders": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="field-dispatch-spares-prep", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"work_orders": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"work_orders": loaded}
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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="field-dispatch-spares-prep")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "field-dispatch-spares-prep",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    dispatch_date_str = str(data.get("dispatch_date") or "2026-10-15")
    dispatch_dt = _safe_date(dispatch_date_str) or date(2026, 11, 10)
    techs = data.get("technicians") or []
    depot_stock = {str(k): _to_int(v) for k, v in (data.get("depot_spares_qty") or {}).items()}
    work_orders = data.get("work_orders") or []
    enforce_certs = _to_bool(cfg.get("enforce_safety_cert_expiry"), True)

    evaluated: list[dict[str, Any]] = []
    for wo in work_orders:
        wo_id = str(wo.get("work_order_id") or "WO-1")
        site = str(wo.get("site_id") or "SITE-1")
        req_skills = set(wo.get("required_skills") or [])
        req_certs = list(wo.get("required_safety_certs") or [])
        req_spares = wo.get("required_spares") or {}

        missing_spares: list[str] = []
        for sku, qty in req_spares.items():
            if depot_stock.get(str(sku), 0) < _to_int(qty):
                missing_spares.append(f"{sku} (need {qty}, stock {depot_stock.get(str(sku), 0)})")

        eligible_techs: list[dict[str, Any]] = []
        cert_failures: list[str] = []

        for tech in techs:
            tid = str(tech.get("tech_id") or "TECH-1")
            tskills = set(tech.get("skills") or [])
            if not req_skills.issubset(tskills):
                continue
            certs = tech.get("certifications") or {}
            expired = []
            for rc in req_certs:
                exp = certs.get(rc)
                if not exp:
                    expired.append(f"{rc} missing")
                elif enforce_certs:
                    exp_dt = _safe_date(exp)
                    if exp_dt is None or exp_dt < dispatch_dt:
                        expired.append(f"{rc} expired/invalid {exp}")
            if expired:
                cert_failures.append(f"{tid}: {', '.join(expired)}")
                continue
            eligible_techs.append(
                {
                    "tech_id": tid,
                    "name": str(tech.get("name") or tid),
                    "travel_hours": (_to_float(tech.get("estimated_travel_hours")) or 1.0),
                }
            )

        eligible_techs.sort(key=lambda t: t["travel_hours"])
        chosen = eligible_techs[0] if eligible_techs else None

        blockers: list[str] = []
        if not chosen:
            if cert_failures:
                blockers.append(f"CERT_BLOCKED ({'; '.join(cert_failures)})")
            else:
                blockers.append("NO_SKILLED_TECHNICIAN_AVAILABLE")
        if missing_spares:
            blockers.append(f"MISSING_SPARES ({', '.join(missing_spares)})")

        status = "BLOCKED" if blockers else "READY_FOR_DISPATCH"
        evaluated.append(
            {
                "work_order_id": wo_id,
                "site_id": site,
                "assigned_technician": chosen,
                "spares_ready": len(missing_spares) == 0,
                "missing_spares": missing_spares,
                "blockers": blockers,
                "dispatch_status": status,
                "hitl_truck_roll_approval_required": True,
            }
        )

    return {
        "skill": "field-dispatch-spares-prep",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "dispatch_date": dispatch_date_str,
            "work_orders_checked": len(evaluated),
            "ready_count": sum(1 for e in evaluated if e["dispatch_status"] == "READY_FOR_DISPATCH"),
            "blocked_count": sum(1 for e in evaluated if e["dispatch_status"] == "BLOCKED"),
        },
        "dispatch_plans": evaluated,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated), existing=["WMS depot inventory feed truncated; confirm physical van bin counts before roll."] if data.get("truncated") else []),
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
            f"# Field Dispatch Technician Cert & Spares Readiness ({s['dispatch_date']})",
            "",
            f"- **Work Orders:** {s['work_orders_checked']} | **Ready:** {s['ready_count']} | **Blocked:** {s['blocked_count']}",
            "",
            "| Work Order | Site | Assigned Tech | Spares Ready | Status | Blockers |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for d in result["dispatch_plans"]:
        tech = f"{d['assigned_technician']['tech_id']} ({d['assigned_technician']['name']})" if d["assigned_technician"] else "NONE"
        lines.append(
            f"| `{d['work_order_id']}` | {d['site_id']} | {tech} | {'YES' if d['spares_ready'] else 'NO'} | "
            f"`{d['dispatch_status']}` | {'; '.join(d['blockers']) or 'None'} |"
        )
    lines.extend(["", "Truck rolls and depot pick-ticket releases require HITL dispatch coordinator confirmation."])
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate technician certs, spares kit completeness, and dispatch readiness.")
    parser.add_argument("--input", required=True, type=Path, help="Path to work orders and spares JSON")
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
            skill_id="field-dispatch-spares-prep",
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
