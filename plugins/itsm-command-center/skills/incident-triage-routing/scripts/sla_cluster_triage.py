#!/usr/bin/env python3
"""Computes business-elapsed SLA risk, clusters correlated CI/error spikes, and ranks runbooks."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "p1_resolution_minutes": 240,
    "p2_resolution_minutes": 480,
    "p3_resolution_minutes": 1440,
    "p4_resolution_minutes": 2400,
    "sla_at_risk_pct": 75.0,
    "spike_cluster_min": 3,
}

STATE_CODE_MAP = {
    "1": "New",
    "2": "In Progress",
    "3": "On Hold",
    "6": "Resolved",
    "7": "Closed",
    "8": "Canceled",
}
TOKEN_RE = re.compile(r"[a-z0-9_]+")


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


def load_payload(input_arg: str | Path | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"incidents": input_arg}
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"incidents": list(csv.DictReader(fh))}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"incidents": data}
    return data


def _unwrap_sn_field(val: Any) -> tuple[str, str]:
    """Handle ServiceNow sysparm_display_value=all dicts or plain values."""
    if isinstance(val, dict):
        raw = str(val.get("value") or "")
        disp = str(val.get("display_value") or raw)
        return raw, disp
    s = "" if val is None else str(val)
    return s, s


def _parse_dt(val: Any) -> dt.datetime | None:
    if not val:
        return None
    norm = str(val).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(norm)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall((text or "").lower()) if len(t) > 2}


def analyze(
    payload: str | Path | dict[str, Any] | list[dict[str, Any]],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)
    incidents = data.get("incidents") or data.get("records") or []
    runbooks = data.get("runbooks", [])
    metadata = data.get("metadata", {})
    as_of = _parse_dt(data.get("as_of_time")) or dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)

    total_available = int(metadata.get("total_available", len(incidents)))
    truncated = bool(metadata.get("truncated", total_available > len(incidents)))
    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"TRUNCATION_WARNING: Evaluated {len(incidents)} of {total_available} ITSM incidents."
        )

    sla_targets = {
        "P1": int(cfg.get("p1_resolution_minutes", 240)),
        "P2": int(cfg.get("p2_resolution_minutes", 480)),
        "P3": int(cfg.get("p3_resolution_minutes", 1440)),
        "P4": int(cfg.get("p4_resolution_minutes", 2400)),
    }
    at_risk_pct = float(cfg.get("sla_at_risk_pct", 75.0))
    cluster_min = int(cfg.get("spike_cluster_min", 3))

    active_rows: list[dict[str, Any]] = []
    clusters: dict[tuple[str, str], list[str]] = defaultdict(list)
    breached_count = 0
    at_risk_count = 0
    canceled_excluded = 0
    closed_excluded = 0

    for idx, inc in enumerate(incidents):
        iid = str(inc.get("incident_id") or inc.get("number") or f"INC-{idx + 1}")
        raw_state, disp_state = _unwrap_sn_field(inc.get("state", "1"))
        state_label = STATE_CODE_MAP.get(raw_state, disp_state)
        if raw_state == "8" or state_label.lower() == "canceled":
            canceled_excluded += 1
            continue
        if raw_state in {"6", "7"} or state_label.lower() in {"resolved", "closed"}:
            closed_excluded += 1
            continue

        _, ci_name = _unwrap_sn_field(inc.get("cmdb_ci") or inc.get("service") or "unknown_ci")
        _, assign_group = _unwrap_sn_field(inc.get("assignment_group") or "ServiceDesk")
        prio_raw, prio_disp = _unwrap_sn_field(inc.get("priority", "P3"))
        prio_norm = prio_disp.upper()[:2] if prio_disp.upper().startswith("P") else f"P{prio_raw}" if prio_raw in {"1", "2", "3", "4"} else "P3"
        target_min = sla_targets.get(prio_norm, sla_targets["P3"])

        # Business elapsed time avoids wall-clock false positives during On Hold / 8x5 off-hours
        if inc.get("business_elapsed_minutes") is not None:
            biz_elapsed = float(inc["business_elapsed_minutes"])
            clock_basis = "business_elapsed_minutes"
        else:
            opened = _parse_dt(inc.get("opened_at") or inc.get("sys_created_on")) or as_of
            wall_min = max(0.0, (as_of - opened).total_seconds() / 60.0)
            paused_min = float(inc.get("sla_paused_minutes", 0.0))
            biz_elapsed = max(0.0, wall_min - paused_min)
            clock_basis = "wall_minus_paused"

        burn_pct = round((biz_elapsed / max(target_min, 1)) * 100.0, 2)
        if burn_pct >= 100.0:
            sla_status = "BREACHED"
            breached_count += 1
        elif burn_pct >= at_risk_pct:
            sla_status = "AT_RISK"
            at_risk_count += 1
        else:
            sla_status = "ON_TRACK"

        err_sig = str(inc.get("error_signature") or inc.get("category") or "general").strip().lower()
        clusters[(ci_name, err_sig)].append(iid)

        desc = str(inc.get("short_description") or inc.get("summary") or "")
        inc_toks = _tokens(f"{ci_name} {err_sig} {desc}")
        best_rb = None
        best_score = 0.0
        for rb in runbooks:
            rb_toks = _tokens(f"{rb.get('title', '')} {rb.get('service_ci', '')} {' '.join(rb.get('tags', []))}")
            if not rb_toks or not inc_toks:
                continue
            sim = len(inc_toks & rb_toks) / len(inc_toks | rb_toks)
            if sim > best_score:
                best_score = sim
                best_rb = {"runbook_id": rb.get("runbook_id"), "title": rb.get("title"), "score": round(sim, 3)}

        active_rows.append(
            {
                "incident_id": iid,
                "priority": prio_norm,
                "state": state_label,
                "cmdb_ci": ci_name,
                "assignment_group": assign_group,
                "error_signature": err_sig,
                "business_elapsed_minutes": round(biz_elapsed, 1),
                "sla_target_minutes": target_min,
                "sla_burn_pct": burn_pct,
                "sla_status": sla_status,
                "clock_basis": clock_basis,
                "recommended_runbook": best_rb,
            }
        )

    active_rows.sort(key=lambda r: (r["sla_burn_pct"], r["priority"] == "P1"), reverse=True)
    spike_clusters = [
        {"cmdb_ci": ci, "error_signature": sig, "count": len(ids), "incident_ids": ids}
        for (ci, sig), ids in sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True)
        if len(ids) >= cluster_min
    ]

    return {
        "skill": "incident-triage-routing",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "total_records_received": len(incidents),
            "active_incident_count": len(active_rows),
            "closed_excluded_count": closed_excluded,
            "canceled_excluded_count": canceled_excluded,
            "sla_breached_count": breached_count,
            "sla_at_risk_count": at_risk_count,
            "spike_cluster_count": len(spike_clusters),
        },
        "active_incidents": active_rows,
        "spike_clusters": spike_clusters,
        "truncation_warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# ITSM Incident Triage & SLA Burn Report",
            "",
            f"- **Active Backlog:** {s['active_incident_count']} (Breached: {s['sla_breached_count']}, At Risk: {s['sla_at_risk_count']})",
            f"- **Spike Clusters Detected:** {s['spike_cluster_count']} | **Canceled Excluded:** {s['canceled_excluded_count']}",
            "",
            "| Incident | Priority | State | CI | SLA Burn % | Status | Top Runbook |",
            "| :--- | :---: | :--- | :--- | ---: | :---: | :--- |",
        ]
    )
    for r in result["active_incidents"]:
        rb = r["recommended_runbook"]["title"] if r.get("recommended_runbook") else "None matched"
        lines.append(
            f"| `{r['incident_id']}` | {r['priority']} | {r['state']} | {r['cmdb_ci']} | "
            f"{r['sla_burn_pct']:.1f}% | `{r['sla_status']}` | {rb} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze ITSM incident SLA risk and spike clusters.")
    parser.add_argument("--input", required=True, type=Path, help="Path to incidents JSON or CSV")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output path")
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
