#!/usr/bin/env python3
"""Evaluates insurance claims against policy dates, exclusions, deductibles, sublimits, and coinsurance."""

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
    "high_value_claim_threshold": 100000.0,
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
        return {"claims": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="insurance-claims-triage-pack", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"claims": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"claims": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return _safe_date(s)


def _evaluate_claim(c: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    cid = str(c.get("claim_id") or "CLM-1")
    pol = c.get("policy") or {}
    peril = str(c.get("peril") or "general").lower().strip()
    claimed = _to_float(c.get("claimed_amount_usd"), 0.0)
    loss_dt = _parse_date(c.get("loss_date"))
    eff_dt = _parse_date(pol.get("effective_date"))
    exp_dt = _parse_date(pol.get("expiration_date"))
    doc_ok = _to_bool(c.get("documentation_complete"), True)
    excluded = {str(p).lower().strip() for p in _as_list(pol.get("excluded_perils"))}

    high_val_thresh = _to_float(cfg.get("high_value_claim_threshold"), 100000.0)

    in_period = bool(loss_dt and eff_dt and exp_dt and eff_dt <= loss_dt <= exp_dt)
    reasons: list[str] = []

    if not in_period:
        reasons.append(f"Loss date {loss_dt} outside policy period [{eff_dt}, {exp_dt}].")
        return {
            "claim_id": cid,
            "peril": peril,
            "claimed_amount_usd": round(claimed, 2),
            "net_payable_usd": 0.0,
            "reserve_escalation": False,
            "triage_decision": "COVERAGE_DENIED_OUT_OF_PERIOD",
            "notes": reasons,
        }

    if peril in excluded:
        reasons.append(f"Peril '{peril}' is explicitly excluded under policy {pol.get('policy_id')}.")
        return {
            "claim_id": cid,
            "peril": peril,
            "claimed_amount_usd": round(claimed, 2),
            "net_payable_usd": 0.0,
            "reserve_escalation": False,
            "triage_decision": "COVERAGE_DENIED_EXCLUSION",
            "notes": reasons,
        }

    deductible = _to_float(pol.get("deductible_usd"), 0.0)
    coinsurance_insurer_pct = _to_float(pol.get("insurer_coinsurance_pct"), 100.0) / 100.0
    sublimits = {str(k).lower().strip(): val for k, v in _as_dict(pol.get("sublimits")).items() for val in [_to_opt_float(v)] if val is not None}
    agg_limit = (_to_float(pol.get("aggregate_limit_usd")) or claimed)

    after_ded = max(0.0, claimed - deductible)
    insurer_portion = after_ded * coinsurance_insurer_pct
    capped = min(insurer_portion, sublimits.get(peril, agg_limit), agg_limit)
    reserve_esc = capped >= high_val_thresh

    if not doc_ok:
        decision = "PENDING_EVIDENCE_HOLD"
        reasons.append("Mandatory supporting claim evidence incomplete.")
    elif reserve_esc:
        decision = "RESERVE_ESCALATION_SENIOR_ADJUSTER"
        reasons.append(f"Net payable ${capped:,.2f} >= ${high_val_thresh:,.0f} authority cap.")
    else:
        decision = "ELIGIBLE_FOR_ADJUSTER_SIGN_OFF"

    return {
        "claim_id": cid,
        "peril": peril,
        "claimed_amount_usd": round(claimed, 2),
        "deductible_applied_usd": round(deductible, 2),
        "net_payable_usd": round(capped, 2),
        "reserve_escalation": reserve_esc,
        "triage_decision": decision,
        "notes": reasons,
    }


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    claims = data.get("claims") or ([data] if "claim_id" in data else [])
    triaged = [_evaluate_claim(c, cfg) for c in claims]

    return {
        "skill": "insurance-claims-triage-pack",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "claims_triaged": len(triaged),
            "denied_count": sum(1 for t in triaged if t["triage_decision"].startswith("COVERAGE_DENIED")),
            "reserve_escalation_count": sum(1 for t in triaged if t["reserve_escalation"]),
            "total_claimed_usd": round(sum(t["claimed_amount_usd"] for t in triaged), 2),
            "total_net_payable_usd": round(sum(t["net_payable_usd"] for t in triaged), 2),
        },
        "claim_evaluations": triaged,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Insurance Claims Coverage, Sublimit & Reserve Triage",
            "",
            f"- **Claims Triaged:** {s['claims_triaged']} | **Denied:** {s['denied_count']} | "
            f"**Reserve Escalations:** {s['reserve_escalation_count']}",
            f"- **Total Claimed:** ${s['total_claimed_usd']:,.2f} | **Calculated Net Payable:** ${s['total_net_payable_usd']:,.2f}",
            "",
            "| Claim ID | Peril | Claimed | Net Payable | Decision | Notes |",
            "| :--- | :--- | ---: | ---: | :--- | :--- |",
        ]
    )
    for t in result["claim_evaluations"]:
        lines.append(
            f"| `{t['claim_id']}` | {t['peril']} | ${t['claimed_amount_usd']:,.2f} | "
            f"**${t['net_payable_usd']:,.2f}** | `{t['triage_decision']}` | {'; '.join(t['notes']) or 'Covered'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate insurance claims against policy periods, deductibles, and limits.")
    parser.add_argument("--input", required=True, type=Path, help="Path to claims JSON")
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
