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


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    return json.loads(Path(input_arg).read_text(encoding="utf-8"))


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    modules = data.get("modules") or data.get("files") or []
    requirements = data.get("requirements", [])
    tests = data.get("tests", [])
    hotspot_thresh = int(cfg.get("complexity_hotspot_threshold", 15))
    min_trace_pct = float(cfg.get("min_requirement_traceability_pct", 85.0))
    metadata = data.get("metadata", {})

    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: Legacy module inventory truncated; dependency graph may be incomplete.")

    module_inventory: list[dict[str, Any]] = []
    hotspots: list[dict[str, Any]] = []
    db_couplings: dict[str, dict[str, list[str]]] = {}

    for idx, mod in enumerate(modules):
        mname = str(mod.get("path") or mod.get("name") or f"module_{idx + 1}")
        code = str(mod.get("source") or mod.get("content") or "")
        explicit_cc = mod.get("cyclomatic_complexity")
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
        for rid in t.get("covers_requirements", []):
            test_by_req.setdefault(str(rid), []).append(tid)

    trace_matrix: list[dict[str, Any]] = []
    covered_count = 0
    untested_critical: list[str] = []
    for idx, req in enumerate(requirements):
        rid = str(req.get("req_id") or f"REQ-{idx + 1}")
        prio = str(req.get("priority") or "medium").lower()
        linked_tests = sorted(set(test_by_req.get(rid, []) + list(req.get("test_ids", []))))
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
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
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
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze legacy modules for entrypoints, DB couplings, and PRD traceability.")
    parser.add_argument("--input", required=True, type=Path, help="Path to codebase/requirements JSON")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
