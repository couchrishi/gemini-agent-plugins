#!/usr/bin/env python3
"""Checks E2B ICSR 4 minimum safety criteria, computes statutory reporting clocks, and detects raw PHI."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "fatal_lt_susar_days": 7,
    "serious_unexpected_days": 15,
    "periodic_report_days": 90,
}

PHI_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "Email"),
    (re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"), "Phone"),
]


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
                skill_id="pharmacovigilance-safety-intake",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"cases": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="pharmacovigilance-safety-intake", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"cases": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"cases": loaded}
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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="pharmacovigilance-safety-intake")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "pharmacovigilance-safety-intake",
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

    d_fatal = _to_int(cfg.get("fatal_lt_susar_days"), 7)
    d_serious = _to_int(cfg.get("serious_unexpected_days"), 15)
    d_periodic = _to_int(cfg.get("periodic_report_days"), 90)

    cases = _as_list(data.get("cases"))
    evaluations: list[dict[str, Any]] = []

    for c in cases:
        cid = str(c.get("case_id") or "ICSR-1")
        patient_ok = bool(str(c.get("patient_identifier") or "").strip())
        reporter_ok = bool(str(c.get("reporter_qualification") or "").strip())
        drug_ok = bool(str(c.get("suspect_drug") or "").strip())
        ae_ok = bool(str(c.get("adverse_event_term") or "").strip())

        missing_criteria: list[str] = []
        if not patient_ok:
            missing_criteria.append("Identifiable Patient")
        if not reporter_ok:
            missing_criteria.append("Identifiable Reporter")
        if not drug_ok:
            missing_criteria.append("Suspect Medicinal Product")
        if not ae_ok:
            missing_criteria.append("Adverse Event / MedDRA Term")

        narrative = str(c.get("narrative") or "")
        phi_hits = [label for pat, label in PHI_PATTERNS if pat.search(narrative)]

        aware_dt = _parse_date(c.get("awareness_date"))
        is_fatal_lt = _to_bool(c.get("is_fatal_or_life_threatening"), False)
        is_serious = _to_bool(c.get("is_serious"), False) or is_fatal_lt
        expectedness = str(c.get("expectedness") or "expected").lower().strip()

        if is_fatal_lt and expectedness == "unexpected":
            sla_days = d_fatal
            sla_class = "7-Day Fatal/LT SUSAR"
        elif is_serious and expectedness == "unexpected":
            sla_days = d_serious
            sla_class = "15-Day Expedited SUSAR"
        else:
            sla_days = d_periodic
            sla_class = "90-Day Periodic PBRER"

        if aware_dt:
            due_dt = aware_dt + timedelta(days=sla_days)
            days_left = (due_dt - as_of).days
            due_str = due_dt.isoformat()
        else:
            due_str = None
            days_left = None

        valid_icsr = len(missing_criteria) == 0
        if phi_hits:
            intake_state = "PHI_REDACTION_REQUIRED"
        elif not valid_icsr:
            intake_state = "INCOMPLETE_FOLLOWUP_REQUIRED"
        elif days_left is not None and days_left < 0:
            intake_state = "REGULATORY_SLA_OVERDUE"
        elif days_left is not None and days_left <= 3:
            intake_state = "EXPEDITED_SIGN_OFF_URGENT"
        else:
            intake_state = "READY_FOR_PV_SIGN_OFF"

        evaluations.append(
            {
                "case_id": cid,
                "valid_4_ich_criteria": valid_icsr,
                "missing_ich_criteria": missing_criteria,
                "phi_detected": phi_hits,
                "reporting_class": sla_class,
                "awareness_date": aware_dt.isoformat() if aware_dt else None,
                "regulatory_due_date": due_str,
                "days_remaining": days_left,
                "intake_status": intake_state,
            }
        )

    return {
        "skill": "pharmacovigilance-safety-intake",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "cases_screened": len(evaluations),
            "valid_icsr_count": sum(1 for e in evaluations if e["valid_4_ich_criteria"]),
            "phi_redaction_alerts": sum(1 for e in evaluations if e["phi_detected"]),
            "urgent_or_overdue_count": sum(
                1 for e in evaluations if e["intake_status"] in {"REGULATORY_SLA_OVERDUE", "EXPEDITED_SIGN_OFF_URGENT"}
            ),
        },
        "icsr_evaluations": evaluations,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
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
            f"# Pharmacovigilance E2B ICSR Completeness & SLA Watch (As Of {result['as_of_date']})",
            "",
            f"- **Cases Screened:** {s['cases_screened']} | **Valid 4-Criteria ICSRs:** {s['valid_icsr_count']} | "
            f"**PHI Redaction Alerts:** {s['phi_redaction_alerts']} | **Urgent/Overdue:** {s['urgent_or_overdue_count']}",
            "",
            "| Case ID | Valid 4-ICH | Reporting Class | Due Date | Days Left | PHI Alerts | Status |",
            "| :--- | :--- | :--- | :--- | ---: | :--- | :--- |",
        ]
    )
    for e in result["icsr_evaluations"]:
        lines.append(
            f"| `{e['case_id']}` | {'YES' if e['valid_4_ich_criteria'] else 'NO'} | {e['reporting_class']} | "
            f"{e['regulatory_due_date'] or 'MISSING'} | {e['days_remaining'] if e['days_remaining'] is not None else '—'} | "
            f"{', '.join(e['phi_detected']) or 'Clean'} | `{e['intake_status']}` |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate E2B ICSR criteria, reporting SLAs, and PHI redaction.")
    parser.add_argument("--input", required=True, type=Path, help="Path to safety cases JSON")
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
            skill_id="pharmacovigilance-safety-intake",
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
