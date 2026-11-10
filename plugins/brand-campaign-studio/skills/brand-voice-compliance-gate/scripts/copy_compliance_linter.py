#!/usr/bin/env python3
"""Lints marketing copy against brand voice rules, prohibited claims, disclaimers, and channel limits."""

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
    "channel_limits": {
        "search_ad_headline": 30,
        "search_ad_description": 90,
        "email_subject": 60,
        "linkedin_post": 300,
    },
    "prohibited_claims": [
        "100% guaranteed",
        "zero risk",
        "never fails",
        "best in the world",
        "instant cure",
        "risk-free return",
    ],
    "max_avg_sentence_words": 22,
}

CLAIM_REQUIRES_DISCLAIMER = re.compile(r"\b(up\s+to\s+\d+%|roi|apr|apy|save\s+\$|guaranteed\s+uptime|clinical)\b", re.I)
DISCLAIMER_MARKERS = re.compile(r"(terms\s+apply|results\s+may\s+vary|subject\s+to\s+eligibility|see\s+disclosures|see\s+sla)", re.I)


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


def _lint_asset(asset: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    aid = str(asset.get("asset_id") or "ASSET-1")
    channel = str(asset.get("channel") or "linkedin_post").lower().strip()
    headline = str(asset.get("headline") or "")
    body = str(asset.get("body") or "")
    disclaimer = str(asset.get("disclaimer") or "")
    full_text = f"{headline} {body}".strip()
    combined = f"{full_text} {disclaimer}".strip()

    limits = cfg.get("channel_limits", DEFAULT_CONFIG["channel_limits"])
    prohibited = [str(p).lower() for p in cfg.get("prohibited_claims", DEFAULT_CONFIG["prohibited_claims"])]
    max_words_per_sent = int(cfg.get("max_avg_sentence_words", 22))

    violations: list[str] = []
    warnings: list[str] = []
    score = 100

    lowered = full_text.lower()
    for term in prohibited:
        if term in lowered:
            violations.append(f"Prohibited unsubstantiated claim: '{term}'")
            score -= 35

    if CLAIM_REQUIRES_DISCLAIMER.search(full_text) and not DISCLAIMER_MARKERS.search(combined):
        violations.append("Substantiation claim ('up to %' / ROI / financial rate) missing required disclaimer.")
        score -= 30

    if channel in limits:
        limit = int(limits[channel])
        target_len = len(headline) if "headline" in channel or "subject" in channel else len(full_text)
        if target_len > limit:
            warnings.append(f"Character limit exceeded for {channel}: {target_len} > {limit} chars.")
            score -= 15

    sentences = [s.strip() for s in re.split(r"[.!?]+", body) if s.strip()]
    avg_words = (sum(len(s.split()) for s in sentences) / len(sentences)) if sentences else 0.0
    if avg_words > max_words_per_sent:
        warnings.append(f"Dense readability: avg {avg_words:.1f} words/sentence (> {max_words_per_sent}).")
        score -= 10

    score = max(0, score)
    gate = "BLOCKED_COMPLIANCE_VIOLATION" if violations else ("WARNINGS_REVIEW" if warnings else "APPROVED_FOR_LOCALIZATION")

    return {
        "asset_id": aid,
        "channel": channel,
        "char_count_headline": len(headline),
        "char_count_total": len(full_text),
        "avg_sentence_words": round(avg_words, 1),
        "compliance_score": score,
        "violations": violations,
        "warnings": warnings,
        "publish_gate": gate,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    assets = data.get("assets") or ([data] if "body" in data or "headline" in data else [])
    linted = [_lint_asset(a, cfg) for a in assets]

    return {
        "skill": "brand-voice-compliance-gate",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "assets_linted": len(linted),
            "blocked_count": sum(1 for x in linted if x["publish_gate"] == "BLOCKED_COMPLIANCE_VIOLATION"),
            "warnings_count": sum(1 for x in linted if x["publish_gate"] == "WARNINGS_REVIEW"),
            "approved_count": sum(1 for x in linted if x["publish_gate"] == "APPROVED_FOR_LOCALIZATION"),
            "avg_compliance_score": round(sum(x["compliance_score"] for x in linted) / len(linted), 1) if linted else 0.0,
        },
        "asset_audits": linted,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Brand Voice & Claims Compliance Gate",
            "",
            f"- **Assets Linted:** {s['assets_linted']} | **Blocked:** {s['blocked_count']} | "
            f"**Approved:** {s['approved_count']} | **Avg Score:** {s['avg_compliance_score']:.1f}/100",
            "",
            "| Asset | Channel | Score | Gate | Findings |",
            "| :--- | :--- | ---: | :--- | :--- |",
        ]
    )
    for a in result["asset_audits"]:
        notes = "; ".join(a["violations"] + a["warnings"]) or "Clean"
        lines.append(
            f"| `{a['asset_id']}` | `{a['channel']}` | {a['compliance_score']} | `{a['publish_gate']}` | {notes} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint marketing copy for brand voice, claims, and channel limits.")
    parser.add_argument("--input", required=True, type=Path, help="Path to marketing copy assets JSON")
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
