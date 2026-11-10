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
        return {"candidates": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="structured-hiring-rubric", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"candidates": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"candidates": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _audit_candidate(cand: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    cid = str(cand.get("candidate_id") or "CAND-1")
    name = str(cand.get("candidate_name") or cid)
    role = str(cand.get("role") or "Unspecified Role")
    panel = _as_list(cand.get("interviewers"))

    max_spread_limit = _to_float(cfg.get("max_score_spread"), 2.0)
    min_ev_chars = _to_int(cfg.get("min_evidence_chars"), 40)
    hire_thresh = _to_float(cfg.get("hire_mean_threshold"), 3.0)

    scores: list[float] = []
    thin_evidence: list[str] = []
    bias_flags: list[dict[str, str]] = []
    invalid_scores: list[str] = []
    strong_no_hire_present = False

    for idx, iv in enumerate(panel):
        iid = str(iv.get("interviewer_id") or f"IV-{idx + 1}")
        comp = str(iv.get("competency") or "General")
        raw_score = _to_opt_float(iv.get("score"))
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

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated)),
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check hiring scorecards for dispersion, thin evidence, and bias.")
    parser.add_argument("--input", required=True, type=Path, help="Path to candidate scorecards JSON")
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
