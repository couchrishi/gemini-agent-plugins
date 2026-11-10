#!/usr/bin/env python3
"""Enterprise corpus freshness, departed-owner, near-duplicate, and ticket-gap scanner."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import json
import re
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "stale_review_days": 180,
    "duplicate_title_similarity_threshold": 0.82,
}


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
        return {"documents": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"documents": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"documents": data}
    return data


def _parse_date(val: Any) -> dt.date | None:
    if not val:
        return None
    try:
        return dt.date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    docs = data.get("documents") or data.get("records") or []
    ticket_topics = data.get("ticket_topics", [])
    inactive_owners = {str(o).lower() for o in data.get("inactive_owners", [])}
    as_of = _parse_date(data.get("as_of_date")) or dt.date(2026, 11, 10)
    stale_days = int(cfg.get("stale_review_days", 180))
    dup_threshold = float(cfg.get("duplicate_title_similarity_threshold", 0.82))

    metadata = data.get("metadata", {})
    total_available = int(metadata.get("total_available", len(docs)))
    truncated = bool(metadata.get("truncated", total_available > len(docs)))
    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"TRUNCATION_WARNING: Scanned {len(docs)} of {total_available} indexed documents."
        )

    stale_docs: list[dict[str, Any]] = []
    unverified_null_reviews: list[dict[str, Any]] = []
    departed_owner_docs: list[dict[str, Any]] = []
    unpublished_drafts: list[dict[str, Any]] = []
    covered_topics: set[str] = set()

    normalized_titles: list[tuple[str, str, str, str]] = []
    for idx, d in enumerate(docs):
        doc_id = str(d.get("doc_id") or f"DOC-{idx + 1}")
        title = str(d.get("title") or doc_id)
        repo = str(d.get("repository") or "unknown")
        owner = str(d.get("owner") or "").strip()
        owner_status = str(d.get("owner_status") or "active").lower()
        version = str(d.get("version") or "1.0")
        last_rev = _parse_date(d.get("last_reviewed_at"))
        for t in d.get("topics", []):
            covered_topics.add(str(t).lower())
        covered_topics.update(re.findall(r"[a-z0-9]{4,}", title.lower()))

        normalized_titles.append((doc_id, title, repo, re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()))

        if last_rev is None:
            # Null timestamp != clean: explicitly treat as unverified / overdue review.
            unverified_null_reviews.append(
                {"doc_id": doc_id, "title": title, "repository": repo, "owner": owner or "UNASSIGNED"}
            )
        else:
            age = (as_of - last_rev).days
            if age > stale_days:
                stale_docs.append(
                    {
                        "doc_id": doc_id,
                        "title": title,
                        "repository": repo,
                        "last_reviewed_at": last_rev.isoformat(),
                        "age_days": age,
                    }
                )

        if not owner or owner_status in {"departed", "inactive", "disabled"} or owner.lower() in inactive_owners:
            departed_owner_docs.append(
                {"doc_id": doc_id, "title": title, "owner": owner or "UNASSIGNED", "owner_status": owner_status}
            )

        if re.match(r"^\d+\.[1-9]\d*$", version) or str(d.get("moderation_status", "")).lower() == "draft":
            unpublished_drafts.append({"doc_id": doc_id, "title": title, "repository": repo, "version": version})

    near_duplicates: list[dict[str, Any]] = []
    for i in range(len(normalized_titles)):
        id_a, title_a, repo_a, norm_a = normalized_titles[i]
        for j in range(i + 1, len(normalized_titles)):
            id_b, title_b, repo_b, norm_b = normalized_titles[j]
            ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
            if ratio >= dup_threshold:
                near_duplicates.append(
                    {
                        "doc_a": id_a,
                        "title_a": title_a,
                        "repo_a": repo_a,
                        "doc_b": id_b,
                        "title_b": title_b,
                        "repo_b": repo_b,
                        "similarity": round(ratio, 4),
                    }
                )

    unindexed_topics: list[dict[str, Any]] = []
    for item in ticket_topics:
        if isinstance(item, str):
            topic = item.strip()
            vol = 1
        elif isinstance(item, dict):
            topic = str(item.get("topic") or "").strip()
            vol = int(item.get("ticket_count", 0))
        else:
            continue
        t_words = set(re.findall(r"[a-z0-9]{4,}", topic.lower()))
        if not t_words or not (t_words & covered_topics):
            unindexed_topics.append({"topic": topic, "ticket_count": vol})
    unindexed_topics.sort(key=lambda x: x["ticket_count"], reverse=True)

    return {
        "skill": "knowledge-gap-freshness-audit",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "documents_scanned": len(docs),
            "total_available": total_available,
            "truncated": truncated,
            "stale_count": len(stale_docs),
            "unverified_null_review_count": len(unverified_null_reviews),
            "departed_owner_count": len(departed_owner_docs),
            "unpublished_draft_count": len(unpublished_drafts),
            "near_duplicate_pair_count": len(near_duplicates),
            "unindexed_ticket_topic_count": len(unindexed_topics),
        },
        "stale_docs": stale_docs,
        "unverified_null_reviews": unverified_null_reviews,
        "departed_owner_docs": departed_owner_docs,
        "unpublished_drafts": unpublished_drafts,
        "near_duplicates": near_duplicates,
        "unindexed_topics": unindexed_topics,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Corpus Hygiene & Knowledge Gap Audit",
            "",
            f"- **Documents Scanned:** {s['documents_scanned']} / {s['total_available']}",
            f"- **Overdue Review (>Threshold):** {s['stale_count']}",
            f"- **Null / Unverified Review Date:** {s['unverified_null_review_count']}",
            f"- **Departed / Missing Owner:** {s['departed_owner_count']}",
            f"- **Near-Duplicate Pairs:** {s['near_duplicate_pair_count']}",
            f"- **Unindexed Ticket Topics:** {s['unindexed_ticket_topic_count']}",
            "",
        ]
    )
    for w in result.get("truncation_warnings", []):
        lines.append(f"> **WARNING:** {w}")
    if result["unindexed_topics"]:
        lines.extend(["## Top Unindexed Ticket Topics", "", "| Topic | Ticket Volume |", "| :--- | ---: |"])
        for t in result["unindexed_topics"]:
            lines.append(f"| {t['topic']} | {t['ticket_count']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit enterprise knowledge base freshness and gaps.")
    parser.add_argument("--input", required=True, type=Path, help="Path to corpus JSON or CSV")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
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
