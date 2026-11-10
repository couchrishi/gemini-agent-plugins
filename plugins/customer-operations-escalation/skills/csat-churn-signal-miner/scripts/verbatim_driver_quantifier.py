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
        return {"responses": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="csat-churn-signal-miner", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"responses": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"responses": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    det_csat = _to_int(cfg.get("detractor_csat_max"), 2)
    det_nps = _to_int(cfg.get("detractor_nps_max"), 6)

    responses = _as_list(data.get("responses"))
    csat_vals: list[float] = []
    nps_vals: list[int] = []
    unrated_csat = 0
    promoters = passives = detractors = 0

    driver_stats: dict[str, dict[str, Any]] = {}
    churn_alerts: list[dict[str, Any]] = []

    for r in responses:
        rid = str(r.get("response_id") or "RESP-1")
        acct = str(r.get("account_id") or r.get("account_name") or "ACCT")
        arr = _to_float(r.get("arr_usd"), 0.0)
        csat = _to_opt_float(r.get("csat_score"))
        nps = _to_opt_int(r.get("nps_score"))
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
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quantify CSAT/NPS verbatim drivers and ARR churn signals.")
    parser.add_argument("--input", required=True, type=Path, help="Path to survey responses JSON")
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
