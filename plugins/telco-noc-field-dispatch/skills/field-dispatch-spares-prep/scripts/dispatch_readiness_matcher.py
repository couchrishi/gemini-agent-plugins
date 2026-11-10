#!/usr/bin/env python3
"""Validates field technician certifications, depot/van spare parts availability, and dispatch readiness."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "enforce_safety_cert_expiry": True,
    "require_all_spares_reserved": True,
    "min_sla_buffer_hours": 1.0,
}


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

    dispatch_date_str = str(data.get("dispatch_date") or "2026-10-15")
    dispatch_dt = date.fromisoformat(dispatch_date_str[:10])
    techs = data.get("technicians") or []
    depot_stock = {str(k): int(v) for k, v in (data.get("depot_spares_qty") or {}).items()}
    work_orders = data.get("work_orders") or []
    enforce_certs = bool(cfg.get("enforce_safety_cert_expiry", True))

    evaluated: list[dict[str, Any]] = []
    for wo in work_orders:
        wo_id = str(wo.get("work_order_id") or "WO-1")
        site = str(wo.get("site_id") or "SITE-1")
        req_skills = set(wo.get("required_skills") or [])
        req_certs = list(wo.get("required_safety_certs") or [])
        req_spares = wo.get("required_spares") or {}

        missing_spares: list[str] = []
        for sku, qty in req_spares.items():
            if depot_stock.get(str(sku), 0) < int(qty):
                missing_spares.append(f"{sku} (need {qty}, stock {depot_stock.get(str(sku), 0)})")

        eligible_techs: list[dict[str, Any]] = []
        cert_failures: list[str] = []

        for tech in techs:
            tid = str(tech.get("tech_id") or "TECH-1")
            tskills = set(tech.get("skills") or [])
            if not req_skills.issubset(tskills):
                continue
            certs = tech.get("certifications") or {}
            expired = []
            for rc in req_certs:
                exp = certs.get(rc)
                if not exp:
                    expired.append(f"{rc} missing")
                elif enforce_certs and date.fromisoformat(str(exp)[:10]) < dispatch_dt:
                    expired.append(f"{rc} expired {exp}")
            if expired:
                cert_failures.append(f"{tid}: {', '.join(expired)}")
                continue
            eligible_techs.append(
                {
                    "tech_id": tid,
                    "name": str(tech.get("name") or tid),
                    "travel_hours": float(tech.get("estimated_travel_hours") or 1.0),
                }
            )

        eligible_techs.sort(key=lambda t: t["travel_hours"])
        chosen = eligible_techs[0] if eligible_techs else None

        blockers: list[str] = []
        if not chosen:
            if cert_failures:
                blockers.append(f"CERT_BLOCKED ({'; '.join(cert_failures)})")
            else:
                blockers.append("NO_SKILLED_TECHNICIAN_AVAILABLE")
        if missing_spares:
            blockers.append(f"MISSING_SPARES ({', '.join(missing_spares)})")

        status = "BLOCKED" if blockers else "READY_FOR_DISPATCH"
        evaluated.append(
            {
                "work_order_id": wo_id,
                "site_id": site,
                "assigned_technician": chosen,
                "spares_ready": len(missing_spares) == 0,
                "missing_spares": missing_spares,
                "blockers": blockers,
                "dispatch_status": status,
                "hitl_truck_roll_approval_required": True,
            }
        )

    return {
        "skill": "field-dispatch-spares-prep",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "dispatch_date": dispatch_date_str,
            "work_orders_checked": len(evaluated),
            "ready_count": sum(1 for e in evaluated if e["dispatch_status"] == "READY_FOR_DISPATCH"),
            "blocked_count": sum(1 for e in evaluated if e["dispatch_status"] == "BLOCKED"),
        },
        "dispatch_plans": evaluated,
        "truncation_warnings": ["WMS depot inventory feed truncated; confirm physical van bin counts before roll."] if data.get("truncated") else [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Field Dispatch Technician Cert & Spares Readiness ({s['dispatch_date']})",
            "",
            f"- **Work Orders:** {s['work_orders_checked']} | **Ready:** {s['ready_count']} | **Blocked:** {s['blocked_count']}",
            "",
            "| Work Order | Site | Assigned Tech | Spares Ready | Status | Blockers |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for d in result["dispatch_plans"]:
        tech = f"{d['assigned_technician']['tech_id']} ({d['assigned_technician']['name']})" if d["assigned_technician"] else "NONE"
        lines.append(
            f"| `{d['work_order_id']}` | {d['site_id']} | {tech} | {'YES' if d['spares_ready'] else 'NO'} | "
            f"`{d['dispatch_status']}` | {'; '.join(d['blockers']) or 'None'} |"
        )
    lines.extend(["", "Truck rolls and depot pick-ticket releases require HITL dispatch coordinator confirmation."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate technician certs, spares kit completeness, and dispatch readiness.")
    parser.add_argument("--input", required=True, type=Path, help="Path to work orders and spares JSON")
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
