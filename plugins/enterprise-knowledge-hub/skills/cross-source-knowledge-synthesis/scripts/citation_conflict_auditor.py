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


def load_config(config_path: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    merged = dict(DEFAULT_CONFIG)
    if isinstance(config_path, dict):
        merged.update(config_path)
    elif config_path is not None:
        p = Path(config_path)
        if p.is_file():
            merged.update(json.loads(p.read_text(encoding="utf-8")))
    org_configured = _to_bool(merged.get("org_configured"), False)
    banner = "" if org_configured else BASELINE_BANNER
    return merged, org_configured, banner


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
                skill_id="cross-source-knowledge-synthesis",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"sources": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="cross-source-knowledge-synthesis", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"sources": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"sources": loaded}
    return loaded if isinstance(loaded, dict) else {}


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
    return _to_bool(src.get("is_draft"), False)


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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="cross-source-knowledge-synthesis")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "cross-source-knowledge-synthesis",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    sources = data.get("sources") or data.get("records") or []
    draft_claims = _as_list(data.get("draft_claims"))
    metadata = _as_dict(data.get("metadata"))
    as_of = _parse_date(data.get("as_of_date"), dt.date(2026, 11, 10))

    total_available = _to_int(metadata.get("total_available"), len(sources))
    truncated = bool(metadata.get("truncated", total_available > len(sources)))
    blocked_repos = list(_as_list(metadata.get("blocked_connectors")))
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
    half_life = max(1, _to_int(cfg.get("recency_half_life_days"), 365))
    allow_drafts = _to_bool(cfg.get("allow_draft_versions_in_answers"), False)

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
        irm_protected = _to_bool(src.get("irm_protected"), False)

        if irm_protected and len(excerpt.strip()) < 15:
            irm_warnings.append(f"{sid} ({title}): IRM/sensitivity-encrypted body omitted by connector.")

        for pat in INJECTION_PATTERNS:
            if pat.search(excerpt):
                injection_flags.append({"source_id": sid, "title": title, "pattern": pat.pattern})

        draft_flag = _is_draft(src)
        mod_date = _parse_date(src.get("last_modified") or src.get("updated_at"), as_of)
        age_days = max(0, (as_of - mod_date).days)
        recency_score = math.exp(-math.log(2) * (age_days / half_life))
        base_auth = _to_float(weights.get(doc_type), 0.5)
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
        cites = [str(c) for c in _as_list(claim.get("citations"))]
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
    min_cov = _to_float(cfg.get("min_citation_coverage_pct"), 100.0)

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
        "truncation_warnings": _collect_truncation_warnings(data, count=None, existing=warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
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
    for w in _as_list(result.get("truncation_warnings")):
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
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional file path to write output")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="cross-source-knowledge-synthesis",
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
    rendered = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
