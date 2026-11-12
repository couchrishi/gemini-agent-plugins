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
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            return _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="noc-outage-topology-correlator",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"alarms": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="noc-outage-topology-correlator", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"alarms": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"alarms": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="noc-outage-topology-correlator")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "noc-outage-topology-correlator",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )

    nodes = {str(n["node_id"]): n for n in (data.get("nodes") or []) if "node_id" in n}
    edges = data.get("edges") or []
    alarms = data.get("alarms") or []
    p1_subs = _to_int(cfg.get("p1_subscriber_threshold"), 5000)
    p2_subs = _to_int(cfg.get("p2_subscriber_threshold"), 500)

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
        return (tier_rank.get(ntype, 4), -len(_as_list(children.get(nid))), nid)

    def _ancestors_with_dist(nid: str) -> dict[str, int]:
        dist: dict[str, int] = {}
        q = deque([(p, 1) for p in _as_list(parents.get(nid)) if p != nid])
        while q:
            anc, d = q.popleft()
            if anc in dist or anc == nid:
                continue
            dist[anc] = d
            for p in _as_list(parents.get(anc)):
                if p not in dist and p != nid:
                    q.append((p, d + 1))
        return dist

    ancestors_by_node = {nid: _ancestors_with_dist(nid) for nid in alarm_by_node}

    def _dominates(cand: str, target: str) -> bool:
        if cand == target or cand not in _as_dict(ancestors_by_node.get(target)):
            return False
        if target not in _as_dict(ancestors_by_node.get(cand)):
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
                "root_alarms": [a.get("alarm_code") for a in _as_list(alarm_by_node.get(root_nid))],
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
        q = deque(_as_list(children.get(root_nid)))
        while q:
            dn = q.popleft()
            if dn in cone_seen:
                continue
            cone_seen.add(dn)
            for ch in _as_list(children.get(dn)):
                if ch not in cone_seen:
                    q.append(ch)
        subs = 0
        vips = 0
        for cid in cone_seen:
            meta = nodes.get(cid) or {}
            subs += _to_int(meta.get("subscribers"), 0)
            vips += _to_int(meta.get("enterprise_vip_circuits"), 0)

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
        "truncation_warnings": _collect_truncation_warnings(data, count=len(incidents), existing=["SNMP alarm stream truncated; active storms outside window omitted."] if data.get("truncated") else []),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
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
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Correlate telco NOC alarms across parent-child topology.")
    parser.add_argument("--input", required=True, type=Path, help="Path to topology & alarms JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="noc-outage-topology-correlator",
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        out = json.dumps(diag, indent=2, default=str)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0
    result = analyze(args.input, config=args.config, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
