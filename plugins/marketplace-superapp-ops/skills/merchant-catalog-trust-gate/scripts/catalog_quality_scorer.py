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
) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"listings": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="merchant-catalog-trust-gate", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"listings": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"listings": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)

    listings = data.get("listings") or []
    cat_medians: dict[str, float] = {str(k): val for k, v in _as_dict(data.get("category_medians_usd")).items() for val in [_to_opt_float(v)] if val is not None}
    min_imgs = _to_int(cfg.get("min_images"), 2)
    low_ratio = _to_float(cfg.get("low_price_ratio_threshold"), 0.35)
    high_mult = _to_float(cfg.get("high_price_multiplier_threshold"), 4.0)
    prohibited = [t.lower() for t in cfg.get("prohibited_terms", DEFAULT_CONFIG["prohibited_terms"])]
    req_attrs = list(cfg.get("required_attributes", DEFAULT_CONFIG["required_attributes"]))

    # Derive category medians dynamically when missing from payload
    prices_by_cat: dict[str, list[float]] = {}
    for row in listings:
        cat = str(row.get("category") or "general")
        price = _to_float(row.get("price_usd"), 0.0)
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
        price = _to_float(row.get("price_usd"), 0.0)
        img_count = _to_int(row.get("image_count"), 0)
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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated), existing=["Catalog feed truncated; unscreened SKUs must stay held in draft."] if data.get("truncated") else []),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score merchant catalog trust, IPI signals, and price outliers.")
    parser.add_argument("--input", required=True, type=Path, help="Path to merchant catalog listings JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, sheet=args.sheet)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
