#!/usr/bin/env python3
"""Checks market localization packs against do-not-translate lists, regional glossaries, and target locale coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "required_locales": ["ja-JP", "de-DE", "fr-FR"],
    "do_not_translate_terms": ["Gemini Enterprise", "BigQuery", "Vertex AI"],
}


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
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    _loaded = json.loads(Path(input_arg).read_text(encoding="utf-8"))
    return _loaded if isinstance(_loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)

    source_text = str(data.get("source_text") or "")
    target_locales = [str(l) for l in (data.get("target_locales") or _as_list(cfg.get("required_locales")))]
    dnt_terms = [str(t) for t in (data.get("do_not_translate_terms") or _as_list(cfg.get("do_not_translate_terms")))]
    glossary = _as_list(data.get("glossary"))
    translations = _as_list(data.get("translations"))

    trans_by_locale = {str(t.get("locale")): t for t in translations if t.get("locale")}
    audits: list[dict[str, Any]] = []

    active_dnt = [term for term in dnt_terms if term in source_text]

    for loc in target_locales:
        entry = trans_by_locale.get(loc)
        if not entry or not str(entry.get("translated_text") or "").strip():
            audits.append(
                {
                    "locale": loc,
                    "status": "MISSING_LOCALE_TRANSLATION",
                    "dnt_violations": [],
                    "glossary_mismatches": [],
                    "untranslated_leak": False,
                }
            )
            continue

        t_text = str(entry.get("translated_text"))
        dnt_violations = [term for term in active_dnt if term not in t_text]
        glossary_mismatches: list[str] = []
        for g in glossary:
            src_term = str(g.get("source_term") or "")
            expected = (g.get("approved_translations") or {}).get(loc)
            if src_term and expected and src_term.lower() in source_text.lower() and expected not in t_text:
                glossary_mismatches.append(f"Expected '{expected}' for '{src_term}'")

        untranslated_leak = bool(source_text.strip()) and t_text.strip() == source_text.strip()
        if untranslated_leak or dnt_violations or glossary_mismatches:
            status = "LOCALIZATION_REWORK_REQUIRED"
        else:
            status = "LOCALE_QA_PASSED"

        audits.append(
            {
                "locale": loc,
                "status": status,
                "dnt_violations": dnt_violations,
                "glossary_mismatches": glossary_mismatches,
                "untranslated_leak": untranslated_leak,
            }
        )

    return {
        "skill": "market-localization-adapter",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "target_locales_count": len(target_locales),
            "passed_count": sum(1 for a in audits if a["status"] == "LOCALE_QA_PASSED"),
            "missing_locale_count": sum(1 for a in audits if a["status"] == "MISSING_LOCALE_TRANSLATION"),
            "rework_required_count": sum(1 for a in audits if a["status"] == "LOCALIZATION_REWORK_REQUIRED"),
        },
        "locale_audits": audits,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(audits)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Market Localization & Terminology QA Report",
            "",
            f"- **Target Locales:** {s['target_locales_count']} | **Passed:** {s['passed_count']} | "
            f"**Missing:** {s['missing_locale_count']} | **Rework Required:** {s['rework_required_count']}",
            "",
            "| Locale | Status | DNT Violations | Glossary Mismatches | Untranslated Leak |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for a in result["locale_audits"]:
        dnt = ", ".join(a["dnt_violations"]) or "None"
        gl = "; ".join(a["glossary_mismatches"]) or "None"
        lines.append(
            f"| `{a['locale']}` | `{a['status']}` | {dnt} | {gl} | {'YES' if a['untranslated_leak'] else 'No'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify localized marketing copy against DNT terms and glossaries.")
    parser.add_argument("--input", required=True, type=Path, help="Path to localization pack JSON")
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
