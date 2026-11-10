#!/usr/bin/env python3
"""Inspects SQL queries and table schemas for missing partition filters, join fanouts, and DDL/DML."""

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
    "max_query_scan_gb": 500.0,
}

DESTRUCTIVE_RE = re.compile(
    r"\b(DROP|TRUNCATE|DELETE|ALTER|INSERT|UPDATE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
FROM_JOIN_RE = re.compile(
    r"\b(FROM|JOIN)\s+([`\"a-zA-Z0-9_.-]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?",
    re.IGNORECASE,
)
JOIN_ON_RE = re.compile(
    r"\bJOIN\s+([`\"a-zA-Z0-9_.-]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?\s+ON\s+([^\n;]+?)(?=\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|$)",
    re.IGNORECASE | re.DOTALL,
)
AGG_FUNC_RE = re.compile(r"\b(SUM|COUNT|AVG)\s*\(", re.IGNORECASE)
CTE_NAMES_RE = re.compile(r"(?:WITH|,)\s*([a-zA-Z0-9_]+)\s+AS\s*\(([\s\S]*?)\)", re.IGNORECASE)


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
    p = Path(input_arg)
    if p.suffix.lower() == ".sql":
        return {"sql": p.read_text(encoding="utf-8"), "tables": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _clean_ident(raw: str) -> str:
    return raw.strip("`\" ").split(".")[-1].lower()


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    sql = str(data.get("sql") or "")
    tables = data.get("tables") or data.get("schema", [])
    dry_run_gb = float(data.get("estimated_scan_gb", 0.0))
    max_scan_gb = float(cfg.get("max_query_scan_gb", 500.0))

    table_meta = {_clean_ident(t["table_name"]): t for t in tables if t.get("table_name")}
    ctes = {m.group(1).lower(): m.group(2) for m in CTE_NAMES_RE.finditer(sql)}

    destructive_hits = sorted({m.group(1).upper() for m in DESTRUCTIVE_RE.finditer(sql)})
    is_read_only_safe = len(destructive_hits) == 0 and bool(re.search(r"\bSELECT\b|\bWITH\b", sql, re.IGNORECASE))

    referenced_tables: list[str] = []
    for _kw, tname, _alias in FROM_JOIN_RE.findall(sql):
        cleaned = _clean_ident(tname)
        if cleaned not in ctes:
            referenced_tables.append(cleaned)

    missing_partition_filters: list[dict[str, str]] = []
    for tname in sorted(set(referenced_tables)):
        meta = table_meta.get(tname)
        if not meta:
            continue
        pcol = str(meta.get("partition_column") or "").strip()
        req_part = bool(meta.get("require_partition_filter", bool(pcol)))
        if req_part and pcol:
            # Verify partition column appears inside WHERE / ON / HAVING filter
            where_match = re.search(r"\bWHERE\b([\s\S]+)$", sql, re.IGNORECASE)
            where_clause = where_match.group(1) if where_match else ""
            if not re.search(rf"\b{re.escape(pcol)}\b", where_clause, re.IGNORECASE):
                missing_partition_filters.append({"table_name": tname, "partition_column": pcol})

    fanout_risks: list[dict[str, Any]] = []
    has_aggregates = bool(AGG_FUNC_RE.search(sql))
    for m in JOIN_ON_RE.finditer(sql):
        joined_raw, _alias, on_expr = m.group(1), m.group(2), m.group(3)
        joined_name = _clean_ident(joined_raw)
        # Skip if joined CTE already uses GROUP BY
        if joined_name in ctes and re.search(r"\bGROUP\s+BY\b", ctes[joined_name], re.IGNORECASE):
            continue
        meta = table_meta.get(joined_name)
        if not meta:
            continue
        pks = [str(k).lower() for k in meta.get("primary_keys", [])]
        if pks:
            missing_pk_cols = [
                pk for pk in pks if not re.search(rf"\b{re.escape(pk)}\b", on_expr, re.IGNORECASE)
            ]
            if missing_pk_cols:
                fanout_risks.append(
                    {
                        "joined_table": joined_name,
                        "expected_primary_keys": pks,
                        "missing_join_keys": missing_pk_cols,
                        "inflates_aggregates": has_aggregates,
                        "remediation": f"Pre-aggregate {joined_name} in a CTE or include {missing_pk_cols} in JOIN ON.",
                    }
                )

    select_star_flag = bool(re.search(r"\bSELECT\s+\*", sql, re.IGNORECASE))
    scan_over_budget = dry_run_gb > max_scan_gb

    denominator_seams: list[str] = []
    if re.search(r"\bfiscal_", sql, re.IGNORECASE) and re.search(r"\bcalendar_|CURRENT_DATE", sql, re.IGNORECASE):
        denominator_seams.append("Mixed fiscal_* and calendar date columns detected; verify calendar alignment.")
    if re.search(r"\bcurrency", sql, re.IGNORECASE) and not re.search(r"fx_rate|convert|GROUP\s+BY[^\n]*currency", sql, re.IGNORECASE):
        denominator_seams.append("Currency column referenced without apparent FX normalization or currency grouping.")

    passed = (
        is_read_only_safe
        and not missing_partition_filters
        and not fanout_risks
        and not scan_over_budget
    )

    return {
        "skill": "schema-grounded-sql-analyst",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "is_read_only_safe": is_read_only_safe,
            "destructive_keywords": destructive_hits,
            "referenced_tables": sorted(set(referenced_tables)),
            "missing_partition_filter_count": len(missing_partition_filters),
            "fanout_risk_count": len(fanout_risks),
            "select_star_warning": select_star_flag,
            "estimated_scan_gb": dry_run_gb,
            "scan_over_budget": scan_over_budget,
            "denominator_seam_count": len(denominator_seams),
            "sql_gate_passed": passed,
        },
        "missing_partition_filters": missing_partition_filters,
        "fanout_risks": fanout_risks,
        "denominator_seams": denominator_seams,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# SQL Safety & Join Fanout Gate",
            "",
            f"- **Gate Passed:** `{s['sql_gate_passed']}` | **Read-Only Safe:** `{s['is_read_only_safe']}`",
            f"- **Missing Partition Filters:** {s['missing_partition_filter_count']} | **M:N Fanout Risks:** {s['fanout_risk_count']}",
            f"- **Estimated Scan:** {s['estimated_scan_gb']} GB (Over Budget: `{s['scan_over_budget']}`)",
            "",
        ]
    )
    for mp in result["missing_partition_filters"]:
        lines.append(
            f"- **Partition Guard:** Table `{mp['table_name']}` requires a `WHERE` predicate on `{mp['partition_column']}`."
        )
    for fr in result["fanout_risks"]:
        lines.append(
            f"- **Join Fanout Risk:** `{fr['joined_table']}` missing primary key(s) `{fr['missing_join_keys']}` — {fr['remediation']}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SQL safety, partition filters, and M:N join fanout.")
    parser.add_argument("--input", required=True, type=Path, help="Path to SQL/schema JSON or .sql file")
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
