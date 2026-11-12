#!/usr/bin/env python3
"""Extracts entrypoints, DB read/write couplings, complexity hotspots, and PRD test traceability."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "complexity_hotspot_threshold": 15,
    "min_requirement_traceability_pct": 85.0,
}

ENTRYPOINT_RE = re.compile(
    r"(?:^|\s)(?:def|async\s+def|function|public\s+(?:static\s+)?[\w<>\[\]]+|PROCEDURE\s+DIVISION|@(?:app|router)\.\w+)\s*([A-Za-z_][A-Za-z0-9_./-]*)",
    re.MULTILINE,
)
SQL_READ_RE = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.]+)", re.IGNORECASE)
SQL_WRITE_RE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO)\s+([a-zA-Z0-9_.]+)", re.IGNORECASE)
BRANCH_RE = re.compile(r"\b(if|elif|else\s+if|for|while|case|catch|except|when|PERFORM)\b|&&|\|\|")


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
                skill_id="legacy-code-to-prd",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"modules": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="legacy-code-to-prd", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"modules": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"modules": loaded}
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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="legacy-code-to-prd")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "legacy-code-to-prd",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    modules = data.get("modules") or data.get("files") or []
    requirements = _as_list(data.get("requirements"))
    tests = _as_list(data.get("tests"))
    hotspot_thresh = _to_int(cfg.get("complexity_hotspot_threshold"), 15)
    min_trace_pct = _to_float(cfg.get("min_requirement_traceability_pct"), 85.0)
    metadata = _as_dict(data.get("metadata"))

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Legacy module inventory truncated; dependency graph may be incomplete.")

    module_inventory: list[dict[str, Any]] = []
    hotspots: list[dict[str, Any]] = []
    db_couplings: dict[str, dict[str, list[str]]] = {}

    for idx, mod in enumerate(modules):
        mname = str(mod.get("path") or mod.get("name") or f"module_{idx + 1}")
        code = str(mod.get("source") or mod.get("content") or "")
        explicit_cc = _to_opt_int(mod.get("cyclomatic_complexity"))
        complexity = int(explicit_cc) if explicit_cc is not None else 1 + len(BRANCH_RE.findall(code))
        entrypoints = list(mod.get("entrypoints") or ENTRYPOINT_RE.findall(code))
        reads = sorted({t.lower() for t in (mod.get("db_reads") or SQL_READ_RE.findall(code))})
        writes = sorted({t.lower() for t in (mod.get("db_writes") or SQL_WRITE_RE.findall(code))})

        for tbl in reads:
            db_couplings.setdefault(tbl, {"readers": [], "writers": []})["readers"].append(mname)
        for tbl in writes:
            db_couplings.setdefault(tbl, {"readers": [], "writers": []})["writers"].append(mname)

        is_hotspot = complexity >= hotspot_thresh
        entry = {
            "module": mname,
            "cyclomatic_complexity": complexity,
            "is_hotspot": is_hotspot,
            "entrypoints": entrypoints,
            "db_reads": reads,
            "db_writes": writes,
        }
        module_inventory.append(entry)
        if is_hotspot:
            hotspots.append(entry)

    hotspots.sort(key=lambda h: h["cyclomatic_complexity"], reverse=True)

    # Traceability matrix across requirements <-> tests <-> modules
    test_by_req: dict[str, list[str]] = {}
    for t in tests:
        tid = str(t.get("test_id") or "")
        for rid in _as_list(t.get("covers_requirements")):
            test_by_req.setdefault(str(rid), []).append(tid)

    trace_matrix: list[dict[str, Any]] = []
    covered_count = 0
    untested_critical: list[str] = []
    for idx, req in enumerate(requirements):
        rid = str(req.get("req_id") or f"REQ-{idx + 1}")
        prio = str(req.get("priority") or "medium").lower()
        linked_tests = sorted(set(_as_list(test_by_req.get(rid)) + list(_as_list(req.get("test_ids")))))
        is_covered = len(linked_tests) > 0
        if is_covered:
            covered_count += 1
        elif prio in {"critical", "high", "p0", "p1"}:
            untested_critical.append(rid)
        trace_matrix.append(
            {
                "req_id": rid,
                "title": req.get("title"),
                "priority": prio,
                "source_module": req.get("source_module"),
                "test_ids": linked_tests,
                "covered": is_covered,
            }
        )

    trace_pct = round((covered_count / len(requirements)) * 100.0, 2) if requirements else 0.0

    return {
        "skill": "legacy-code-to-prd",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "module_count": len(module_inventory),
            "hotspot_count": len(hotspots),
            "db_table_count": len(db_couplings),
            "requirement_count": len(requirements),
            "covered_requirement_count": covered_count,
            "traceability_coverage_pct": trace_pct,
            "traceability_gate_passed": trace_pct >= min_trace_pct and not untested_critical,
            "untested_critical_count": len(untested_critical),
        },
        "module_inventory": module_inventory,
        "complexity_hotspots": hotspots,
        "db_couplings": db_couplings,
        "traceability_matrix": trace_matrix,
        "untested_critical_requirements": untested_critical,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(module_inventory), existing=warnings),
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
            "# Legacy Code-to-PRD Traceability & Coupling Matrix",
            "",
            f"- **Modules Parsed:** {s['module_count']} | **Complexity Hotspots:** {s['hotspot_count']} | **DB Tables Coupled:** {s['db_table_count']}",
            f"- **Traceability Coverage:** {s['traceability_coverage_pct']}% ({s['covered_requirement_count']}/{s['requirement_count']}) | **Gate Passed:** `{s['traceability_gate_passed']}`",
            "",
            "| Module | Complexity | Hotspot | Entrypoints | DB Reads | DB Writes |",
            "| :--- | ---: | :---: | ---: | :--- | :--- |",
        ]
    )
    for m in result["module_inventory"]:
        lines.append(
            f"| `{m['module']}` | {m['cyclomatic_complexity']} | `{m['is_hotspot']}` | "
            f"{len(m['entrypoints'])} | {', '.join(m['db_reads']) or '—'} | {', '.join(m['db_writes']) or '—'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze legacy modules for entrypoints, DB couplings, and PRD traceability.")
    parser.add_argument("--input", required=True, type=Path, help="Path to codebase/requirements JSON")
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
            skill_id="legacy-code-to-prd",
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
