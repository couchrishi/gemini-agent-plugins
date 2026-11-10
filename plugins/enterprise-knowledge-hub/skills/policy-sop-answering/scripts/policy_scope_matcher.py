#!/usr/bin/env python3
"""Jurisdiction-, entity-, and effective-date-scoped policy/SOP matcher with strict abstention."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "allow_draft_versions_in_answers": False,
    "stale_review_days": 180,
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


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


def load_payload(input_arg: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"clauses": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"clauses": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"clauses": data}
    return data


def _parse_date(val: Any) -> dt.date | None:
    if not val:
        return None
    try:
        return dt.date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def _tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall((text or "").lower()) if len(t) > 2}


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
    *,
    query: str | None = None,
    jurisdiction: str | None = None,
    entity: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    clauses = data.get("clauses") or data.get("records") or []
    q_text = query or data.get("query") or ""
    target_jur = (jurisdiction or data.get("jurisdiction") or "GLOBAL").upper()
    target_ent = (entity or data.get("entity") or "ALL").lower()
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or dt.date(2026, 11, 10)
    allow_drafts = bool(cfg.get("allow_draft_versions_in_answers", False))

    metadata = data.get("metadata", {})
    total_available = int(metadata.get("total_available", len(clauses)))
    truncated = bool(metadata.get("truncated", total_available > len(clauses)))
    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"TRUNCATION_WARNING: Evaluated {len(clauses)} of {total_available} policy clauses."
        )

    q_toks = _tokens(q_text)
    matched: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for idx, c in enumerate(clauses):
        cid = str(c.get("clause_id") or f"CL-{idx + 1}")
        status = str(c.get("status") or "published").lower()
        c_jur = str(c.get("jurisdiction") or "GLOBAL").upper()
        c_ent = str(c.get("entity") or "ALL").lower()
        eff = _parse_date(c.get("effective_date"))
        exp = _parse_date(c.get("expiration_date"))
        title = str(c.get("title") or "")
        body = str(c.get("text") or c.get("body") or "")

        if status in {"superseded", "archived", "retired"}:
            rejected.append({"clause_id": cid, "reason": f"status={status}"})
            continue
        if status == "draft" and not allow_drafts:
            rejected.append({"clause_id": cid, "reason": "unpublished_draft"})
            continue
        if c_jur not in {target_jur, "GLOBAL", "ALL"}:
            rejected.append({"clause_id": cid, "reason": f"jurisdiction_mismatch:{c_jur}"})
            continue
        if target_ent != "all" and c_ent not in {target_ent, "all", "global"}:
            rejected.append({"clause_id": cid, "reason": f"entity_mismatch:{c_ent}"})
            continue
        if eff and eff > as_of:
            rejected.append({"clause_id": cid, "reason": f"not_yet_effective:{eff.isoformat()}"})
            continue
        if exp and exp < as_of:
            rejected.append({"clause_id": cid, "reason": f"expired:{exp.isoformat()}"})
            continue

        c_toks = _tokens(f"{title} {body} {c.get('category', '')}")
        overlap = len(q_toks & c_toks) / max(len(q_toks), 1) if q_toks else 1.0
        jur_bonus = 0.25 if c_jur == target_jur else 0.0
        ent_bonus = 0.15 if c_ent == target_ent else 0.0
        score = round(overlap + jur_bonus + ent_bonus, 4)

        if q_toks and overlap == 0.0:
            rejected.append({"clause_id": cid, "reason": "zero_query_term_overlap"})
            continue

        matched.append(
            {
                "clause_id": cid,
                "policy_name": str(c.get("policy_name") or title),
                "version": str(c.get("version") or "1.0"),
                "jurisdiction": c_jur,
                "entity": str(c.get("entity") or "ALL"),
                "effective_date": eff.isoformat() if eff else "UNSPECIFIED",
                "relevance_score": score,
                "text": body,
            }
        )

    matched.sort(key=lambda m: (m["relevance_score"], m["jurisdiction"] == target_jur), reverse=True)
    abstained = len(matched) == 0

    return {
        "skill": "policy-sop-answering",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "query_context": {
            "query": q_text,
            "jurisdiction": target_jur,
            "entity": target_ent,
            "as_of_date": as_of.isoformat(),
        },
        "summary": {
            "evaluated_clauses": len(clauses),
            "active_clause_count": len(matched),
            "rejected_clause_count": len(rejected),
            "abstained": abstained,
            "abstention_code": "ABSTENTION_NO_EFFECTIVE_COVERAGE" if abstained else "NONE",
        },
        "matched_clauses": matched,
        "rejected_clauses": rejected,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    qc = result["query_context"]
    lines.extend(
        [
            "# Scoped Policy & SOP Determination",
            "",
            f"- **Jurisdiction / Entity / As-Of:** `{qc['jurisdiction']}` / `{qc['entity']}` / `{qc['as_of_date']}`",
            f"- **Active Matching Clauses:** {s['active_clause_count']} (Rejected: {s['rejected_clause_count']})",
            f"- **Abstained:** `{s['abstained']}` (`{s['abstention_code']}`)",
            "",
        ]
    )
    if s["abstained"]:
        lines.append(
            "> **ABSTENTION:** No active, non-superseded policy clause covers the requested jurisdiction and effective date."
        )
        lines.append("")
    else:
        lines.extend(
            [
                "| Clause ID | Policy | Version | Jurisdiction | Effective | Score |",
                "| :--- | :--- | :--- | :--- | :--- | ---: |",
            ]
        )
        for m in result["matched_clauses"]:
            lines.append(
                f"| `{m['clause_id']}` | {m['policy_name']} | {m['version']} | {m['jurisdiction']} | "
                f"{m['effective_date']} | {m['relevance_score']:.4f} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match policy/SOP clauses by jurisdiction, entity, and date.")
    parser.add_argument("--input", required=True, type=Path, help="Path to policy clauses JSON or CSV")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--query", help="Policy question text")
    parser.add_argument("--jurisdiction", help="Target jurisdiction code (e.g. SG, US-CA, DE)")
    parser.add_argument("--entity", help="Target legal entity")
    parser.add_argument("--as-of-date", help="ISO effective reference date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
    args = parser.parse_args(argv)

    result = analyze(
        args.input,
        config=args.config,
        query=args.query,
        jurisdiction=args.jurisdiction,
        entity=args.entity,
        as_of_date=args.as_of_date,
    )
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
