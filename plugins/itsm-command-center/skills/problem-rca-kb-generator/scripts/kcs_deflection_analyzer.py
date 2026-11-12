#!/usr/bin/env python3
"""Mines resolved tickets for repeat Problem candidates, MTTR, L1 deflection savings, and KCS checks."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "cost_per_l1_ticket_usd": 28.0,
    "expected_kcs_deflection_rate": 0.35,
}
REQUIRED_KCS_SECTIONS = ("environment", "symptoms", "root_cause", "resolution_steps", "verification_check")


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
                skill_id="problem-rca-kb-generator",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"tickets": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="problem-rca-kb-generator", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"tickets": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"tickets": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_dt(val: Any) -> dt.datetime | None:
    if not val:
        return None
    norm = str(val).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(norm)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="problem-rca-kb-generator")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "problem-rca-kb-generator",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    tickets = data.get("tickets") or data.get("records") or []
    kcs_drafts = _as_list(data.get("kcs_drafts"))
    sample_window_days = max(1, _to_int(data.get("sample_window_days"), 90))
    unit_cost = _to_float(cfg.get("cost_per_l1_ticket_usd"), 28.0)
    deflection_rate = _to_float(cfg.get("expected_kcs_deflection_rate"), 0.35)
    metadata = _as_dict(data.get("metadata"))

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Resolved ticket sample truncated; annualized figures scaled cautiously.")

    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    open_unresolved_count = 0
    canceled_count = 0

    for t in tickets:
        state = str(t.get("state") or "").lower()
        if state in {"8", "canceled", "cancelled"}:
            canceled_count += 1
            continue
        opened = _parse_dt(t.get("opened_at"))
        resolved = _parse_dt(t.get("resolved_at"))
        if resolved is None:
            # Never treat unresolved null timestamp as 0h MTTR
            open_unresolved_count += 1
            continue
        mttr_hours = max(0.0, (resolved - opened).total_seconds() / 3600.0) if opened else _to_float(t.get("mttr_hours"), 0.0)
        cat = str(t.get("category") or "General")
        sig = str(t.get("root_cause_signature") or t.get("short_description") or "unspecified").strip().lower()
        grouped[(cat, sig)].append(mttr_hours)

    annual_factor = 365.0 / sample_window_days
    candidates: list[dict[str, Any]] = []
    total_savings = 0.0
    for (cat, sig), durations in grouped.items():
        if len(durations) < 2 and len(tickets) > 3:
            continue
        durations_sorted = sorted(durations)
        mean_mttr = round(sum(durations_sorted) / len(durations_sorted), 2)
        p90_idx = min(len(durations_sorted) - 1, max(0, math.ceil(0.9 * len(durations_sorted)) - 1))
        p90_mttr = round(durations_sorted[p90_idx], 2)
        annual_vol = round(len(durations_sorted) * annual_factor, 1)
        deflected = round(annual_vol * deflection_rate, 1)
        savings = round(deflected * unit_cost, 2)
        total_savings += savings
        candidates.append(
            {
                "category": cat,
                "root_cause_signature": sig,
                "ticket_count": len(durations_sorted),
                "mean_mttr_hours": mean_mttr,
                "p90_mttr_hours": p90_mttr,
                "estimated_annual_tickets": annual_vol,
                "estimated_annual_deflected": deflected,
                "estimated_annual_savings_usd": savings,
            }
        )

    candidates.sort(key=lambda c: c["estimated_annual_savings_usd"], reverse=True)

    kcs_validations: list[dict[str, Any]] = []
    for draft in kcs_drafts:
        missing = [sec for sec in REQUIRED_KCS_SECTIONS if not str(draft.get(sec) or "").strip()]
        kcs_validations.append(
            {
                "article_id": draft.get("article_id"),
                "title": draft.get("title"),
                "kcs_completeness_passed": len(missing) == 0,
                "missing_sections": missing,
            }
        )

    return {
        "skill": "problem-rca-kb-generator",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "total_tickets_scanned": len(tickets),
            "open_unresolved_excluded": open_unresolved_count,
            "canceled_excluded": canceled_count,
            "problem_candidate_count": len(candidates),
            "total_estimated_annual_savings_usd": round(total_savings, 2),
            "kcs_drafts_checked": len(kcs_validations),
        },
        "problem_candidates": candidates,
        "kcs_validations": kcs_validations,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(candidates), existing=warnings),
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
            "# Problem Candidate & KCS Deflection Analysis",
            "",
            f"- **Tickets Scanned:** {s['total_tickets_scanned']} (Excluded open: {s['open_unresolved_excluded']}, canceled: {s['canceled_excluded']})",
            f"- **Problem Candidates:** {s['problem_candidate_count']} | **Estimated Annual L1 Savings:** ${s['total_estimated_annual_savings_usd']:,.2f}",
            "",
            "| Category | Root Cause Signature | Count | Mean MTTR (h) | Annual Savings (USD) |",
            "| :--- | :--- | ---: | ---: | ---: |",
        ]
    )
    for c in result["problem_candidates"]:
        lines.append(
            f"| {c['category']} | {c['root_cause_signature']} | {c['ticket_count']} | "
            f"{c['mean_mttr_hours']:.2f} | ${c['estimated_annual_savings_usd']:,.2f} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Identify Problem RCA candidates and KCS deflection ROI.")
    parser.add_argument("--input", required=True, type=Path, help="Path to resolved tickets JSON or CSV")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="problem-rca-kb-generator",
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
