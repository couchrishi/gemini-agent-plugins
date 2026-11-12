#!/usr/bin/env python3
"""Matches RFP questionnaire rows against verified answer libraries using TF-IDF similarity."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "rfp_min_similarity_threshold": 0.22,
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
INJECTION_RE = re.compile(r"(ignore\s+(all\s+)?previous\s+instructions|system\s+override|exfiltrate)", re.IGNORECASE)


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
                skill_id="rfp-questionnaire-responder",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"questions": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="rfp-questionnaire-responder", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"questions": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"questions": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _tokenize(text: str) -> list[str]:
    stop = {"the", "and", "for", "with", "that", "this", "are", "does", "your", "have", "can", "you"}
    return [t for t in TOKEN_RE.findall((text or "").lower()) if len(t) > 2 and t not in stop]


def _cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(v * vec_b.get(k, 0.0) for k, v in vec_a.items())
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    *,
    library_path: str | Path | None = None,
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
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="rfp-questionnaire-responder")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "rfp-questionnaire-responder",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    questions = data.get("questions") or data.get("requirements") or []
    library = list(_as_list(data.get("answer_library")))
    if library_path and not library:
        lp = Path(library_path)
        if _ENTERPRISE_IO is not None:
            if lp.suffix.lower() in {".xlsx", ".xlsm"}:
                loaded_lp = _ENTERPRISE_IO.load_enterprise_payload(
                    lp,
                    skill_id="rfp-questionnaire-responder",
                    sheet=sheet,
                    column_map=eff_col_map,
                    sheet_map=eff_sheet_map,
                )
                library = list(loaded_lp.get("answer_library") or _ENTERPRISE_IO.read_enterprise_table(lp, sheet=sheet, column_map=eff_col_map))
            else:
                library = _ENTERPRISE_IO.read_enterprise_table(
                    lp,
                    sheet=sheet,
                    column_map=eff_col_map,
                    fallback_keys=("answer_library", "rows", "items", "records"),
                )
        if library and _ENTERPRISE_IO is not None:
            lib_diag = _ENTERPRISE_IO.validate_payload_schema({"answer_library": library}, skill_id="rfp-questionnaire-responder")
            if lib_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
                return _ENTERPRISE_IO.build_schema_error_result(
                    "rfp-questionnaire-responder",
                    lib_diag,
                    org_configured=org_configured,
                    banner=banner,
                    source=lp,
                    config=cfg,
                    column_map=eff_col_map,
                    sheet_map=eff_sheet_map,
                    sheet=sheet,
                )
        elif lp.suffix.lower() == ".csv":
            with lp.open("r", encoding="utf-8", newline="") as fh:
                library = list(csv.DictReader(fh))
        else:
            loaded = json.loads(lp.read_text(encoding="utf-8"))
            library = loaded.get("answer_library", loaded if isinstance(loaded, list) else [])

    min_sim = _to_float(cfg.get("rfp_min_similarity_threshold"), 0.22)
    metadata = _as_dict(data.get("metadata"))
    warnings: list[str] = []
    if metadata.get("truncated"):
        warnings.append("TRUNCATION_WARNING: RFP question sheet or answer library was truncated.")
    if not library:
        warnings.append("UNVERIFIED_INSUFFICIENT_SCOPE: Verified answer library is empty; 0 answers matched.")

    # Build IDF across answer library + questions
    lib_docs: list[list[str]] = []
    for entry in library:
        toks = _tokenize(f"{entry.get('category', '')} {entry.get('question', '')} {entry.get('answer', '')} {' '.join(_as_list(entry.get('tags')))}")
        lib_docs.append(toks)
    q_docs = [_tokenize(f"{q.get('category', '')} {q.get('question', '')}") for q in questions]
    all_docs = lib_docs + q_docs
    num_docs = max(1, len(all_docs))
    df: Counter[str] = Counter()
    for toks in all_docs:
        df.update(set(toks))
    idf = {tok: math.log((1.0 + num_docs) / (1.0 + cnt)) + 1.0 for tok, cnt in df.items()}

    def to_tfidf(toks: list[str]) -> dict[str, float]:
        tf = Counter(toks)
        total = max(1, len(toks))
        return {tok: (cnt / total) * idf.get(tok, 1.0) for tok, cnt in tf.items()}

    lib_vecs = [to_tfidf(toks) for toks in lib_docs]

    matrix_rows: list[dict[str, Any]] = []
    mandatory_gaps: list[dict[str, Any]] = []
    injection_flags: list[dict[str, Any]] = []
    matched_count = 0
    cited_count = 0

    for idx, q in enumerate(questions):
        qid = str(q.get("question_id") or f"RFP-{idx + 1}")
        qtext = str(q.get("question") or "")
        qcat = str(q.get("category") or "general").lower()
        mandatory = _to_bool(q.get("is_mandatory"), False)

        if INJECTION_RE.search(qtext):
            injection_flags.append({"question_id": qid, "snippet": qtext[:120]})

        qvec = to_tfidf(q_docs[idx])
        best_idx = -1
        best_score = 0.0
        for j, entry in enumerate(library):
            sim = _cosine(qvec, lib_vecs[j])
            ecat = str(entry.get("category") or "general").lower()
            if qcat != "general" and ecat == qcat:
                sim += 0.08
            if sim > best_score:
                best_score = sim
                best_idx = j

        if best_idx >= 0 and best_score >= min_sim:
            best = library[best_idx]
            matched_count += 1
            src_id = best.get("source_id")
            if src_id:
                cited_count += 1
            status = "MATCHED_VERIFIED"
            row = {
                "question_id": qid,
                "category": qcat,
                "is_mandatory": mandatory,
                "status": status,
                "similarity_score": round(min(1.0, best_score), 4),
                "matched_entry_id": best.get("id"),
                "source_id": src_id,
                "proposed_answer": best.get("answer"),
            }
        else:
            status = "MANDATORY_GAP" if mandatory else "UNMATCHED_GAP"
            row = {
                "question_id": qid,
                "category": qcat,
                "is_mandatory": mandatory,
                "status": status,
                "similarity_score": round(best_score, 4),
                "matched_entry_id": None,
                "source_id": None,
                "proposed_answer": None,
            }
            if mandatory:
                mandatory_gaps.append({"question_id": qid, "category": qcat, "question": qtext})
        matrix_rows.append(row)

    total_q = len(questions)
    completion_pct = round((matched_count / total_q) * 100.0, 2) if total_q else 0.0
    citation_pct = round((cited_count / matched_count) * 100.0, 2) if matched_count else 100.0

    return {
        "skill": "rfp-questionnaire-responder",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "question_count": total_q,
            "matched_count": matched_count,
            "unmatched_count": total_q - matched_count,
            "mandatory_gap_count": len(mandatory_gaps),
            "completion_rate_pct": completion_pct,
            "citation_coverage_pct": citation_pct,
            "injection_flag_count": len(injection_flags),
        },
        "response_matrix": matrix_rows,
        "mandatory_gaps": mandatory_gaps,
        "injection_flags": injection_flags,
        "truncation_warnings": _collect_truncation_warnings(data, count=None, existing=warnings),
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
            "# RFP Questionnaire Response Matrix",
            "",
            f"- **Matched:** {s['matched_count']} / {s['question_count']} ({s['completion_rate_pct']}%) | **Citation Coverage:** {s['citation_coverage_pct']}%",
            f"- **Mandatory Gaps:** {s['mandatory_gap_count']} | **Injection Flags:** {s['injection_flag_count']}",
            "",
            "| Question ID | Category | Mandatory | Status | Similarity | Source ID |",
            "| :--- | :--- | :---: | :--- | ---: | :--- |",
        ]
    )
    for r in result["response_matrix"]:
        lines.append(
            f"| `{r['question_id']}` | {r['category']} | `{r['is_mandatory']}` | `{r['status']}` | "
            f"{r['similarity_score']:.3f} | `{r['source_id'] or 'NONE'}` |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match RFP questionnaire rows against verified library.")
    parser.add_argument("--input", required=True, type=Path, help="Path to RFP JSON or CSV")
    parser.add_argument("--library", type=Path, help="Optional separate verified answer library JSON/CSV")
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
            skill_id="rfp-questionnaire-responder",
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
    result = analyze(args.input, config=args.config, library_path=args.library, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
