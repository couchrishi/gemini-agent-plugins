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
        return {"assets": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="brand-voice-compliance-gate", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"assets": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"assets": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _lint_asset(asset: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    aid = str(asset.get("asset_id") or "ASSET-1")
    channel = str(asset.get("channel") or "linkedin_post").lower().strip()
    headline = str(asset.get("headline") or "")
    body = str(asset.get("body") or "")
    disclaimer = str(asset.get("disclaimer") or "")
    full_text = f"{headline} {body}".strip()
    combined = f"{full_text} {disclaimer}".strip()

    limits = _as_dict(cfg.get("channel_limits"), DEFAULT_CONFIG["channel_limits"])
    prohibited = [str(p).lower() for p in cfg.get("prohibited_claims", DEFAULT_CONFIG["prohibited_claims"])]
    max_words_per_sent = _to_int(cfg.get("max_avg_sentence_words"), 22)

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
        limit = _to_int(limits.get(channel), 0)
        target_len = len(headline) if "headline" in channel or "subject" in channel else len(full_text)
        if limit > 0 and target_len > limit:
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

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(assets)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint marketing copy for brand voice, claims, and channel limits.")
    parser.add_argument("--input", required=True, type=Path, help="Path to marketing copy assets JSON")
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
