#!/usr/bin/env python3
"""Validates support troubleshooting decision trees for orphan nodes, cycles, dead ends, and broken targets."""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "max_resolution_hops": 6,
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
        return {"nodes": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="troubleshooting-tree-author", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"nodes": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"nodes": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)
    max_hops = _to_int(cfg.get("max_resolution_hops"), 6)

    nodes = _as_list(data.get("nodes"))
    root_id = str(data.get("root_node_id") or (nodes[0]["node_id"] if nodes else ""))
    node_map = {str(n["node_id"]): n for n in nodes if "node_id" in n}

    broken_refs: list[str] = []
    dead_ends: list[str] = []
    adj: dict[str, list[str]] = {}

    for nid, node in node_map.items():
        ntype = str(node.get("node_type") or "question").lower().strip()
        branches = _as_list(node.get("branches"))
        targets: list[str] = []
        for br in branches:
            tgt = str(br.get("target_node_id") or "")
            if tgt not in node_map:
                broken_refs.append(f"{nid} -> '{tgt}' (missing target node)")
            else:
                targets.append(tgt)
        adj[nid] = targets
        if ntype in {"question", "diagnostic"} and not branches:
            dead_ends.append(nid)

    # BFS reachability & depth from root
    visited: set[str] = set()
    depths: dict[str, int] = {}
    if root_id in node_map:
        q: deque[tuple[str, int]] = deque([(root_id, 0)])
        visited.add(root_id)
        depths[root_id] = 0
        while q:
            curr, d = q.popleft()
            for nxt in _as_list(adj.get(curr)):
                if nxt not in visited:
                    visited.add(nxt)
                    depths[nxt] = d + 1
                    q.append((nxt, d + 1))

    unreachable = sorted(nid for nid in node_map if nid not in visited)

    # DFS cycle detection
    color: dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=done
    cycles: list[str] = []

    def _dfs(u: str, path: list[str]) -> None:
        color[u] = 1
        for v in _as_list(adj.get(u)):
            state = color.get(v, 0)
            if state == 1:
                idx = path.index(v) if v in path else 0
                cycles.append(" -> ".join(path[idx:] + [v]))
            elif state == 0:
                _dfs(v, path + [v])
        color[u] = 2

    for nid in node_map:
        if color.get(nid, 0) == 0:
            _dfs(nid, [nid])

    terminal_depths = [
        depths[nid]
        for nid, n in node_map.items()
        if nid in depths and str(n.get("node_type", "")).lower() in {"resolution", "escalation"}
    ]
    max_depth = max(terminal_depths) if terminal_depths else (max(depths.values()) if depths else 0)
    excess_depth = max_depth > max_hops

    valid_graph = not (broken_refs or dead_ends or unreachable or cycles or root_id not in node_map)

    return {
        "skill": "troubleshooting-tree-author",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "node_count": len(node_map),
            "root_node_id": root_id,
            "graph_valid": valid_graph,
            "broken_ref_count": len(broken_refs),
            "dead_end_count": len(dead_ends),
            "unreachable_node_count": len(unreachable),
            "cycle_count": len(cycles),
            "max_resolution_depth": max_depth,
            "exceeds_max_hops": excess_depth,
        },
        "broken_references": broken_refs,
        "dead_end_nodes": dead_ends,
        "unreachable_nodes": unreachable,
        "cycles_detected": cycles,
        "truncation_warnings": _collect_truncation_warnings(data, count=None),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Troubleshooting Decision Tree Integrity Audit (Root: `{s['root_node_id']}`)",
            "",
            f"- **Nodes:** {s['node_count']} | **Graph Valid:** `{s['graph_valid']}` | **Max Depth:** {s['max_resolution_depth']} hops",
            f"- **Broken Refs:** {s['broken_ref_count']} | **Dead Ends:** {s['dead_end_count']} | "
            f"**Unreachable:** {s['unreachable_node_count']} | **Cycles:** {s['cycle_count']}",
        ]
    )
    if result["broken_references"]:
        lines.extend(["", "## Broken References"] + [f"- {x}" for x in result["broken_references"]])
    if result["dead_end_nodes"]:
        lines.extend(["", "## Dead-End Non-Terminal Nodes"] + [f"- `{x}`" for x in result["dead_end_nodes"]])
    if result["cycles_detected"]:
        lines.extend(["", "## Cycles Detected"] + [f"- `{c}`" for c in result["cycles_detected"]])
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate support troubleshooting decision trees for graph defects.")
    parser.add_argument("--input", required=True, type=Path, help="Path to decision tree JSON")
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
