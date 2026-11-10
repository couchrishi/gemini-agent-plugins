#!/usr/bin/env python3
"""Matches open consulting project demands against bench talent skills, availability, and target margin."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_skill_overlap_pct": 60.0,
    "max_start_delay_days": 14,
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


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return date.fromisoformat(s[:10]) if s else None


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    min_overlap = float(cfg.get("min_skill_overlap_pct", 60.0))
    max_delay = int(cfg.get("max_start_delay_days", 14))

    demands = data.get("demands", [])
    consultants = data.get("consultants", [])

    role_matches: list[dict[str, Any]] = []
    unfilled_count = 0

    for d in demands:
        rid = str(d.get("role_id") or "ROLE-1")
        proj = str(d.get("project_name") or "Engagement")
        req_skills = {str(s).lower().strip() for s in d.get("required_skills", [])}
        pref_loc = str(d.get("location_pref") or "").lower().strip()
        need_dt = _parse_date(d.get("start_date"))
        target_bill = float(d.get("target_bill_rate_hourly") or 0.0)

        candidates: list[dict[str, Any]] = []
        for c in consultants:
            c_skills = {str(s).lower().strip() for s in c.get("skills", [])}
            overlap = (len(req_skills & c_skills) / len(req_skills) * 100.0) if req_skills else 100.0
            avail_dt = _parse_date(c.get("available_from"))
            delay_days = max(0, (avail_dt - need_dt).days) if (avail_dt and need_dt) else 0
            c_loc = str(c.get("location") or "").lower().strip()
            loc_bonus = 10.0 if (not pref_loc or pref_loc == c_loc or pref_loc == "any") else 0.0
            cost_hr = float(c.get("cost_rate_hourly") or 0.0)
            margin_pct = ((target_bill - cost_hr) / target_bill * 100.0) if target_bill > 0 else 0.0

            if overlap < min_overlap or delay_days > max_delay:
                continue

            composite = round(overlap * 0.7 + margin_pct * 0.2 + loc_bonus - delay_days, 2)
            candidates.append(
                {
                    "consultant_id": str(c.get("consultant_id")),
                    "name": str(c.get("name") or c.get("consultant_id")),
                    "grade": str(c.get("grade") or ""),
                    "location": str(c.get("location") or ""),
                    "skill_match_pct": round(overlap, 1),
                    "start_delay_days": delay_days,
                    "estimated_margin_pct": round(margin_pct, 1),
                    "composite_fit_score": composite,
                }
            )

        candidates.sort(key=lambda x: -x["composite_fit_score"])
        status = "MATCHED_INTERNAL_BENCH" if candidates else "EXTERNAL_SUBCONTRACT_REQUIRED"
        if not candidates:
            unfilled_count += 1

        role_matches.append(
            {
                "role_id": rid,
                "project_name": proj,
                "required_skills": sorted(req_skills),
                "fill_status": status,
                "shortlisted_candidates": candidates[:3],
            }
        )

    return {
        "skill": "bench-skill-demand-matcher",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "demands_evaluated": len(demands),
            "consultants_screened": len(consultants),
            "filled_internally_count": len(demands) - unfilled_count,
            "external_subcontract_required_count": unfilled_count,
        },
        "role_matches": role_matches,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Bench Talent & Project Demand Match Report",
            "",
            f"- **Open Demands:** {s['demands_evaluated']} | **Internal Match:** {s['filled_internally_count']} | "
            f"**Subcontract Gaps:** {s['external_subcontract_required_count']}",
            "",
            "| Role ID | Project | Status | Top Candidate | Match % | Margin % |",
            "| :--- | :--- | :--- | :--- | ---: | ---: |",
        ]
    )
    for rm in result["role_matches"]:
        top = rm["shortlisted_candidates"][0] if rm["shortlisted_candidates"] else None
        cand_name = f"{top['name']} (`{top['consultant_id']}`)" if top else "None"
        m_pct = f"{top['skill_match_pct']:.1f}%" if top else "—"
        gm_pct = f"{top['estimated_margin_pct']:.1f}%" if top else "—"
        lines.append(f"| `{rm['role_id']}` | {rm['project_name']} | `{rm['fill_status']}` | {cand_name} | {m_pct} | {gm_pct} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match consulting demand seats to bench consultants.")
    parser.add_argument("--input", required=True, type=Path, help="Path to demands and bench JSON")
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
