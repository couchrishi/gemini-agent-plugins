#!/usr/bin/env python3
"""Maps regulatory mandates against internal compliance controls and identifies uncovered/stale gaps."""

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
    "max_control_evidence_days": 365,
}
SEVERITY_WEIGHT = {"CRITICAL": 4.0, "HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}


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
    as_of_date: str | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)
    max_ev_days = int(cfg.get("max_control_evidence_days", 365))

    articles = data.get("articles", [])
    controls = data.get("controls", [])

    # Index controls by mapped article_id and also evaluate individual control freshness
    article_to_controls: dict[str, list[dict[str, Any]]] = {}
    control_health: dict[str, dict[str, Any]] = {}
    for ctrl in controls:
        cid = str(ctrl.get("control_id") or "CTRL-1")
        tested_dt = _parse_date(ctrl.get("last_tested_date"))
        ev_uri = str(ctrl.get("evidence_uri") or "").strip()
        raw_status = str(ctrl.get("control_status") or "UNKNOWN").upper()
        age_days = (as_of - tested_dt).days if tested_dt else None
        missing_ev = tested_dt is None or not ev_uri
        stale_ev = age_days is not None and age_days > max_ev_days

        if raw_status == "NOT_IMPLEMENTED":
            eff_status = "NOT_IMPLEMENTED"
        elif raw_status == "FAILED":
            eff_status = "FAILED"
        elif missing_ev:
            eff_status = "UNVERIFIED_MISSING_EVIDENCE"
        elif stale_ev:
            eff_status = "STALE_EVIDENCE"
        elif raw_status == "PARTIAL":
            eff_status = "PARTIAL"
        else:
            eff_status = "PASSING"

        info = {
            "control_id": cid,
            "domain": str(ctrl.get("domain") or "general").lower(),
            "owner": str(ctrl.get("owner") or "Unassigned"),
            "effective_status": eff_status,
            "evidence_age_days": age_days,
            "last_tested_date": tested_dt.isoformat() if tested_dt else None,
        }
        control_health[cid] = info
        for aid in ctrl.get("mapped_articles", []):
            article_to_controls.setdefault(str(aid), []).append(info)

    mappings: list[dict[str, Any]] = []
    remediation_queue: list[dict[str, Any]] = []

    for art in articles:
        aid = str(art.get("article_id") or "ART-1")
        reg = str(art.get("regulation") or "Regulation")
        title = str(art.get("title") or aid)
        sev = str(art.get("severity") or "HIGH").upper()
        req_domains = {str(d).lower() for d in art.get("required_domains", [])}

        linked = article_to_controls.get(aid, [])
        active_impl = [c for c in linked if c["effective_status"] != "NOT_IMPLEMENTED"]
        covered_domains = {c["domain"] for c in active_impl}
        missing_domains = sorted(req_domains - covered_domains)

        bad_controls = [
            c
            for c in linked
            if c["effective_status"] in {"FAILED", "UNVERIFIED_MISSING_EVIDENCE", "STALE_EVIDENCE", "NOT_IMPLEMENTED"}
        ]
        partial_controls = [c for c in linked if c["effective_status"] == "PARTIAL"]

        if not active_impl:
            status = "UNCOVERED_GAP"
        elif bad_controls:
            status = "FAILING_OR_STALE_EVIDENCE"
        elif missing_domains or partial_controls:
            status = "PARTIAL_COVERAGE"
        else:
            status = "COMPLIANT_COVERED"

        base_sev = SEVERITY_WEIGHT.get(sev, 2.0)
        status_mult = {
            "UNCOVERED_GAP": 3.0,
            "FAILING_OR_STALE_EVIDENCE": 2.5,
            "PARTIAL_COVERAGE": 1.5,
            "COMPLIANT_COVERED": 0.0,
        }[status]
        priority_score = round(base_sev * status_mult * (1.0 + 0.25 * len(missing_domains)), 2)

        entry = {
            "article_id": aid,
            "regulation": reg,
            "title": title,
            "severity": sev,
            "coverage_status": status,
            "mapped_control_ids": [c["control_id"] for c in linked],
            "missing_domains": missing_domains,
            "stale_or_unverified_controls": [
                c["control_id"]
                for c in bad_controls
                if c["effective_status"] in {"UNVERIFIED_MISSING_EVIDENCE", "STALE_EVIDENCE"}
            ],
            "remediation_priority_score": priority_score,
        }
        mappings.append(entry)
        if status != "COMPLIANT_COVERED":
            remediation_queue.append(
                {
                    "article_id": aid,
                    "regulation": reg,
                    "severity": sev,
                    "coverage_status": status,
                    "priority_score": priority_score,
                    "action": (
                        f"Implement control for domains {missing_domains}"
                        if status == "UNCOVERED_GAP" or missing_domains
                        else f"Refresh evidence / remediate controls {entry['stale_or_unverified_controls'] or entry['mapped_control_ids']}"
                    ),
                }
            )

    remediation_queue.sort(key=lambda r: -r["priority_score"])
    total_arts = len(mappings)
    compliant_cnt = sum(1 for m in mappings if m["coverage_status"] == "COMPLIANT_COVERED")
    compliance_pct = (compliant_cnt / total_arts * 100.0) if total_arts > 0 else 0.0

    return {
        "skill": "regulatory-change-mapper",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "articles_evaluated": total_arts,
            "compliant_count": compliant_cnt,
            "uncovered_gap_count": sum(1 for m in mappings if m["coverage_status"] == "UNCOVERED_GAP"),
            "failing_or_stale_count": sum(
                1 for m in mappings if m["coverage_status"] == "FAILING_OR_STALE_EVIDENCE"
            ),
            "partial_coverage_count": sum(1 for m in mappings if m["coverage_status"] == "PARTIAL_COVERAGE"),
            "overall_compliance_pct": round(compliance_pct, 2),
        },
        "article_mappings": mappings,
        "remediation_queue": remediation_queue,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Regulatory Change & Control Gap Matrix (As Of {result['as_of_date']})",
            "",
            f"- **Articles Evaluated:** {s['articles_evaluated']} | **Compliance Rate:** {s['overall_compliance_pct']:.1f}%",
            f"- **Uncovered Gaps:** {s['uncovered_gap_count']} | **Failing/Stale Controls:** {s['failing_or_stale_count']} | "
            f"**Partial:** {s['partial_coverage_count']}",
            "",
            "| Article | Regulation | Severity | Status | Mapped Controls | Missing Domains | Priority |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | ---: |",
        ]
    )
    for m in result["article_mappings"]:
        ctrls = ", ".join(m["mapped_control_ids"]) or "NONE"
        miss = ", ".join(m["missing_domains"]) or "—"
        lines.append(
            f"| `{m['article_id']}` | {m['regulation']} | {m['severity']} | `{m['coverage_status']}` | "
            f"{ctrls} | {miss} | {m['remediation_priority_score']:.1f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map regulatory mandates to compliance controls and find gaps.")
    parser.add_argument("--input", required=True, type=Path, help="Path to regulatory & controls JSON")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--as-of", type=str, help="Reference ISO date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, as_of_date=args.as_of)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
