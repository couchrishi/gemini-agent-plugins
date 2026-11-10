#!/usr/bin/env python3
"""Lints SOW deliverables and clauses for open-ended scope creep, missing acceptance criteria, and margin breaches."""

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
    "min_sow_gross_margin_pct": 30.0,
    "critical_margin_floor_pct": 20.0,
    "max_acceptance_business_days": 10,
}

SCOPE_CREEP_PATTERNS = [
    (re.compile(r"\ball\s+work\s+required\b", re.I), "Unbounded 'all work required' obligation"),
    (re.compile(r"\bunlimited\s+(revisions|changes|support)\b", re.I), "Unlimited revisions/changes clause"),
    (re.compile(r"\bsole\s+and\s+absolute\s+satisfaction\b", re.I), "Subjective acceptance veto"),
    (re.compile(r"\bno\s+additional\s+cost\s+regardless\b", re.I), "Fixed-fee uncapped change exposure"),
]


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
        return {"deliverables": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="sow-scope-margin-auditor", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"deliverables": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"deliverables": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)

    min_margin = _to_float(cfg.get("min_sow_gross_margin_pct"), 30.0)
    crit_margin = _to_float(cfg.get("critical_margin_floor_pct"), 20.0)
    max_accept_days = _to_int(cfg.get("max_acceptance_business_days"), 10)

    fee = _to_float(data.get("fixed_fee_usd"), 0.0)
    cost = _to_float(data.get("estimated_cost_usd"), 0.0)
    margin_pct = ((fee - cost) / fee * 100.0) if fee > 0 else 0.0
    accept_days = _to_opt_int(data.get("acceptance_business_days"))

    blockers: list[str] = []
    warnings: list[str] = []
    clause_hits: list[dict[str, Any]] = []

    if margin_pct < crit_margin:
        blockers.append(f"SOW gross margin {margin_pct:.1f}% breaches hard {crit_margin:.0f}% floor (Score 9).")
    elif margin_pct < min_margin:
        warnings.append(f"SOW gross margin {margin_pct:.1f}% sits below {min_margin:.0f}% standard target (Score 3).")

    if accept_days is None:
        warnings.append("Milestone acceptance window omitted (deemed acceptance not bounded).")
    elif int(accept_days) > max_accept_days:
        warnings.append(f"Acceptance window {accept_days} business days exceeds {max_accept_days}-day ceiling.")

    for c in _as_list(data.get("clauses")):
        cid = str(c.get("clause_id") or "CL")
        txt = str(c.get("text") or "")
        for pat, desc in SCOPE_CREEP_PATTERNS:
            if pat.search(txt):
                blockers.append(f"Clause {cid}: {desc}")
                clause_hits.append({"clause_id": cid, "issue": desc, "severity": 9})

    missing_criteria: list[str] = []
    for d in _as_list(data.get("deliverables")):
        did = str(d.get("deliverable_id") or "DELIV")
        if not str(d.get("acceptance_criteria") or "").strip():
            missing_criteria.append(did)
            warnings.append(f"Deliverable {did} lacks objective acceptance criteria.")

    if not data.get("client_dependencies"):
        warnings.append("SOW omits Client Dependencies & Assumptions schedule.")

    gate = "BLOCKED_SCORE_9" if blockers else ("REDLINES_REQUIRED" if warnings else "READY_FOR_EXECUTION")

    return {
        "skill": "sow-scope-margin-auditor",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "sow_id": str(data.get("sow_id") or "SOW-1"),
            "fixed_fee_usd": round(fee, 2),
            "estimated_cost_usd": round(cost, 2),
            "gross_margin_pct": round(margin_pct, 2),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "missing_acceptance_criteria_count": len(missing_criteria),
            "sow_gate_status": gate,
        },
        "blockers": blockers,
        "warnings": warnings,
        "clause_risk_hits": clause_hits,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# SOW Scope Creep & Margin Audit — `{s['sow_id']}`",
            "",
            f"- **Fixed Fee:** ${s['fixed_fee_usd']:,.2f} | **Est Cost:** ${s['estimated_cost_usd']:,.2f} | "
            f"**Gross Margin:** {s['gross_margin_pct']:.2f}% | **Gate:** `{s['sow_gate_status']}`",
            f"- **Score-9 Blockers:** {s['blocker_count']} | **Negotiable Warnings:** {s['warning_count']}",
        ]
    )
    if result["blockers"]:
        lines.extend(["", "## Walk-Away Scope/Margin Blockers"])
        lines.extend(f"- {b}" for b in result["blockers"])
    if result["warnings"]:
        lines.extend(["", "## Redline Warnings"])
        lines.extend(f"- {w}" for w in result["warnings"])
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit SOW clauses for open-ended scope creep and margin breaches.")
    parser.add_argument("--input", required=True, type=Path, help="Path to SOW payload JSON")
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
