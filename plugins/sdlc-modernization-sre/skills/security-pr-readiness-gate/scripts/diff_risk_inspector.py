#!/usr/bin/env python3
"""Scans unified PR diffs and dependency manifests for secrets, dropped authz, and unsafe migrations."""

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
}

SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("gcp_api_key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("private_key_block", re.compile(r"BEGIN\s+(?:RSA|EC|OPENSSH|PRIVATE)\s+KEY")),
    ("hardcoded_secret_assign", re.compile(r"""(?:password|api_secret|client_secret|bearer_token)\s*[:=]\s*["'][^"']{8,}["']""", re.IGNORECASE)),
]
AUTHZ_DECORATOR_RE = re.compile(r"@(?:require_auth|login_required|PreAuthorize|RolesAllowed|authorized)\b")
DESTRUCTIVE_DDL_RE = re.compile(r"\b(?:DROP\s+TABLE|DROP\s+COLUMN|TRUNCATE\s+TABLE)\b", re.IGNORECASE)
UNINDEXED_CREATE_INDEX_RE = re.compile(r"\bCREATE\s+INDEX\b(?!\s+CONCURRENTLY)", re.IGNORECASE)
BREAKING_ENDPOINT_RE = re.compile(r"@(?:app|router)\.(?:get|post|put|delete)\(\s*[\"']([^\"']+)[\"']")


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
    p = Path(input_arg)
    if p.suffix.lower() in {".diff", ".patch"}:
        return {"diff": p.read_text(encoding="utf-8"), "pr_id": p.stem}
    return json.loads(p.read_text(encoding="utf-8"))


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    _cfg, org_configured, banner = load_config(config)
    diff_text = str(data.get("diff") or "")
    dependencies = data.get("dependencies", [])

    secret_findings: list[dict[str, Any]] = []
    removed_authz: list[dict[str, Any]] = []
    migration_risks: list[dict[str, Any]] = []
    breaking_api_changes: list[dict[str, Any]] = []
    dependency_risks: list[dict[str, Any]] = []

    current_file = "unknown"
    removed_routes: list[str] = []
    added_routes: list[str] = []
    added_authz_lines = 0

    for line_no, raw in enumerate(diff_text.splitlines(), start=1):
        if raw.startswith("+++ b/"):
            current_file = raw[6:].strip()
            continue
        if raw.startswith("--- ") or raw.startswith("+++ "):
            continue

        if raw.startswith("+"):
            added = raw[1:]
            for kind, pat in SECRET_PATTERNS:
                if pat.search(added):
                    secret_findings.append(
                        {"file": current_file, "line": line_no, "kind": kind, "severity": "CRITICAL"}
                    )
            if AUTHZ_DECORATOR_RE.search(added):
                added_authz_lines += 1
            if DESTRUCTIVE_DDL_RE.search(added):
                migration_risks.append(
                    {"file": current_file, "line": line_no, "issue": "Destructive DDL (DROP/TRUNCATE)", "severity": "HIGH"}
                )
            if UNINDEXED_CREATE_INDEX_RE.search(added):
                migration_risks.append(
                    {
                        "file": current_file,
                        "line": line_no,
                        "issue": "Blocking CREATE INDEX without CONCURRENTLY",
                        "severity": "MEDIUM",
                    }
                )
            for m in BREAKING_ENDPOINT_RE.finditer(added):
                added_routes.append(m.group(1))
        elif raw.startswith("-"):
            removed = raw[1:]
            if AUTHZ_DECORATOR_RE.search(removed):
                removed_authz.append(
                    {"file": current_file, "line": line_no, "decorator": removed.strip(), "severity": "CRITICAL"}
                )
            for m in BREAKING_ENDPOINT_RE.finditer(removed):
                removed_routes.append(m.group(1))

    # Filter out authz decorators that were only moved/replaced in same diff if balanced,
    # while still flagging net removals explicitly
    net_removed_routes = [r for r in removed_routes if r not in added_routes]
    for r in net_removed_routes:
        breaking_api_changes.append({"route": r, "issue": "Removed public API route without deprecation"})

    for dep in dependencies:
        name = str(dep.get("name") or "")
        ver = str(dep.get("version") or "").strip()
        src_url = str(dep.get("source_url") or "")
        if ver in {"*", "latest", ""}:
            dependency_risks.append({"package": name, "version": ver or "UNPINNED", "issue": "Unpinned dependency version"})
        if src_url.startswith("http://"):
            dependency_risks.append({"package": name, "version": ver, "issue": "Non-TLS HTTP package source"})

    critical_count = len(secret_findings) + (len(removed_authz) if added_authz_lines < len(removed_authz) else 0)
    gate_passed = critical_count == 0 and not any(m["severity"] == "HIGH" for m in migration_risks)

    return {
        "skill": "security-pr-readiness-gate",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "pr_id": data.get("pr_id", "PR-1"),
            "secret_finding_count": len(secret_findings),
            "removed_authz_count": len(removed_authz),
            "migration_risk_count": len(migration_risks),
            "breaking_api_count": len(breaking_api_changes),
            "dependency_risk_count": len(dependency_risks),
            "pr_gate_passed": gate_passed,
        },
        "secret_findings": secret_findings,
        "removed_authz": removed_authz,
        "migration_risks": migration_risks,
        "breaking_api_changes": breaking_api_changes,
        "dependency_risks": dependency_risks,
        "truncation_warnings": [],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Security & Migration PR Readiness Gate ({s['pr_id']})",
            "",
            f"- **Gate Passed:** `{s['pr_gate_passed']}`",
            f"- **Secrets:** {s['secret_finding_count']} | **Removed Authz:** {s['removed_authz_count']} | **Migration Risks:** {s['migration_risk_count']}",
            f"- **Breaking API Routes:** {s['breaking_api_count']} | **Dependency Risks:** {s['dependency_risk_count']}",
            "",
        ]
    )
    for sf in result["secret_findings"]:
        lines.append(f"- **CRITICAL Secret (`{sf['kind']}`)** at `{sf['file']}:{sf['line']}`")
    for ra in result["removed_authz"]:
        lines.append(f"- **CRITICAL Removed Authz** at `{ra['file']}:{ra['line']}`: `{ra['decorator']}`")
    for mr in result["migration_risks"]:
        lines.append(f"- **{mr['severity']} Migration Risk** at `{mr['file']}:{mr['line']}`: {mr['issue']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect unified PR diff for secrets, authz drops, and migration risks.")
    parser.add_argument("--input", required=True, type=Path, help="Path to PR diff JSON or .diff/.patch file")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file")
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
