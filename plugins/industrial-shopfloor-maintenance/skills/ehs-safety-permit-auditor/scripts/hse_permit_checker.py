#!/usr/bin/env python3
"""Audits EHS Permit-to-Work (PTW) packages for LOTO isolation, gas test limits, and worker certification."""

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
    "o2_min_pct": 19.5,
    "o2_max_pct": 23.5,
    "max_lel_pct": 0.0,
    "max_gas_test_age_mins": 60,
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
                skill_id="ehs-safety-permit-auditor",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"permits": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="ehs-safety-permit-auditor", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"permits": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"permits": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return _safe_date(s)


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,

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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="ehs-safety-permit-auditor")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "ehs-safety-permit-auditor",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)

    o2_min = _to_float(cfg.get("o2_min_pct"), 19.5)
    o2_max = _to_float(cfg.get("o2_max_pct"), 23.5)
    max_lel = _to_float(cfg.get("max_lel_pct"), 0.0)
    max_gas_age = _to_int(cfg.get("max_gas_test_age_mins"), 60)

    permits = _as_list(data.get("permits"))
    audits: list[dict[str, Any]] = []

    for p in permits:
        pid = str(p.get("permit_id") or "PTW-1")
        wtype = str(p.get("work_type") or "general").lower().strip()
        work_dt = _parse_date(p.get("work_date")) or as_of
        cert_exp = _parse_date(p.get("worker_cert_valid_until"))
        issuer_signed = _to_bool(p.get("issuer_signed"), False)
        loto = p.get("loto_isolated")

        stop_work_reasons: list[str] = []
        if not issuer_signed:
            stop_work_reasons.append("Area Authority / Issuer signature missing.")
        if cert_exp is None or cert_exp < work_dt:
            stop_work_reasons.append(f"Worker safety certification missing or expired ({cert_exp}).")

        if wtype in {"confined_space", "high_voltage"} and loto is not True:
            stop_work_reasons.append(f"Mandatory Lockout/Tagout (LOTO) verification missing for {wtype}.")

        if wtype == "confined_space":
            o2 = _to_opt_float(p.get("gas_test_o2_pct"))
            lel = _to_opt_float(p.get("gas_test_lel_pct"))
            age = _to_opt_int(p.get("gas_test_age_mins"))
            if o2 is None or lel is None or age is None:
                stop_work_reasons.append("Mandatory atmospheric gas test fields missing (absent != safe).")
            else:
                if not (o2_min <= float(o2) <= o2_max):
                    stop_work_reasons.append(f"Unsafe O2 level {o2}% (must be {o2_min}%-{o2_max}%).")
                if float(lel) > max_lel:
                    stop_work_reasons.append(f"Flammable LEL {lel}% exceeds {max_lel}% limit.")
                if int(age) > max_gas_age:
                    stop_work_reasons.append(f"Gas test age {age}m exceeds {max_gas_age}m recency limit.")

        if wtype == "hot_work" and not _to_bool(p.get("fire_watch_assigned"), False):
            stop_work_reasons.append("Dedicated Fire Watch not assigned for hot work.")

        status = "STOP_WORK_BLOCKED" if stop_work_reasons else "ELIGIBLE_FOR_EHS_ISSUE"
        audits.append(
            {
                "permit_id": pid,
                "facility": str(p.get("facility") or "Plant"),
                "work_type": wtype,
                "permit_status": status,
                "stop_work_reasons": stop_work_reasons,
            }
        )

    return {
        "skill": "ehs-safety-permit-auditor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "permits_audited": len(audits),
            "stop_work_blocked_count": sum(1 for a in audits if a["permit_status"] == "STOP_WORK_BLOCKED"),
            "eligible_count": sum(1 for a in audits if a["permit_status"] == "ELIGIBLE_FOR_EHS_ISSUE"),
        },
        "permit_audits": audits,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(audits)),
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
            f"# EHS Permit-to-Work (PTW) & LOTO Safety Audit (As Of {result['as_of_date']})",
            "",
            f"- **Permits Audited:** {s['permits_audited']} | **STOP WORK Blocked:** {s['stop_work_blocked_count']} | "
            f"**Eligible for EHS Sign-Off:** {s['eligible_count']}",
            "",
            "| Permit | Facility | Work Type | Status | Safety Defects |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for a in result["permit_audits"]:
        notes = "; ".join(a["stop_work_reasons"]) or "All mandatory checks verified"
        lines.append(f"| `{a['permit_id']}` | {a['facility']} | `{a['work_type']}` | `{a['permit_status']}` | {notes} |")
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit EHS Permit-to-Work packages for LOTO and gas safety.")
    parser.add_argument("--input", required=True, type=Path, help="Path to permits JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--as-of", type=str, help="Reference ISO date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="ehs-safety-permit-auditor",
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
    result = analyze(args.input, config=args.config, as_of_date=args.as_of, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
