#!/usr/bin/env python3
"""Audits structured interview scorecards for score dispersion, thin evidence, and bias signals."""

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
    "max_score_spread": 2.0,
    "min_evidence_chars": 40,
    "hire_mean_threshold": 3.0,
}

BIAS_PATTERNS = [
    (re.compile(r"\b(\d{2}\s*years?\s*old|too\s+(old|young)|digital\s+native|recent\s+grad\s+energy)\b", re.I), "Age proxy"),
    (re.compile(r"\b(pregnant|maternity|paternity|childcare|married|single\s+parent|family\s+plans)\b", re.I), "Family/marital status"),
    (re.compile(r"\b(native\s+english\s+speaker|foreign\s+accent|heavy\s+accent)\b", re.I), "National origin/accent"),
    (re.compile(r"\b(culture\s+fit|beers?\s+test|guys?\s+guy|aggressive\s+female)\b", re.I), "Subjective/gendered affinity"),
]
GENERIC_PHRASES = ("great fit", "smart candidate", "good vibes", "nice person", "seems solid", "liked them")


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


def _audit_candidate(cand: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    cid = str(cand.get("candidate_id") or "CAND-1")
    name = str(cand.get("candidate_name") or cid)
    role = str(cand.get("role") or "Unspecified Role")
    panel = cand.get("interviewers", [])

    max_spread_limit = float(cfg.get("max_score_spread", 2.0))
    min_ev_chars = int(cfg.get("min_evidence_chars", 40))
    hire_thresh = float(cfg.get("hire_mean_threshold", 3.0))

    scores: list[float] = []
    thin_evidence: list[str] = []
    bias_flags: list[dict[str, str]] = []
    invalid_scores: list[str] = []
    strong_no_hire_present = False

    for idx, iv in enumerate(panel):
        iid = str(iv.get("interviewer_id") or f"IV-{idx + 1}")
        comp = str(iv.get("competency") or "General")
        raw_score = iv.get("score")
        ev = str(iv.get("evidence_text") or "").strip()

        if raw_score is None or not (1.0 <= float(raw_score) <= 4.0):
            invalid_scores.append(f"{iid} ({comp}): invalid/missing score {raw_score!r}")
        else:
            s_val = float(raw_score)
            scores.append(s_val)
            if s_val <= 1.0:
                strong_no_hire_present = True

        if len(ev) < min_ev_chars or (len(ev) < 80 and any(g in ev.lower() for g in GENERIC_PHRASES)):
            thin_evidence.append(f"{iid} ({comp}): {len(ev)} chars (< {min_ev_chars} min behavioral evidence)")

        for pat, label in BIAS_PATTERNS:
            m = pat.search(ev)
            if m:
                bias_flags.append({"interviewer_id": iid, "category": label, "matched_phrase": m.group(0)})

    mean_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    spread = round(max(scores) - min(scores), 2) if len(scores) >= 2 else 0.0
    dispersion_alert = spread >= max_spread_limit

    if not scores:
        status = "INCOMPLETE_NO_SCORES"
    elif bias_flags or thin_evidence or invalid_scores:
        status = "CALIBRATION_BLOCKED_BIAS_OR_THIN_EVIDENCE"
    elif dispersion_alert or strong_no_hire_present:
        status = "DEBRIEF_REQUIRED_SPLIT_PANEL"
    elif mean_score >= hire_thresh:
        status = "HIRE_RECOMMENDED_FOR_HITL"
    else:
        status = "NO_HIRE_CONSENSUS"

    return {
        "candidate_id": cid,
        "candidate_name": name,
        "role": role,
        "interviewer_count": len(panel),
        "scores": scores,
        "mean_score": mean_score,
        "score_spread": spread,
        "dispersion_alert": dispersion_alert,
        "strong_no_hire_veto": strong_no_hire_present,
        "thin_evidence_flags": thin_evidence,
        "bias_flags": bias_flags,
        "invalid_scores": invalid_scores,
        "calibration_status": status,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    candidates = data.get("candidates") or ([data] if "interviewers" in data else [])
    evaluated = [_audit_candidate(c, cfg) for c in candidates]

    return {
        "skill": "structured-hiring-rubric",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "candidates_reviewed": len(evaluated),
            "hire_recommended_count": sum(1 for e in evaluated if e["calibration_status"] == "HIRE_RECOMMENDED_FOR_HITL"),
            "debrief_required_count": sum(1 for e in evaluated if e["calibration_status"] == "DEBRIEF_REQUIRED_SPLIT_PANEL"),
            "blocked_bias_or_evidence_count": sum(
                1 for e in evaluated if e["calibration_status"] == "CALIBRATION_BLOCKED_BIAS_OR_THIN_EVIDENCE"
            ),
            "total_bias_flags": sum(len(e["bias_flags"]) for e in evaluated),
        },
        "candidate_calibrations": evaluated,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Structured Hiring Rubric & Panel Calibration Audit",
            "",
            f"- **Candidates Reviewed:** {s['candidates_reviewed']} | **Hire Ready (HITL):** {s['hire_recommended_count']} | "
            f"**Debrief Required:** {s['debrief_required_count']} | **Blocked (Bias/Thin Evidence):** {s['blocked_bias_or_evidence_count']}",
            "",
            "| Candidate | Role | Panel | Mean | Spread | Bias Flags | Thin Evidence | Calibration Status |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for c in result["candidate_calibrations"]:
        lines.append(
            f"| `{c['candidate_id']}` {c['candidate_name']} | {c['role']} | {c['interviewer_count']} | "
            f"{c['mean_score']:.2f} | {c['score_spread']:.1f} | {len(c['bias_flags'])} | "
            f"{len(c['thin_evidence_flags'])} | `{c['calibration_status']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check hiring scorecards for dispersion, thin evidence, and bias.")
    parser.add_argument("--input", required=True, type=Path, help="Path to candidate scorecards JSON")
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
