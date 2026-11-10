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
    max_hops = int(cfg.get("max_resolution_hops", 6))

    nodes = data.get("nodes", [])
    root_id = str(data.get("root_node_id") or (nodes[0]["node_id"] if nodes else ""))
    node_map = {str(n["node_id"]): n for n in nodes if "node_id" in n}

    broken_refs: list[str] = []
    dead_ends: list[str] = []
    adj: dict[str, list[str]] = {}

    for nid, node in node_map.items():
        ntype = str(node.get("node_type") or "question").lower().strip()
        branches = node.get("branches", [])
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
            for nxt in adj.get(curr, []):
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
        for v in adj.get(u, []):
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
        "truncation_warnings": [],
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
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate support troubleshooting decision trees for graph defects.")
    parser.add_argument("--input", required=True, type=Path, help="Path to decision tree JSON")
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
