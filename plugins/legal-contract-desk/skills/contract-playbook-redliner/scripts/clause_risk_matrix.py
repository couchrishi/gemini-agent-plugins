#!/usr/bin/env python3
"""Scores commercial contract clauses on a 1/3/9 risk scale and flags IPI and walk-away blockers."""

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
    "lol_cap_months_min": 12,
    "lol_cap_months_max": 24,
    "super_cap_multiplier_max": 3.0,
    "max_renewal_notice_days": 60,
    "max_price_escalator_pct": 5.0,
    "max_breach_notify_hours": 72,
    "forbid_customer_data_training": True,
    "approved_jurisdictions": ["Delaware", "New York", "England and Wales", "Singapore"],
    "max_control_evidence_days": 365,
}

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"override\s+(the\s+)?playbook", re.IGNORECASE),
    re.compile(r"assign\s+score\s+1\s+to\s+all", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[\s*system\s+instruction", re.IGNORECASE),
]

FALLBACK_REDLINES = {
    "limitation_of_liability": (
        "Replace unilateral/uncapped terms with a mutual general liability cap equal to the greater of "
        "12 months trailing fees or $1,000,000, with an explicit 2x-3x super-cap solely for data breach, "
        "IP infringement indemnity, and confidentiality breaches."
    ),
    "auto_renewal": (
        "Limit notice period to no more than 60 days prior to term expiry (prefer 30 days or explicit opt-in), "
        "and cap annual renewal uplifts at the lesser of CPI or 5.0%."
    ),
    "data_rights_ai_training": (
        "Add explicit prohibition: Vendor shall not use Customer Data, prompts, embeddings, or outputs to train "
        "or fine-tune shared or foundation AI models."
    ),
    "dpa_breach_notification": (
        "Mandate confirmed security incident notification without undue delay and in no event later than 72 hours "
        "(target 48 hours), with deterministic forensic cooperation obligations."
    ),
    "governing_law": (
        "Amend governing law and exclusive venue to an approved neutral jurisdiction (Delaware, New York, "
        "England and Wales, or Singapore)."
    ),
    "indemnification": (
        "Require mutual third-party IP infringement and bodily injury/gross negligence indemnity uncapped only "
        "to the extent permitted by statutory law or subject to the agreed super-cap."
    ),
}


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
        return {"clauses": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="contract-playbook-redliner", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"clauses": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"clauses": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _detect_prompt_injection(text: str) -> list[str]:
    hits: list[str] = []
    for pat in INJECTION_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def _score_clause(clause: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    cid = str(clause.get("clause_id") or "CL-1")
    family = str(clause.get("clause_family") or "general").lower().strip()
    text = str(clause.get("clause_text") or "")
    metrics = clause.get("metrics") if isinstance(clause.get("metrics"), dict) else {}

    injection_hits = _detect_prompt_injection(text)
    quarantined = len(injection_hits) > 0

    lol_min = _to_int(cfg.get("lol_cap_months_min"), 12)
    lol_max = _to_int(cfg.get("lol_cap_months_max"), 24)
    super_cap_max = _to_float(cfg.get("super_cap_multiplier_max"), 3.0)
    max_notice = _to_int(cfg.get("max_renewal_notice_days"), 60)
    max_cpi = _to_float(cfg.get("max_price_escalator_pct"), 5.0)
    max_breach_hrs = _to_int(cfg.get("max_breach_notify_hours"), 72)
    forbid_ai = _to_bool(cfg.get("forbid_customer_data_training"), True)
    approved_jur = {str(j).lower().strip() for j in _as_list(cfg.get("approved_jurisdictions"))}

    score = 1
    rationale: list[str] = []

    if family == "limitation_of_liability":
        uncapped = _to_bool(metrics.get("uncapped_liability"), False) or "unlimited liability" in text.lower()
        asymmetric = _to_bool(metrics.get("unilateral_cap"), False)
        cap_months = _to_opt_float(metrics.get("lol_cap_months"))
        super_mult = _to_opt_float(metrics.get("super_cap_multiplier"))
        if uncapped:
            score = 9
            rationale.append("General liability is uncapped or exposes consequential damages.")
        elif cap_months is not None and float(cap_months) < 6:
            score = 9
            rationale.append(f"Vendor liability cap ({cap_months} months fees) is below minimum 6-month floor.")
        elif asymmetric:
            score = 9
            rationale.append("Asymmetric unilateral liability cap favors counterparty only.")
        else:
            if cap_months is None:
                score = max(score, 3)
                rationale.append("Liability cap months missing or ambiguous; verify trailing 12-month fee formula.")
            elif float(cap_months) < lol_min or float(cap_months) > lol_max:
                score = max(score, 3)
                rationale.append(
                    f"Liability cap ({cap_months} months) outside preferred {lol_min}-{lol_max} month band."
                )
            if super_mult is not None and float(super_mult) > super_cap_max:
                score = max(score, 3)
                rationale.append(
                    f"Super-cap multiplier ({super_mult}x) exceeds baseline ceiling ({super_cap_max}x)."
                )
        if not rationale:
            rationale.append(f"Mutual cap aligns within {lol_min}-{lol_max} month policy band.")

    elif family == "auto_renewal":
        evergreen = _to_bool(metrics.get("silent_evergreen"), False)
        notice_days = _to_opt_int(metrics.get("notice_days"))
        cpi_pct = _to_opt_float(metrics.get("price_escalator_pct"))
        uncapped_cpi = _to_bool(metrics.get("uncapped_price_escalator"), False)
        if uncapped_cpi or (notice_days is not None and int(notice_days) > 90):
            score = 9
            rationale.append(
                f"Blocker renewal term (notice={notice_days}d, uncapped_cpi={uncapped_cpi}) locks pricing unfairly."
            )
        elif notice_days is None and evergreen:
            score = 9
            rationale.append("Silent evergreen renewal omits mandatory notice window.")
        else:
            if notice_days is not None and int(notice_days) > max_notice:
                score = max(score, 3)
                rationale.append(f"Opt-out notice window ({notice_days} days) exceeds max {max_notice} days.")
            elif notice_days is not None and int(notice_days) > 30:
                score = max(score, 3)
                rationale.append(f"Notice window ({notice_days} days) exceeds preferred 30-day standard.")
            if cpi_pct is not None and float(cpi_pct) > max_cpi:
                score = max(score, 3)
                rationale.append(f"Annual renewal uplift ({cpi_pct}%) exceeds max escalator cap ({max_cpi}%).")
            if evergreen and score == 1:
                score = 3
                rationale.append("Evergreen auto-renewal present; propose explicit written opt-in renewal.")
        if not rationale:
            rationale.append("Renewal notice window and escalator cap comply with baseline limits.")

    elif family in {"data_rights_ai_training", "ip_and_data", "data_privacy"}:
        trains_on_data = _to_bool(metrics.get("vendor_ai_training_allowed"), False) or any(
            kw in text.lower() for kw in ("train its models", "train foundation models", "train general foundation models", "improve vendor ai")
        )
        ip_assign = _to_bool(metrics.get("assigns_customer_preexisting_ip"), False)
        hours = _to_opt_int(metrics.get("breach_notify_hours"))
        if ip_assign or (forbid_ai and trains_on_data):
            score = 9
            rationale.append("Counterparty claims customer pre-existing IP or unrestricted AI training rights.")
        if hours is not None and int(hours) > max_breach_hrs:
            score = 9
            rationale.append(f"Breach notification window ({hours}h) exceeds maximum {max_breach_hrs}h policy limit.")
        if score == 1:
            if metrics.get("shared_background_ip_license"):
                score = 3
                rationale.append("Broad derivative/background IP license requires narrow internal-use scoping.")
            else:
                rationale.append("Customer retains exclusive IP and data ownership without AI training rights.")

    elif family == "dpa_breach_notification":
        vague = _to_bool(metrics.get("vague_timing"), False) or "commercially reasonable" in text.lower()
        hours = _to_opt_int(metrics.get("breach_notify_hours"))
        if vague or (hours is not None and int(hours) > max_breach_hrs):
            score = 9
            rationale.append(
                f"Breach notification window ({hours or 'vague'}h) fails statutory <= {max_breach_hrs}h threshold."
            )
        elif hours is None:
            score = 9
            rationale.append("Breach notification SLA omits explicit hour limit (cannot assume compliant).")
        elif hours > 48:
            score = 3
            rationale.append(f"Notification at {hours}h meets GDPR ceiling (72h) but misses 48h preferred target.")
        else:
            rationale.append(f"Breach notification within {hours}h satisfies preferred <= 48h SLA.")

    elif family == "governing_law":
        jur = str(metrics.get("jurisdiction") or "").strip()
        jury_waiver = _to_bool(metrics.get("unilateral_venue_or_appeal_waiver"), False)
        if jury_waiver:
            score = 9
            rationale.append("Unilateral venue or statutory appeal waiver violates playbook floor.")
        elif not jur or jur.lower() not in approved_jur:
            score = 3
            rationale.append(
                f"Jurisdiction '{jur or 'Unspecified'}' is outside approved list ({', '.join(sorted(approved_jur))})."
            )
        else:
            rationale.append(f"Approved governing jurisdiction ({jur}).")

    else:
        severity_hint = _to_opt_int(clause.get("playbook_risk_hint"))
        if severity_hint in {1, 3, 9}:
            score = int(severity_hint)
            rationale.append(f"Evaluated against custom clause hint ({family}: score {score}).")
        elif any(w in text.lower() for w in ("sole discretion", "irrevocable", "perpetual worldwide license")):
            score = 3
            rationale.append("Broad unilateral counterparty right warrants negotiable fallback tightening.")
        else:
            rationale.append("Standard commercial wording within tolerance.")

    fallback = "" if score == 1 else FALLBACK_REDLINES.get(
        family, "Narrow clause scope to mutual obligations capped at agreed LoL ceiling and standard notice periods."
    )
    band = {1: "Low / Acceptable", 3: "Moderate / Negotiable", 9: "Critical / Walk-Away Blocker"}[score]

    return {
        "clause_id": cid,
        "clause_family": family,
        "risk_score": score,
        "risk_band": band,
        "injection_quarantined": quarantined,
        "injection_signals": injection_hits,
        "rationale": rationale,
        "suggested_fallback_language": fallback,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)

    contract_id = str(data.get("contract_id") or "CONTRACT-1")
    counterparty = str(data.get("counterparty") or "Unknown Counterparty")
    contract_type = str(data.get("contract_type") or "MSA")
    clauses = _as_list(data.get("clauses"))

    evaluated = [_score_clause(c, cfg) for c in clauses]
    score9 = [e for e in evaluated if e["risk_score"] == 9]
    score3 = [e for e in evaluated if e["risk_score"] == 3]
    quarantined = [e for e in evaluated if e["injection_quarantined"]]

    if score9 or quarantined:
        readiness = "BLOCKED_BY_SCORE_9"
    elif score3:
        readiness = "NEGOTIABLE_REDLINES_REQUIRED"
    else:
        readiness = "READY_FOR_COUNSEL_SIGN_OFF"

    return {
        "skill": "contract-playbook-redliner",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "contract_id": contract_id,
        "counterparty": counterparty,
        "contract_type": contract_type,
        "summary": {
            "clauses_reviewed": len(evaluated),
            "blocker_score9_count": len(score9),
            "negotiable_score3_count": len(score3),
            "acceptable_score1_count": sum(1 for e in evaluated if e["risk_score"] == 1),
            "total_risk_points": sum(e["risk_score"] for e in evaluated),
            "injection_quarantined_count": len(quarantined),
            "signature_readiness": readiness,
        },
        "clause_evaluations": evaluated,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(evaluated)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Contract Playbook Redline Matrix — `{result['contract_id']}` ({result['counterparty']})",
            "",
            f"- **Contract Type:** {result['contract_type']} | **Signature Readiness:** `{s['signature_readiness']}`",
            f"- **Clauses Reviewed:** {s['clauses_reviewed']} | **Score 9 Blockers:** {s['blocker_score9_count']} | "
            f"**Score 3 Redlines:** {s['negotiable_score3_count']} | **Injection Quarantined:** {s['injection_quarantined_count']}",
            "",
            "| Clause ID | Family | Score | Band | IPI Flag | Finding |",
            "| :--- | :--- | ---: | :--- | :--- | :--- |",
        ]
    )
    for c in result["clause_evaluations"]:
        finding = "; ".join(c["rationale"])
        ipi = "QUARANTINED" if c["injection_quarantined"] else "Clean"
        lines.append(
            f"| `{c['clause_id']}` | `{c['clause_family']}` | **{c['risk_score']}** | {c['risk_band']} | {ipi} | {finding} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score contract clauses on a 1/3/9 playbook risk matrix.")
    parser.add_argument("--input", required=True, type=Path, help="Path to contract clauses JSON")
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
