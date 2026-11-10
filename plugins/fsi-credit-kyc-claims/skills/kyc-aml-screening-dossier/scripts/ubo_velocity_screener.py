#!/usr/bin/env python3
"""Resolves multi-hop KYB/UBO beneficial ownership percentages and screens AML transaction velocity spikes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "ubo_standard_pct": 25.0,
    "ubo_edd_pct": 10.0,
    "velocity_spike_multiplier": 3.0,
    "structuring_count_threshold": 5,
    "high_risk_jurisdictions": ["VG", "KY", "PA", "CY"],
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
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    _loaded = json.loads(Path(input_arg).read_text(encoding="utf-8"))
    return _loaded if isinstance(_loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload))
    cfg, org_configured, banner = load_config(config)

    target_id = str(data.get("target_entity_id") or "TARGET-CO")
    edges = _as_list(data.get("ownership_edges"))
    high_risk_jur = {str(j).upper() for j in cfg.get("high_risk_jurisdictions", DEFAULT_CONFIG["high_risk_jurisdictions"])}

    # Reverse graph: target -> list of (owner_id, share_fraction, owner_meta)
    parents_of: dict[str, list[tuple[str, float, dict[str, Any]]]] = {}
    owner_meta: dict[str, dict[str, Any]] = {}
    edd_triggers: list[str] = []

    for e in edges:
        oid = str(e.get("owner_id") or "").strip()
        if not oid:
            continue
        tid = str(e.get("target_entity_id") or e.get("target_id") or "")
        pct = _to_float(e.get("direct_pct"), 0.0) / 100.0
        jur = str(e.get("jurisdiction") or "US").upper()
        is_pep = bool(e.get("is_pep", False))
        meta = {
            "owner_id": oid,
            "owner_name": str(e.get("owner_name") or oid),
            "owner_type": str(e.get("owner_type") or "ENTITY").upper(),
            "jurisdiction": jur,
            "is_pep": is_pep,
        }
        owner_meta[oid] = meta
        parents_of.setdefault(tid, []).append((oid, pct, meta))
        if jur in high_risk_jur:
            edd_triggers.append(f"High-risk jurisdiction {jur} on {meta['owner_name']}")
        if is_pep:
            edd_triggers.append(f"PEP match on {meta['owner_name']}")

    effective_shares: dict[str, float] = {}
    cycles_detected: list[list[str]] = []

    def _walk_up(curr: str, mult: float, visited: list[str]) -> None:
        for oid, share, meta in _as_list(parents_of.get(curr)):
            if oid in visited:
                cycles_detected.append(visited + [oid])
                continue
            new_mult = mult * share
            if meta["owner_type"] == "INDIVIDUAL":
                effective_shares[oid] = effective_shares.get(oid, 0.0) + new_mult
            else:
                _walk_up(oid, new_mult, visited + [oid])

    _walk_up(target_id, 1.0, [target_id])

    threshold_pct = _to_float(cfg.get("ubo_edd_pct"), 10.0) if edd_triggers else _to_float(cfg.get("ubo_standard_pct"), 25.0)
    ubo_candidates: list[dict[str, Any]] = []
    for oid, frac in sorted(effective_shares.items(), key=lambda kv: -kv[1]):
        pct = round(frac * 100.0, 2)
        meta = owner_meta[oid]
        if pct >= threshold_pct or meta["is_pep"]:
            ubo_candidates.append(
                {
                    "owner_id": oid,
                    "owner_name": meta["owner_name"],
                    "jurisdiction": meta["jurisdiction"],
                    "is_pep": meta["is_pep"],
                    "effective_ownership_pct": pct,
                    "meets_ubo_threshold": pct >= threshold_pct,
                }
            )

    # AML transaction velocity & structuring detection
    vel_30d = _to_float(data.get("rolling_30d_volume_usd"), 0.0)
    base_90d_monthly = _to_float(data.get("trailing_90d_monthly_avg_usd"), 0.0)
    vel_mult = (vel_30d / base_90d_monthly) if base_90d_monthly > 0 else 0.0
    vel_spike = vel_mult >= _to_float(cfg.get("velocity_spike_multiplier"), 3.0)

    near_threshold_deposits = [
        tx
        for tx in _as_list(data.get("transactions"))
        if 8000.0 <= _to_float(tx.get("amount_usd"), 0.0) <= 9999.99
        and str(tx.get("tx_type", "CASH")).upper() in {"CASH", "WIRE", "DEPOSIT"}
    ]
    structuring_alert = len(near_threshold_deposits) >= _to_int(cfg.get("structuring_count_threshold"), 5)

    if edd_triggers or vel_spike or structuring_alert or cycles_detected:
        risk_tier = "EDD_MLRO_ESCALATION_REQUIRED"
    else:
        risk_tier = "STANDARD_KYC_APPROVED_FOR_HITL"

    return {
        "skill": "kyc-aml-screening-dossier",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "target_entity_id": target_id,
        "summary": {
            "ubo_threshold_applied_pct": threshold_pct,
            "edd_triggered": bool(edd_triggers),
            "identified_ubo_count": len(ubo_candidates),
            "velocity_multiplier": round(vel_mult, 2),
            "velocity_spike_alert": vel_spike,
            "near_threshold_structuring_count": len(near_threshold_deposits),
            "structuring_alert": structuring_alert,
            "ownership_cycle_count": len(cycles_detected),
            "kyc_risk_tier": risk_tier,
        },
        "beneficial_owners": ubo_candidates,
        "edd_signals": sorted(set(edd_triggers)),
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# KYB Beneficial Ownership & AML Screening Dossier — `{result['target_entity_id']}`",
            "",
            f"- **KYC Tier:** `{s['kyc_risk_tier']}` | **Active UBO Threshold:** {s['ubo_threshold_applied_pct']:.1f}% | "
            f"**Identified UBOs:** {s['identified_ubo_count']}",
            f"- **30d Velocity Multiplier:** {s['velocity_multiplier']:.2f}x (Alert: `{s['velocity_spike_alert']}`) | "
            f"**Structuring ($8k-$9.99k) Count:** {s['near_threshold_structuring_count']} (Alert: `{s['structuring_alert']}`)",
            "",
            "| UBO ID | Beneficial Owner | Jurisdiction | PEP | Effective Ownership % | Threshold Hit |",
            "| :--- | :--- | :--- | :--- | ---: | :--- |",
        ]
    )
    for u in result["beneficial_owners"]:
        lines.append(
            f"| `{u['owner_id']}` | {u['owner_name']} | {u['jurisdiction']} | {'YES' if u['is_pep'] else 'No'} | "
            f"**{u['effective_ownership_pct']:.2f}%** | {'YES' if u['meets_ubo_threshold'] else 'No'} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute multi-hop UBO ownership and screen AML velocity spikes.")
    parser.add_argument("--input", required=True, type=Path, help="Path to ownership and transactions JSON")
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
