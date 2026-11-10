#!/usr/bin/env python3
"""Matches prior authorization requests against clinical ICD-10, step therapy, and lab criteria."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "default_min_step_days": 30,
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
    def_step_days = int(cfg.get("default_min_step_days", 30))

    policies = {str(p["cpt_code"]).upper(): p for p in data.get("policies", []) if "cpt_code" in p}
    requests = data.get("requests", [])
    reviews: list[dict[str, Any]] = []

    for req in requests:
        aid = str(req.get("auth_id") or "PA-1")
        cpt = str(req.get("cpt_code") or "").upper().strip()
        pol = policies.get(cpt)
        if not pol:
            reviews.append(
                {
                    "auth_id": aid,
                    "cpt_code": cpt,
                    "criteria_met": False,
                    "recommendation": "UNMAPPED_POLICY_CLINICAL_REVIEW",
                    "met_items": [],
                    "gaps": [f"No payer medical policy rule found for CPT '{cpt}'."],
                }
            )
            continue

        icds = [str(c).upper().strip() for c in req.get("icd10_codes", [])]
        allowed_prefixes = [str(x).upper().strip() for x in pol.get("covered_icd10_prefixes", [])]
        icd_ok = (not allowed_prefixes) or any(any(code.startswith(pref) for pref in allowed_prefixes) for code in icds)

        min_trials = int(pol.get("min_step_therapy_trials", 0))
        min_days = int(pol.get("min_step_days_each", def_step_days))
        qualifying_steps = [
            s
            for s in req.get("step_therapy_history", [])
            if int(s.get("duration_days") or 0) >= min_days
            and str(s.get("outcome") or "").lower() in {"failed", "intolerant", "contraindicated"}
        ]
        step_ok = len(qualifying_steps) >= min_trials

        labs = {str(k).lower(): v for k, v in (req.get("diagnostic_labs") or {}).items()}
        req_labs = [str(l).lower() for l in pol.get("required_labs", [])]
        missing_labs = [l for l in req_labs if labs.get(l) in (None, "", False)]

        met_items: list[str] = []
        gaps: list[str] = []
        if icd_ok:
            met_items.append("Covered ICD-10 diagnosis matched")
        else:
            gaps.append(f"Diagnosis codes {icds} do not match covered prefixes {allowed_prefixes}.")

        if step_ok:
            met_items.append(f"Step therapy satisfied ({len(qualifying_steps)}/{min_trials} qualifying trials)")
        else:
            gaps.append(f"Step therapy shortfall: {len(qualifying_steps)} qualifying trials (>= {min_days}d), need {min_trials}.")

        if not missing_labs:
            met_items.append("All required diagnostic labs attached")
        else:
            gaps.append(f"Missing required diagnostic documentation: {', '.join(missing_labs)}.")

        all_met = icd_ok and step_ok and not missing_labs
        rec = "RECOMMEND_CLINICAL_APPROVAL" if all_met else ("PEER_REVIEW_MISSING_DOCS" if missing_labs else "MEDICAL_DIRECTOR_REVIEW")

        reviews.append(
            {
                "auth_id": aid,
                "cpt_code": cpt,
                "criteria_met": all_met,
                "recommendation": rec,
                "met_items": met_items,
                "gaps": gaps,
            }
        )

    return {
        "skill": "prior-auth-medical-necessity",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "requests_evaluated": len(reviews),
            "criteria_met_count": sum(1 for r in reviews if r["criteria_met"]),
            "gap_or_review_count": sum(1 for r in reviews if not r["criteria_met"]),
        },
        "prior_auth_reviews": reviews,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Prior Authorization Medical Necessity Checklist",
            "",
            f"- **Requests Evaluated:** {s['requests_evaluated']} | **All Criteria Met (HITL Ready):** {s['criteria_met_count']} | "
            f"**Gaps / Director Review:** {s['gap_or_review_count']}",
            "",
            "| Auth ID | CPT | Criteria Met | Recommendation | Gaps |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in result["prior_auth_reviews"]:
        lines.append(
            f"| `{r['auth_id']}` | `{r['cpt_code']}` | {'YES' if r['criteria_met'] else 'NO'} | "
            f"`{r['recommendation']}` | {'; '.join(r['gaps']) or 'None'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check prior authorization packets against payer clinical criteria.")
    parser.add_argument("--input", required=True, type=Path, help="Path to prior auth requests and policies JSON")
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
