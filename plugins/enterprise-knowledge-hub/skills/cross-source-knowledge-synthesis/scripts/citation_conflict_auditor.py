#!/usr/bin/env python3
"""Cross-source authority scorer, numerical/date conflict auditor, and citation coverage verifier."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_AUTHORITY_WEIGHTS: dict[str, float] = {
    "official_policy": 1.0,
    "approved_sop": 0.9,
    "knowledge_article": 0.8,
    "architecture_doc": 0.75,
    "slide_deck": 0.5,
    "chat_thread": 0.3,
}
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "recency_half_life_days": 365,
    "min_citation_coverage_pct": 100.0,
    "allow_draft_versions_in_answers": False,
    "authoritative_source_weights": dict(DEFAULT_AUTHORITY_WEIGHTS),
}

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"exfiltrate|forward\s+all\s+records", re.IGNORECASE),
]
NUMERIC_CLAIM_RE = re.compile(
    r"(?:USD|\$|EUR|GBP)?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(%|percent|days?|hours?|months?|years?|x|M|K|million|billion)?",
    re.IGNORECASE,
)


def load_config(config_path: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    merged = dict(DEFAULT_CONFIG)
    if isinstance(config_path, dict):
        merged.update(config_path)
    elif config_path is not None:
        p = Path(config_path)
        if p.is_file():
            merged.update(json.loads(p.read_text(encoding="utf-8")))
    org_configured = bool(merged.get("org_configured", False))
    banner = "" if org_configured else BASELINE_BANNER
    return merged, org_configured, banner


def load_payload(input_path: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_path, dict):
        return input_path
    if isinstance(input_path, list):
        return {"sources": input_path}
    p = Path(input_path)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"sources": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"sources": data}
    return data


def _parse_date(val: str | None, fallback: dt.date) -> dt.date:
    if not val:
        return fallback
    cleaned = str(val).strip()[:10]
    try:
        return dt.date.fromisoformat(cleaned)
    except ValueError:
        return fallback


def _extract_claim_signatures(text: str) -> list[str]:
    sigs: list[str] = []
    for num_str, unit in NUMERIC_CLAIM_RE.findall(text or ""):
        norm_num = num_str.replace(",", "")
        norm_unit = (unit or "").lower().rstrip("s")
        sigs.append(f"{norm_num}:{norm_unit}")
    return sigs


def _is_draft(src: dict[str, Any]) -> bool:
    status = str(src.get("status", "")).lower()
    if status in {"draft", "unpublished", "wip"}:
        return True
    ver = str(src.get("version", ""))
    if re.match(r"^\d+\.[1-9]\d*$", ver):
        return True
    return bool(src.get("is_draft", False))


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    sources = data.get("sources") or data.get("records") or []
    draft_claims = data.get("draft_claims", [])
    metadata = data.get("metadata", {})
    as_of = _parse_date(data.get("as_of_date"), dt.date(2026, 11, 10))

    total_available = int(metadata.get("total_available", len(sources)))
    truncated = bool(metadata.get("truncated", total_available > len(sources)))
    blocked_repos = list(metadata.get("blocked_connectors", []))
    warnings: list[str] = []
    if truncated:
        pct = round((len(sources) / max(total_available, 1)) * 100.0, 1)
        warnings.append(
            f"TRUNCATION_WARNING: Analyzed {len(sources)} of {total_available} available search hits ({pct}%)."
        )
    if blocked_repos:
        warnings.append(
            f"UNVERIFIED_INSUFFICIENT_SCOPE: Blocked or missing access on connectors: {', '.join(blocked_repos)}."
        )

    weights = cfg.get("authoritative_source_weights", DEFAULT_AUTHORITY_WEIGHTS)
    half_life = max(1, int(cfg.get("recency_half_life_days", 365)))
    allow_drafts = bool(cfg.get("allow_draft_versions_in_answers", False))

    ranked_sources: list[dict[str, Any]] = []
    topic_claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
    injection_flags: list[dict[str, Any]] = []
    irm_warnings: list[str] = []
    valid_source_ids: set[str] = set()

    for idx, src in enumerate(sources):
        sid = str(src.get("id") or f"SRC-{idx + 1}")
        valid_source_ids.add(sid)
        title = str(src.get("title") or sid)
        repo = str(src.get("repository") or src.get("source_system") or "unknown")
        doc_type = str(src.get("doc_type") or "knowledge_article").lower()
        topic = str(src.get("topic") or "general").lower()
        excerpt = str(src.get("excerpt") or src.get("content") or "")
        irm_protected = bool(src.get("irm_protected", False))

        if irm_protected and len(excerpt.strip()) < 15:
            irm_warnings.append(f"{sid} ({title}): IRM/sensitivity-encrypted body omitted by connector.")

        for pat in INJECTION_PATTERNS:
            if pat.search(excerpt):
                injection_flags.append({"source_id": sid, "title": title, "pattern": pat.pattern})

        draft_flag = _is_draft(src)
        mod_date = _parse_date(src.get("last_modified") or src.get("updated_at"), as_of)
        age_days = max(0, (as_of - mod_date).days)
        recency_score = math.exp(-math.log(2) * (age_days / half_life))
        base_auth = float(weights.get(doc_type, 0.5))
        penalty = 0.25 if (draft_flag and not allow_drafts) else 1.0
        composite = round(base_auth * (0.65 + 0.35 * recency_score) * penalty, 4)

        sigs = _extract_claim_signatures(excerpt)
        if sigs:
            topic_claims[topic].append(
                {
                    "source_id": sid,
                    "title": title,
                    "repository": repo,
                    "doc_type": doc_type,
                    "last_modified": mod_date.isoformat(),
                    "composite_score": composite,
                    "is_draft": draft_flag,
                    "signatures": sigs,
                    "excerpt": excerpt[:180],
                }
            )

        ranked_sources.append(
            {
                "source_id": sid,
                "title": title,
                "repository": repo,
                "doc_type": doc_type,
                "topic": topic,
                "last_modified": mod_date.isoformat(),
                "age_days": age_days,
                "is_draft": draft_flag,
                "irm_protected": irm_protected,
                "authority_score": base_auth,
                "recency_factor": round(recency_score, 4),
                "composite_score": composite,
            }
        )

    ranked_sources.sort(key=lambda r: r["composite_score"], reverse=True)

    conflicts: list[dict[str, Any]] = []
    for topic, entries in sorted(topic_claims.items()):
        sig_sets = {tuple(sorted(set(e["signatures"]))) for e in entries}
        if len(entries) >= 2 and len(sig_sets) > 1:
            ordered = sorted(entries, key=lambda x: x["composite_score"], reverse=True)
            conflicts.append(
                {
                    "topic": topic,
                    "preferred_source_id": ordered[0]["source_id"],
                    "preferred_title": ordered[0]["title"],
                    "conflicting_sources": ordered,
                    "resolution_rationale": (
                        f"Prefer {ordered[0]['source_id']} ({ordered[0]['doc_type']}, "
                        f"score={ordered[0]['composite_score']}) over lower-authority/older variants."
                    ),
                }
            )

    cited_count = 0
    uncited_claims: list[str] = []
    invalid_citations: list[dict[str, str]] = []
    for claim in draft_claims:
        ctext = str(claim.get("claim") or "")
        cites = [str(c) for c in claim.get("citations", [])]
        valid = [c for c in cites if c in valid_source_ids]
        bad = [c for c in cites if c not in valid_source_ids]
        for b in bad:
            invalid_citations.append({"claim": ctext, "missing_source_id": b})
        if valid:
            cited_count += 1
        else:
            uncited_claims.append(ctext)

    coverage_pct = (
        round((cited_count / len(draft_claims)) * 100.0, 2) if draft_claims else 100.0
    )
    min_cov = float(cfg.get("min_citation_coverage_pct", 100.0))

    return {
        "skill": "cross-source-knowledge-synthesis",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "source_count": len(sources),
            "total_available": total_available,
            "truncated": truncated,
            "conflict_topic_count": len(conflicts),
            "draft_claim_count": len(draft_claims),
            "citation_coverage_pct": coverage_pct,
            "citation_gate_passed": coverage_pct >= min_cov and not invalid_citations,
            "injection_flag_count": len(injection_flags),
            "irm_warning_count": len(irm_warnings),
            "top_authoritative_source_id": ranked_sources[0]["source_id"] if ranked_sources else None,
        },
        "ranked_sources": ranked_sources,
        "conflicts": conflicts,
        "uncited_claims": uncited_claims,
        "invalid_citations": invalid_citations,
        "injection_flags": injection_flags,
        "irm_warnings": irm_warnings,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.append(result["baseline_banner"])
        lines.append("")
    s = result["summary"]
    lines.extend(
        [
            "# Cross-Source Knowledge Synthesis Audit",
            "",
            f"- **Sources Ranked:** {s['source_count']} / {s['total_available']} (Truncated: `{s['truncated']}`)",
            f"- **Top Authoritative Source:** `{s['top_authoritative_source_id']}`",
            f"- **Conflicting Topics Flagged:** {s['conflict_topic_count']}",
            f"- **Citation Coverage:** {s['citation_coverage_pct']}% (Gate Passed: `{s['citation_gate_passed']}`)",
            "",
        ]
    )
    for w in result.get("truncation_warnings", []):
        lines.append(f"> **WARNING:** {w}")
    if result.get("truncation_warnings"):
        lines.append("")
    lines.extend(
        [
            "## Source Authority Ranking",
            "",
            "| Source ID | Title | Repo | Type | Modified | Draft | Score |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | ---: |",
        ]
    )
    for row in result["ranked_sources"]:
        lines.append(
            f"| `{row['source_id']}` | {row['title']} | {row['repository']} | {row['doc_type']} | "
            f"{row['last_modified']} | `{row['is_draft']}` | {row['composite_score']:.4f} |"
        )
    if result["conflicts"]:
        lines.extend(["", "## Detected Contradictions", ""])
        for c in result["conflicts"]:
            lines.append(f"- **Topic `{c['topic']}`:** {c['resolution_rationale']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit multi-source authority, conflicts, and citation coverage.")
    parser.add_argument("--input", required=True, type=Path, help="Path to JSON or CSV source dataset")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional file path to write output")
    args = parser.parse_args(argv)

    result = analyze(args.input, config=args.config)
    rendered = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
