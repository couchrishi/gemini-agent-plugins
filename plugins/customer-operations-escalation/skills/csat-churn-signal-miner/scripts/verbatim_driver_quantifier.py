#!/usr/bin/env python3
"""Mines CSAT/NPS verbatims into taxonomy drivers weighted by ARR with null-rating denominator hygiene."""

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
    "detractor_csat_max": 2,
    "detractor_nps_max": 6,
}

DRIVER_TAXONOMY = {
    "latency_reliability": ("timeout", "outage", "slow", "latency", "downtime", "crash", "500"),
    "support_responsiveness": ("support", "ticket", "sla", "wait", "unresponsive", "escalation", "handoff"),
    "billing_pricing": ("invoice", "billing", "expensive", "price", "overcharge", "renewal uplift", "hidden fee"),
    "onboarding_complexity": ("onboarding", "setup", "documentation", "confusing", "implementation", "hard to configure"),
    "missing_product_feature": ("missing", "feature", "integration", "api", "unsupported", "roadmap"),
    "security_compliance": ("sso", "audit", "soc2", "privacy", "permission", "rbac", "security"),
}
CHURN_SIGNAL_RE = re.compile(r"\b(cancel|churn|switching\s+to|evaluating\s+competitor|not\s+renewing|terminate)\b", re.I)


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
    det_csat = int(cfg.get("detractor_csat_max", 2))
    det_nps = int(cfg.get("detractor_nps_max", 6))

    responses = data.get("responses", [])
    csat_vals: list[float] = []
    nps_vals: list[int] = []
    unrated_csat = 0
    promoters = passives = detractors = 0

    driver_stats: dict[str, dict[str, Any]] = {}
    churn_alerts: list[dict[str, Any]] = []

    for r in responses:
        rid = str(r.get("response_id") or "RESP-1")
        acct = str(r.get("account_id") or r.get("account_name") or "ACCT")
        arr = float(r.get("arr_usd") or 0.0)
        csat = r.get("csat_score")
        nps = r.get("nps_score")
        text = str(r.get("verbatim") or "")
        low = text.lower()

        if csat is None:
            unrated_csat += 1
        else:
            csat_vals.append(float(csat))

        is_detractor = False
        if nps is not None:
            n = int(nps)
            nps_vals.append(n)
            if n >= 9:
                promoters += 1
            elif n >= 7:
                passives += 1
            else:
                detractors += 1
                is_detractor = True
        elif csat is not None and float(csat) <= det_csat:
            is_detractor = True

        matched_themes = [theme for theme, kws in DRIVER_TAXONOMY.items() if any(kw in low for kw in kws)]
        if not matched_themes and text.strip():
            matched_themes = ["general_feedback"]

        for theme in matched_themes:
            bucket = driver_stats.setdefault(theme, {"driver": theme, "mention_count": 0, "detractor_mentions": 0, "arr_exposed_usd": 0.0})
            bucket["mention_count"] += 1
            if is_detractor:
                bucket["detractor_mentions"] += 1
                bucket["arr_exposed_usd"] += arr

        if CHURN_SIGNAL_RE.search(text):
            churn_alerts.append({"response_id": rid, "account": acct, "arr_usd": round(arr, 2), "excerpt": text[:160]})

    avg_csat = round(sum(csat_vals) / len(csat_vals), 2) if csat_vals else None
    nps_score = round(((promoters - detractors) / len(nps_vals)) * 100.0, 1) if nps_vals else None
    driver_pareto = sorted(driver_stats.values(), key=lambda d: (-d["arr_exposed_usd"], -d["mention_count"]))
    for d in driver_pareto:
        d["arr_exposed_usd"] = round(d["arr_exposed_usd"], 2)

    return {
        "skill": "csat-churn-signal-miner",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "total_responses": len(responses),
            "rated_csat_count": len(csat_vals),
            "unrated_csat_excluded": unrated_csat,
            "avg_csat": avg_csat,
            "nps_score": nps_score,
            "churn_signal_count": len(churn_alerts),
            "churn_signal_arr_usd": round(sum(c["arr_usd"] for c in churn_alerts), 2),
        },
        "driver_pareto": driver_pareto,
        "churn_alerts": churn_alerts,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# CSAT/NPS Verbatim Driver & Churn Signal Report",
            "",
            f"- **Responses:** {s['total_responses']} (Rated CSAT: {s['rated_csat_count']}, Null Excluded: {s['unrated_csat_excluded']}) | "
            f"**Avg CSAT:** {s['avg_csat'] or 'N/A'} | **NPS:** {s['nps_score'] if s['nps_score'] is not None else 'N/A'}",
            f"- **Explicit Churn Alerts:** {s['churn_signal_count']} (${s['churn_signal_arr_usd']:,.2f} ARR)",
            "",
            "| Driver Theme | Mentions | Detractor Mentions | Exposed ARR (USD) |",
            "| :--- | ---: | ---: | ---: |",
        ]
    )
    for d in result["driver_pareto"]:
        lines.append(f"| `{d['driver']}` | {d['mention_count']} | {d['detractor_mentions']} | ${d['arr_exposed_usd']:,.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quantify CSAT/NPS verbatim drivers and ARR churn signals.")
    parser.add_argument("--input", required=True, type=Path, help="Path to survey responses JSON")
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
