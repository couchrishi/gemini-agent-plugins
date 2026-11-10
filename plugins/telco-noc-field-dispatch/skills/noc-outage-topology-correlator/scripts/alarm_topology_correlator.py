#!/usr/bin/env python3
"""Correlates telco network alarm storms across parent-child topology to suppress symptoms and find root nodes."""

from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "p1_subscriber_threshold": 5000,
    "p2_subscriber_threshold": 500,
    "suppress_downstream_severities": ["CRITICAL", "MAJOR", "MINOR", "WARNING"],
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

    nodes = {str(n["node_id"]): n for n in (data.get("nodes") or []) if "node_id" in n}
    edges = data.get("edges") or []
    alarms = data.get("alarms") or []
    p1_subs = int(cfg.get("p1_subscriber_threshold", 5000))
    p2_subs = int(cfg.get("p2_subscriber_threshold", 500))

    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {}
    for e in edges:
        up = str(e.get("upstream_node_id") or "")
        dn = str(e.get("downstream_node_id") or "")
        if up and dn:
            parents.setdefault(dn, []).append(up)
            children.setdefault(up, []).append(dn)

    alarm_by_node: dict[str, list[dict[str, Any]]] = {}
    for al in alarms:
        nid = str(al.get("node_id") or "")
        if nid:
            alarm_by_node.setdefault(nid, []).append(al)

    tier_rank = {
        "CORE_ROUTER": 0,
        "CORE": 0,
        "BACKBONE": 0,
        "METRO_ROUTER": 1,
        "PE_ROUTER": 1,
        "AGGREGATION": 1,
        "OLT": 1,
        "DIST_SWITCH": 2,
        "CELL_SITE_ROUTER": 2,
        "MICROWAVE": 2,
        "5G_GNODEB": 3,
        "4G_ENODEB": 3,
        "ACCESS_NODE": 3,
        "CPE": 3,
    }

    def _node_priority(nid: str) -> tuple[int, int, str]:
        ntype = str((nodes.get(nid) or {}).get("node_type") or "").upper()
        return (tier_rank.get(ntype, 4), -len(children.get(nid, [])), nid)

    def _ancestors_with_dist(nid: str) -> dict[str, int]:
        dist: dict[str, int] = {}
        q = deque([(p, 1) for p in parents.get(nid, []) if p != nid])
        while q:
            anc, d = q.popleft()
            if anc in dist or anc == nid:
                continue
            dist[anc] = d
            for p in parents.get(anc, []):
                if p not in dist and p != nid:
                    q.append((p, d + 1))
        return dist

    ancestors_by_node = {nid: _ancestors_with_dist(nid) for nid in alarm_by_node}

    def _dominates(cand: str, target: str) -> bool:
        if cand == target or cand not in ancestors_by_node.get(target, {}):
            return False
        if target not in ancestors_by_node.get(cand, {}):
            return True
        return _node_priority(cand) < _node_priority(target)

    root_nodes = {
        nid
        for nid in alarm_by_node
        if not any(_dominates(other, nid) for other in alarm_by_node if other != nid)
    }

    root_clusters: dict[str, dict[str, Any]] = {}
    suppressed_count = 0

    for nid, node_alarms in alarm_by_node.items():
        if nid in root_nodes:
            root_nid = nid
            is_symptom = False
        else:
            cand_roots = [r for r in root_nodes if _dominates(r, nid)]
            cand_roots.sort(key=lambda r: (ancestors_by_node[nid][r], _node_priority(r)))
            root_nid = cand_roots[0] if cand_roots else nid
            is_symptom = root_nid != nid
        if is_symptom:
            suppressed_count += len(node_alarms)

        cluster = root_clusters.setdefault(
            root_nid,
            {
                "root_node_id": root_nid,
                "node_type": str((nodes.get(root_nid) or {}).get("node_type") or "UNKNOWN"),
                "root_alarms": [a.get("alarm_code") for a in alarm_by_node.get(root_nid, [])],
                "suppressed_child_nodes": [],
                "impacted_nodes_set": {root_nid},
                "enterprise_vip_circuits": 0,
                "impacted_subscribers": 0,
            },
        )
        cluster["impacted_nodes_set"].add(nid)
        if is_symptom and nid not in cluster["suppressed_child_nodes"]:
            cluster["suppressed_child_nodes"].append(nid)

    # Traverse full downstream cone of each root node (with cycle guard) for subscriber rollup
    incidents: list[dict[str, Any]] = []
    for root_nid, c in root_clusters.items():
        cone_seen = {root_nid}
        q = deque(children.get(root_nid, []))
        while q:
            dn = q.popleft()
            if dn in cone_seen:
                continue
            cone_seen.add(dn)
            for ch in children.get(dn, []):
                if ch not in cone_seen:
                    q.append(ch)
        subs = 0
        vips = 0
        for cid in cone_seen:
            meta = nodes.get(cid) or {}
            subs += int(meta.get("subscribers") or 0)
            vips += int(meta.get("enterprise_vip_circuits") or 0)

        severity = "P1_CRITICAL" if (subs >= p1_subs or vips >= 5) else ("P2_MAJOR" if subs >= p2_subs or vips >= 1 else "P3_MINOR")
        incidents.append(
            {
                "root_node_id": root_nid,
                "node_type": c["node_type"],
                "root_alarm_codes": c["root_alarms"],
                "suppressed_child_nodes": sorted(c["suppressed_child_nodes"]),
                "downstream_cone_size": len(cone_seen),
                "impacted_subscribers": subs,
                "enterprise_vip_circuits": vips,
                "recommended_severity": severity,
            }
        )

    incidents.sort(key=lambda x: (-x["impacted_subscribers"], -x["downstream_cone_size"]))
    return {
        "skill": "noc-outage-topology-correlator",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "raw_alarms_ingested": len(alarms),
            "correlated_root_incidents": len(incidents),
            "symptom_alarms_suppressed": suppressed_count,
            "noise_reduction_pct": round(suppressed_count / len(alarms) * 100.0, 1) if alarms else 0.0,
            "p1_critical_incidents": sum(1 for i in incidents if i["recommended_severity"] == "P1_CRITICAL"),
        },
        "root_incidents": incidents,
        "truncation_warnings": ["SNMP alarm stream truncated; active storms outside window omitted."] if data.get("truncated") else [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# NOC Alarm Storm Topology Correlation & Root Cause Clusters",
            "",
            f"- **Raw Alarms:** {s['raw_alarms_ingested']} -> **Root Incidents:** {s['correlated_root_incidents']} | "
            f"**Suppressed Symptoms:** {s['symptom_alarms_suppressed']} ({s['noise_reduction_pct']:.1f}% reduction) | "
            f"**P1 Critical:** {s['p1_critical_incidents']}",
            "",
            "| Severity | Root Node | Type | Root Alarms | Suppressed Children | Subscribers | VIP Circuits |",
            "| :--- | :--- | :--- | :--- | ---: | ---: | ---: |",
        ]
    )
    for inc in result["root_incidents"]:
        lines.append(
            f"| `{inc['recommended_severity']}` | `{inc['root_node_id']}` | {inc['node_type']} | "
            f"{', '.join(inc['root_alarm_codes']) or 'NONE'} | {len(inc['suppressed_child_nodes'])} | "
            f"{inc['impacted_subscribers']:,} | {inc['enterprise_vip_circuits']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Correlate telco NOC alarms across parent-child topology.")
    parser.add_argument("--input", required=True, type=Path, help="Path to topology & alarms JSON")
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
