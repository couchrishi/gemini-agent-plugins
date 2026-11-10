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

    source_text = str(data.get("source_text") or "")
    target_locales = [str(l) for l in (data.get("target_locales") or cfg.get("required_locales", []))]
    dnt_terms = [str(t) for t in (data.get("do_not_translate_terms") or cfg.get("do_not_translate_terms", []))]
    glossary = data.get("glossary", [])
    translations = data.get("translations", [])

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
        "truncation_warnings": [],
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
