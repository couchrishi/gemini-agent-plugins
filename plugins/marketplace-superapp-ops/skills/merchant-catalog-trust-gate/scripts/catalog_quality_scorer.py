#!/usr/bin/env python3
"""Scores merchant catalog listings for prohibited keywords, IPI injection, price outliers, and completeness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from statistics import median
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "min_images": 2,
    "low_price_ratio_threshold": 0.35,
    "high_price_multiplier_threshold": 4.0,
    "prohibited_terms": [
        "replica",
        "AAA clone",
        "1:1 copy",
        "unapproved prescription",
        "bypass safety",
        "unlocked stolen",
    ],
    "required_attributes": ["brand", "gtin", "country_of_origin"],
}

IPI_PATTERN = re.compile(
    r"(ignore\s+previous\s+instructions|system\s+override|auto-?approve\s+all|bypass\s+trust\s+check)",
    re.IGNORECASE,
)


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

    listings = data.get("listings") or []
    cat_medians: dict[str, float] = {k: float(v) for k, v in (data.get("category_medians_usd") or {}).items()}
    min_imgs = int(cfg.get("min_images", 2))
    low_ratio = float(cfg.get("low_price_ratio_threshold", 0.35))
    high_mult = float(cfg.get("high_price_multiplier_threshold", 4.0))
    prohibited = [t.lower() for t in cfg.get("prohibited_terms", DEFAULT_CONFIG["prohibited_terms"])]
    req_attrs = list(cfg.get("required_attributes", DEFAULT_CONFIG["required_attributes"]))

    # Derive category medians dynamically when missing from payload
    prices_by_cat: dict[str, list[float]] = {}
    for row in listings:
        cat = str(row.get("category") or "general")
        price = float(row.get("price_usd") or 0.0)
        if price > 0:
            prices_by_cat.setdefault(cat, []).append(price)
    for cat, plist in prices_by_cat.items():
        if cat not in cat_medians and len(plist) >= 3:
            cat_medians[cat] = float(median(plist))

    evaluated: list[dict[str, Any]] = []
    for row in listings:
        lid = str(row.get("listing_id") or "LST-1")
        merchant_id = str(row.get("merchant_id") or "MRC-1")
        cat = str(row.get("category") or "general")
        title = str(row.get("title") or "")
        desc = str(row.get("description") or "")
        combined = f"{title} {desc}"
        price = float(row.get("price_usd") or 0.0)
        img_count = int(row.get("image_count") or 0)
        attrs = row.get("attributes") or {}

        flags: list[str] = []
        severity = "LOW"

        if IPI_PATTERN.search(combined):
            flags.append("PROMPT_INJECTION_SIGNAL")
            severity = "CRITICAL"
        for term in prohibited:
            if term in combined.lower():
                flags.append(f"PROHIBITED_TERM:{term}")
                severity = "CRITICAL"

        med = cat_medians.get(cat)
        price_ratio = round(price / med, 2) if (med and med > 0 and price > 0) else None
        if price <= 0:
            flags.append("INVALID_ZERO_PRICE")
            severity = "CRITICAL"
        elif price_ratio is not None:
            if price_ratio < low_ratio:
                flags.append(f"COUNTERFEIT_LOW_PRICE_OUTLIER ({price_ratio:.2f}x median)")
                if severity != "CRITICAL":
                    severity = "HIGH"
            elif price_ratio > high_mult:
                flags.append(f"PRICE_GOUGING_OUTLIER ({price_ratio:.2f}x median)")
                if severity != "CRITICAL":
                    severity = "HIGH"

        missing_attrs = [a for a in req_attrs if not str(attrs.get(a) or "").strip()]
        if missing_attrs:
            flags.append(f"MISSING_ATTRIBUTES:{','.join(missing_attrs)}")
            if severity == "LOW":
                severity = "MEDIUM"
        if img_count < min_imgs:
            flags.append(f"INSUFFICIENT_IMAGES ({img_count} < {min_imgs})")
            if severity == "LOW":
                severity = "MEDIUM"

        completeness = round(
            ((len(req_attrs) - len(missing_attrs)) / len(req_attrs) * 100.0) if req_attrs else 100.0, 1
        )
        if severity == "CRITICAL":
            decision = "REJECT_TRUST_HOLD"
        elif severity in {"HIGH", "MEDIUM"}:
            decision = "MANUAL_TRUST_REVIEW"
        else:
            decision = "ELIGIBLE_TO_PUBLISH"

        evaluated.append(
            {
                "listing_id": lid,
                "merchant_id": merchant_id,
                "category": cat,
                "price_usd": round(price, 2),
                "category_median_usd": round(med, 2) if med else None,
                "price_to_median_ratio": price_ratio,
                "attribute_completeness_pct": completeness,
                "risk_severity": severity,
                "decision": decision,
                "flags": flags,
            }
        )

    evaluated.sort(key=lambda x: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[x["risk_severity"]], x["listing_id"]))
    return {
        "skill": "merchant-catalog-trust-gate",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "listings_screened": len(evaluated),
            "rejected_trust_hold": sum(1 for e in evaluated if e["decision"] == "REJECT_TRUST_HOLD"),
            "manual_review_required": sum(1 for e in evaluated if e["decision"] == "MANUAL_TRUST_REVIEW"),
            "clean_publish_eligible": sum(1 for e in evaluated if e["decision"] == "ELIGIBLE_TO_PUBLISH"),
        },
        "listing_evaluations": evaluated,
        "truncation_warnings": ["Catalog feed truncated; unscreened SKUs must stay held in draft."] if data.get("truncated") else [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Merchant Catalog Trust & Compliance Gate",
            "",
            f"- **Screened:** {s['listings_screened']} | **Rejected (Trust Hold):** {s['rejected_trust_hold']} | "
            f"**Manual Review:** {s['manual_review_required']} | **Clean Eligible:** {s['clean_publish_eligible']}",
            "",
            "| Listing | Merchant | Category | Price | Ratio vs Med | Completeness | Decision | Flags |",
            "| :--- | :--- | :--- | ---: | ---: | ---: | :--- | :--- |",
        ]
    )
    for e in result["listing_evaluations"]:
        ratio_s = f"{e['price_to_median_ratio']:.2f}x" if e["price_to_median_ratio"] is not None else "N/A"
        lines.append(
            f"| `{e['listing_id']}` | `{e['merchant_id']}` | {e['category']} | ${e['price_usd']:,.2f} | "
            f"{ratio_s} | {e['attribute_completeness_pct']:.0f}% | `{e['decision']}` | {', '.join(e['flags']) or 'None'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score merchant catalog trust, IPI signals, and price outliers.")
    parser.add_argument("--input", required=True, type=Path, help="Path to merchant catalog listings JSON")
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
