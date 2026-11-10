#!/usr/bin/env python3
"""Packages Gemini Agent plugins into 1-click department bundles and granular 1-hop skills.

Usage:
  python3 tools/package.py
  python3 tools/package.py --check
  python3 tools/package.py --org-config tenant.json --output-dir /tmp/tenant-dist
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required to run tools/package.py") from exc

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
SHARED_TRAPS_DIR = ROOT / "shared" / "traps"
SHARED_BASELINES_DIR = ROOT / "shared" / "baselines"
SHARED_EIO_PATH = ROOT / "shared" / "scripts" / "enterprise_io.py"
DEFAULT_DIST_DIR = ROOT / "dist"
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)

LINK_REWRITE_RE = re.compile(r"(\[[^\]]+\]\()([^)\s]+)(\))")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_default_config(schema: dict[str, Any]) -> dict[str, Any]:
    """Derive deterministic default config.json from a plugin config.schema.json."""
    props = schema.get("properties", {})
    cfg: dict[str, Any] = {}
    for key, spec in props.items():
        if "default" in spec:
            cfg[key] = spec["default"]
    cfg["org_configured"] = False
    return cfg


def _validate_value_against_prop(key: str, val: Any, prop: dict[str, Any], plugin_id: str) -> None:
    expected_type = prop.get("type")
    if expected_type == "boolean":
        if not isinstance(val, bool):
            raise ValueError(f"{plugin_id}.{key}: expected boolean, got {type(val).__name__}")
    elif expected_type == "integer":
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(f"{plugin_id}.{key}: expected integer, got {type(val).__name__}")
    elif expected_type == "number":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"{plugin_id}.{key}: expected number, got {type(val).__name__}")
    elif expected_type == "string":
        if not isinstance(val, str):
            raise ValueError(f"{plugin_id}.{key}: expected string, got {type(val).__name__}")
    elif expected_type == "array":
        if not isinstance(val, list):
            raise ValueError(f"{plugin_id}.{key}: expected array, got {type(val).__name__}")
    elif expected_type == "object":
        if not isinstance(val, dict):
            raise ValueError(f"{plugin_id}.{key}: expected object, got {type(val).__name__}")

    if "enum" in prop and val not in prop["enum"]:
        raise ValueError(f"{plugin_id}.{key}: {val!r} not in allowed enum {prop['enum']}")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if "minimum" in prop and val < prop["minimum"]:
            raise ValueError(f"{plugin_id}.{key}: {val} < minimum {prop['minimum']}")
        if "exclusiveMinimum" in prop and val <= prop["exclusiveMinimum"]:
            raise ValueError(f"{plugin_id}.{key}: {val} <= exclusiveMinimum {prop['exclusiveMinimum']}")
        if "maximum" in prop and val > prop["maximum"]:
            raise ValueError(f"{plugin_id}.{key}: {val} > maximum {prop['maximum']}")
    if isinstance(val, str) and "minLength" in prop and len(val) < prop["minLength"]:
        raise ValueError(f"{plugin_id}.{key}: string shorter than minLength {prop['minLength']}")


def resolve_org_config(
    plugin_id: str,
    schema: dict[str, Any],
    org_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build config.json dict, applying and validating --org-config overrides when present."""
    cfg = build_default_config(schema)
    if org_payload is None:
        return cfg

    if not isinstance(org_payload, dict):
        raise ValueError("Org config JSON root must be an object.")

    props = schema.get("properties", {})
    allow_extra = schema.get("additionalProperties", True)
    merged_overrides: dict[str, Any] = {}

    if "organization_name" in org_payload:
        merged_overrides["organization_name"] = org_payload["organization_name"]

    global_block = org_payload.get("global", {})
    if global_block:
        if not isinstance(global_block, dict):
            raise ValueError("org_config.global must be an object.")
        for k, v in global_block.items():
            if k in props or allow_extra:
                merged_overrides[k] = v

    plugins_block = org_payload.get("plugins", {})
    if plugins_block:
        if not isinstance(plugins_block, dict):
            raise ValueError("org_config.plugins must be an object.")
        plugin_overrides = plugins_block.get(plugin_id, {})
        if not isinstance(plugin_overrides, dict):
            raise ValueError(f"org_config.plugins[{plugin_id!r}] must be an object.")
        merged_overrides.update(plugin_overrides)

    # Also support top-level keys directly matching schema properties when non-container keys exist
    reserved = {"organization_name", "global", "plugins"}
    for k, v in org_payload.items():
        if k not in reserved:
            if k in props:
                merged_overrides[k] = v
            elif not plugins_block and not allow_extra:
                raise ValueError(f"{plugin_id}: unknown config property {k!r}")

    for k, v in merged_overrides.items():
        if k not in props and not allow_extra:
            raise ValueError(f"{plugin_id}: unknown config property {k!r} (additionalProperties=false)")
        if k in props:
            _validate_value_against_prop(k, v, props[k], plugin_id)
        cfg[k] = v

    cfg["org_configured"] = True
    return cfg


def format_config_json(cfg: dict[str, Any]) -> bytes:
    return (json.dumps(cfg, indent=2) + "\n").encode("utf-8")


def _strip_frontmatter(skill_md_text: str) -> str:
    norm = skill_md_text.replace("\r\n", "\n")
    if norm.startswith("---\n"):
        end = norm.find("\n---\n", 4)
        if end != -1:
            return norm[end + 5 :].lstrip("\n")
    return norm


def _rewrite_workflow_links(body: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        prefix, target, suffix = match.groups()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        if target.startswith("scripts/"):
            return f"{prefix}../../{target}{suffix}"
        if target.startswith("references/"):
            rel = target[len("references/") :]
            return f"{prefix}../{rel}{suffix}"
        return match.group(0)

    return LINK_REWRITE_RE.sub(_repl, body)


def render_bundle_skill_md(
    plugin_meta: dict[str, Any],
    connectors_meta: dict[str, Any],
    policy_meta: dict[str, Any],
    skill_entries: list[dict[str, Any]],
) -> str:
    """Synthesize the root router SKILL.md for a 1-click department bundle."""
    plugin_id = plugin_meta["id"]
    plugin_name = plugin_meta["name"]
    skill_names = ", ".join(s["id"] for s in skill_entries)

    # Ensure strictly <= 1024 chars and free of '<' or '>'
    pos_clause = f"Use when routing or executing {plugin_name} workflows ({skill_names})."
    neg_clause = (
        f"Don't use for unrelated domains outside {plugin_id} or automated external mutations without HITL confirmation."
    )
    base_desc = plugin_meta["description"].replace("<", "").replace(">", "").strip()
    desc = f"{base_desc} {pos_clause} {neg_clause}"
    if len(desc) > 1024:
        avail = 1024 - len(pos_clause) - len(neg_clause) - 5
        desc = f"{base_desc[:avail].rstrip()}... {pos_clause} {neg_clause}"

    lines: list[str] = [
        "---",
        f"name: {plugin_id}",
        f"description: {json.dumps(desc)}",
        "created_by: gemini-agent-plugins",
        "---",
        "",
        f"# {plugin_name} (Department Bundle)",
        "",
        f"{plugin_meta['description']}",
        "",
        "## Workflow Router Matrix",
        "",
        "Select the workflow guide and Python engine matching the user's request:",
        "",
        "| Skill ID | Workflow Guide | Deterministic Engine | Purpose |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for s in skill_entries:
        sid = s["id"]
        script_rel = s["script"]
        script_name = posixpath.basename(script_rel)
        lines.append(
            f"| `{sid}` | [{sid}.md](references/workflows/{sid}.md) | [{script_name}]({script_rel}) | {s['summary']} |"
        )

    lines.extend(
        [
            "",
            "## Three-Mode Connector Graceful Degradation",
            "",
            "Inspect available tools first and degrade cleanly without failing when enterprise connectors are absent:",
            "",
            "| Capability | Mode A — Live Enterprise Connectors | Mode B — Google Workspace Fallback | Mode C — Direct Local File Upload |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )
    for cap in connectors_meta.get("capabilities", []):
        mode_a = ", ".join(c["connector"] for c in cap["mode_a_live_connectors"])
        mode_b_srcs = ", ".join(cap["mode_b_workspace_fallback"]["google_workspace_sources"])
        mode_b_hint = cap["mode_b_workspace_fallback"]["lookup_hint"]
        mode_c = ", ".join(f".{fmt}" for fmt in cap["mode_c_local_file_formats"])
        lines.append(
            f"| `{cap['id']}` | {mode_a} | {mode_b_srcs} ({mode_b_hint}) | {mode_c} |"
        )

    lines.extend(
        [
            "",
            "## Org Configuration & Starter Baseline Rule",
            "",
            "1. Read [config.json](references/config.json) using `view_file` (or check a user-supplied organization playbook file).",
            "2. Check the boolean flag `org_configured`.",
            "3. When `org_configured` is `false`, evaluate strictly against the bundled starter baseline rubrics and stamp the top of every deliverable verbatim with:",
            "   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`",
            "",
            "Bundled baseline rubrics:",
        ]
    )
    for b in plugin_meta["shared_baselines"]:
        lines.append(f"- [{b}](references/baselines/{b})")

    first_script_rel = skill_entries[0]["script"]
    first_module = posixpath.splitext(posixpath.basename(first_script_rel))[0]
    first_skill_id = skill_entries[0]["id"]
    lines.extend(
        [
            "",
            "## In-Memory Python RAM Execution Pattern",
            "",
            "Always run deterministic calculations in Python RAM rather than estimating tables or totals in prompt tokens. Because runtime shells start in `/workspace` while bundles and individual skills unpack under `skills/<slug>/` or `skills/user-skills/<slug>/`, always resolve `SKILL_DIR` dynamically before importing scripts or reading references.",
            "",
            "- **Zero-dependency enterprise ingestion:** Every engine uses [enterprise_io.py](scripts/enterprise_io.py) to parse multi-tab `.xlsx`/`.xlsm` workbooks (1900/1904 dates, inline/shared strings, formula cached values), `.docx` documents (sections, headings, embedded tables, footnotes/comments), UTF-8 BOM `.csv`/`.tsv`, `.json`, and `.jsonl` directly from `--input` without needing `openpyxl` or `python-docx`. Pass `--sheet <TabNameOrIndex>` (or `sheet='...'` in `analyze()`) to analyze a specific worksheet by tab name or 0-based index.",
            "",
            "Using persistent `pyrepl`:",
            "",
            "```python",
            "import json",
            "import sys",
            "from pathlib import Path",
            "",
            "SKILL_DIR = next(",
            "    (",
            "        p",
            "        for p in (",
            f"            Path(\"skills/{plugin_id}\"),",
            f"            Path(\"skills/user-skills/{plugin_id}\"),",
            f"            Path(\"skills/{first_skill_id}\"),",
            f"            Path(\"skills/user-skills/{first_skill_id}\"),",
            "            Path(\".\"),",
            "        )",
            f"        if (p / \"{first_script_rel}\").is_file()",
            "    ),",
            f"    next((p.parent.parent for p in Path(\"skills\").rglob(\"{first_script_rel}\")), Path(\".\")),",
            ")",
            "sys.modules.pop(\"scripts\", None)",
            "sys.path.insert(0, str(SKILL_DIR))",
            f"from scripts.{first_module} import analyze, render_markdown",
            "",
            "cfg = json.loads((SKILL_DIR / \"references\" / \"config.json\").read_text(encoding=\"utf-8\"))",
            "# Pass loaded Mode A/B/C payload in RAM without flooding prompt tokens:",
            "# result = analyze(payload, config=SKILL_DIR / \"references\" / \"config.json\")",
            "# print(render_markdown(result))",
            "```",
            "",
            "Using CLI fallback (`python3` from `/workspace` or bundle root):",
            "",
            "```bash",
            "SKILL_DIR=\".\"",
            f"for d in skills/{plugin_id} skills/user-skills/{plugin_id} skills/*; do",
            f"  [ -f \"$d/{first_script_rel}\" ] && SKILL_DIR=\"$d\" && break",
            "done",
        ]
    )
    for s in skill_entries:
        lines.append(
            f"python3 \"$SKILL_DIR/{s['script']}\" --input payload.json --config \"$SKILL_DIR/references/config.json\" --format markdown"
        )
    lines.extend(
        [
            "# Or pass .xlsx / .docx / .csv directly (optional --sheet \"TabName\" or --sheet 0):",
            f"# python3 \"$SKILL_DIR/{first_script_rel}\" --input workbook.xlsx --config \"$SKILL_DIR/references/config.json\" --format markdown",
            "# Inspect CLI flags directly:",
        ]
    )
    for s in skill_entries:
        lines.append(f"python3 \"$SKILL_DIR/{s['script']}\" --help")
    lines.extend(
        [
            "```",
            "",
            "## Enterprise API & Analytical Traps",
            "",
            "Apply every bundled trap sheet before interpreting missing records, API page limits, currency scales, or untrusted external text:",
            "",
        ]
    )
    for t in plugin_meta["shared_traps"]:
        lines.append(f"- [{t}](references/traps/{t})")

    lines.extend(
        [
            "",
            "## HITL Mutation & Policy Guardrails",
            "",
            "- **Read-only operations (auto-run):** "
            + ", ".join(f"`{t}`" for t in policy_meta.get("read_only_tools", [])),
            "- **Draft-only operations (auto-run):** "
            + ", ".join(f"`{t}`" for t in policy_meta.get("draft_only_tools", [])),
            "- **HITL-gated external mutations (require explicit user confirmation):**",
        ]
    )
    for gate in policy_meta.get("hitl_gated_mutations", []):
        lines.append(
            f"  - `{gate['tool']}` (scope: `{gate['scope']}`) — {gate['reason']}"
        )

    lines.append("")
    return "\n".join(lines)


def _make_zip_bytes(entries: dict[str, tuple[bytes, int]]) -> bytes:
    """Create a deterministic in-memory zip archive from {rel_path: (bytes, mode)}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel_path in sorted(entries):
            data, mode = entries[rel_path]
            zi = zipfile.ZipInfo(filename=rel_path, date_time=FIXED_ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3  # UNIX
            zi.external_attr = (mode & 0xFFFF) << 16
            zf.writestr(zi, data)
    return buf.getvalue()


def discover_plugins() -> list[Path]:
    if not PLUGINS_DIR.is_dir():
        return []
    return sorted(p for p in PLUGINS_DIR.iterdir() if p.is_dir() and (p / ".gemini-plugin" / "plugin.json").is_file())


def sync_and_build(
    *,
    org_payload: dict[str, Any] | None = None,
    output_dir: Path = DEFAULT_DIST_DIR,
    target_plugin: str | None = None,
    check_only: bool = False,
) -> dict[str, Any]:
    plugins = discover_plugins()
    if target_plugin:
        plugins = [p for p in plugins if p.name == target_plugin]
        if not plugins:
            raise ValueError(f"Plugin {target_plugin!r} not found under {PLUGINS_DIR}.")

    drift_errors: list[str] = []
    manifest_bundles: list[dict[str, Any]] = []
    manifest_skills: list[dict[str, Any]] = []
    if not SHARED_EIO_PATH.is_file():
        raise FileNotFoundError(f"Missing shared enterprise ingestion helper: {SHARED_EIO_PATH}")
    eio_bytes = SHARED_EIO_PATH.read_bytes()

    bundles_dir = output_dir / "bundles"
    skills_dir = output_dir / "skills"
    if not check_only:
        bundles_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)

    for plugin_dir in plugins:
        plugin_meta = load_json(plugin_dir / ".gemini-plugin" / "plugin.json")
        plugin_id = plugin_meta["id"]
        connectors_meta = load_yaml(plugin_dir / ".gemini-plugin" / "connectors.yaml")
        policy_meta = load_yaml(plugin_dir / ".gemini-plugin" / "policy.cel")
        config_schema = load_json(plugin_dir / ".gemini-plugin" / "config.schema.json")

        default_cfg_bytes = format_config_json(build_default_config(config_schema))
        stamped_cfg = resolve_org_config(plugin_id, config_schema, org_payload)
        stamped_cfg_bytes = format_config_json(stamped_cfg)

        shared_trap_bytes = {
            name: (SHARED_TRAPS_DIR / name).read_bytes() for name in plugin_meta["shared_traps"]
        }
        shared_baseline_bytes = {
            name: (SHARED_BASELINES_DIR / name).read_bytes() for name in plugin_meta["shared_baselines"]
        }

        bundle_entries: dict[str, tuple[bytes, int]] = {
            "references/config.json": (stamped_cfg_bytes, 0o100644),
            "scripts/enterprise_io.py": (eio_bytes, 0o100644),
        }
        for name, data in shared_trap_bytes.items():
            bundle_entries[f"references/traps/{name}"] = (data, 0o100644)
        for name, data in shared_baseline_bytes.items():
            bundle_entries[f"references/baselines/{name}"] = (data, 0o100644)

        skill_entries = plugin_meta["skills"]
        for skill_spec in skill_entries:
            skill_id = skill_spec["id"]
            skill_root = plugin_dir / "skills" / skill_id
            script_rel = skill_spec["script"]
            script_path = skill_root / script_rel
            skill_md_path = skill_root / "SKILL.md"

            # 1. Sync or check source references/ directory (default baseline config only)
            expected_source_refs: dict[str, bytes] = {
                "config.json": default_cfg_bytes,
                **{f"traps/{k}": v for k, v in shared_trap_bytes.items()},
                **{f"baselines/{k}": v for k, v in shared_baseline_bytes.items()},
            }
            refs_dir = skill_root / "references"
            if check_only:
                if not refs_dir.is_dir():
                    drift_errors.append(f"Missing materialized references/ dir: {refs_dir}")
                else:
                    actual_rels = {
                        p.relative_to(refs_dir).as_posix(): p.read_bytes()
                        for p in refs_dir.rglob("*")
                        if p.is_file()
                    }
                    if set(actual_rels) != set(expected_source_refs):
                        drift_errors.append(
                            f"Reference file set mismatch in {refs_dir}: "
                            f"expected {sorted(expected_source_refs)}, got {sorted(actual_rels)}"
                        )
                    else:
                        for rel, expected_b in expected_source_refs.items():
                            if actual_rels[rel] != expected_b:
                                drift_errors.append(f"Drifted reference file: {refs_dir / rel}")
            else:
                if refs_dir.exists():
                    for existing in list(refs_dir.rglob("*")):
                        if existing.is_file():
                            rel = existing.relative_to(refs_dir).as_posix()
                            if rel not in expected_source_refs:
                                existing.unlink()
                for rel, content in expected_source_refs.items():
                    dest = refs_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(content)

            # 1b. Sync or check scripts/enterprise_io.py inside skill scripts/
            dest_eio = script_path.parent / "enterprise_io.py"
            if check_only:
                if not dest_eio.is_file() or dest_eio.read_bytes() != eio_bytes:
                    drift_errors.append(f"Drifted or missing enterprise_io.py: {dest_eio}")
            else:
                dest_eio.write_bytes(eio_bytes)

            # 2. Build granular 1-hop skill zip
            skill_md_bytes = skill_md_path.read_bytes()
            script_bytes = script_path.read_bytes()
            skill_zip_entries: dict[str, tuple[bytes, int]] = {
                "SKILL.md": (skill_md_bytes, 0o100644),
                script_rel: (script_bytes, 0o100755),
                "scripts/enterprise_io.py": (eio_bytes, 0o100644),
                "references/config.json": (stamped_cfg_bytes, 0o100644),
            }
            for name, data in shared_trap_bytes.items():
                skill_zip_entries[f"references/traps/{name}"] = (data, 0o100644)
            for name, data in shared_baseline_bytes.items():
                skill_zip_entries[f"references/baselines/{name}"] = (data, 0o100644)

            skill_zip_bytes = _make_zip_bytes(skill_zip_entries)
            skill_zip_path = skills_dir / f"{skill_id}.zip"
            if check_only:
                if not skill_zip_path.is_file() or skill_zip_path.read_bytes() != skill_zip_bytes:
                    drift_errors.append(f"Out-of-sync skill zip: {skill_zip_path}")
            else:
                skill_zip_path.write_bytes(skill_zip_bytes)

            manifest_skills.append(
                {
                    "id": skill_id,
                    "plugin_id": plugin_id,
                    "path": skill_zip_path.relative_to(output_dir).as_posix(),
                    "size_bytes": len(skill_zip_bytes),
                    "sha256": hashlib.sha256(skill_zip_bytes).hexdigest(),
                    "file_count": len(skill_zip_entries),
                    "included_files": sorted(skill_zip_entries),
                }
            )

            # 3. Contribute workflow & script to department bundle
            wf_body = _rewrite_workflow_links(_strip_frontmatter(skill_md_bytes.decode("utf-8")))
            wf_md = f"# Workflow: {skill_id}\n\n{wf_body.strip()}\n"
            bundle_entries[f"references/workflows/{skill_id}.md"] = (wf_md.encode("utf-8"), 0o100644)
            bundle_entries[script_rel] = (script_bytes, 0o100755)

        bundle_skill_md = render_bundle_skill_md(
            plugin_meta, connectors_meta, policy_meta, skill_entries
        )
        bundle_entries["SKILL.md"] = (bundle_skill_md.encode("utf-8"), 0o100644)
        bundle_zip_bytes = _make_zip_bytes(bundle_entries)
        bundle_zip_path = bundles_dir / f"{plugin_id}.zip"
        if check_only:
            if not bundle_zip_path.is_file() or bundle_zip_path.read_bytes() != bundle_zip_bytes:
                drift_errors.append(f"Out-of-sync bundle zip: {bundle_zip_path}")
        else:
            bundle_zip_path.write_bytes(bundle_zip_bytes)

        manifest_bundles.append(
            {
                "id": plugin_id,
                "name": plugin_meta["name"],
                "category": plugin_meta["category"],
                "path": bundle_zip_path.relative_to(output_dir).as_posix(),
                "size_bytes": len(bundle_zip_bytes),
                "sha256": hashlib.sha256(bundle_zip_bytes).hexdigest(),
                "skill_ids": [s["id"] for s in skill_entries],
                "file_count": len(bundle_entries),
                "included_files": sorted(bundle_entries),
            }
        )

    manifest = {
        "version": "1.0.0",
        "generated_by": "tools/package.py",
        "org_configured": bool(org_payload is not None),
        "organization_name": (
            org_payload.get("organization_name", "Configured Organization")
            if org_payload is not None
            else "Standard Baseline Tenant"
        ),
        "bundle_count": len(manifest_bundles),
        "skill_count": len(manifest_skills),
        "bundles": manifest_bundles,
        "skills": manifest_skills,
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    manifest_path = output_dir / "manifest.json"

    if check_only:
        if not manifest_path.is_file() or manifest_path.read_bytes() != manifest_bytes:
            drift_errors.append(f"Out-of-sync manifest: {manifest_path}")
        if drift_errors:
            raise RuntimeError("Packaging drift detected:\n" + "\n".join(f"  - {e}" for e in drift_errors))
    else:
        manifest_path.write_bytes(manifest_bytes)

    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package Gemini Agent plugins and skills.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify references/ and dist/ archives match source without writing.",
    )
    parser.add_argument(
        "--org-config",
        type=Path,
        help="Optional tenant JSON config to validate and stamp org_configured=true into zips.",
    )
    parser.add_argument(
        "--plugin",
        help="Optional single plugin ID to package (useful with --org-config).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Destination directory for packaged zips (defaults to dist/, or dist-org/ with --org-config).",
    )
    args = parser.parse_args(argv)

    if args.check and args.org_config:
        print("ERROR: --check cannot be combined with --org-config.", file=sys.stderr)
        return 2

    org_payload = None
    if args.org_config:
        org_payload = load_json(args.org_config)
        out_dir = args.output_dir or (ROOT / "dist-org")
    else:
        out_dir = args.output_dir or DEFAULT_DIST_DIR

    try:
        manifest = sync_and_build(
            org_payload=org_payload,
            output_dir=out_dir,
            target_plugin=args.plugin,
            check_only=args.check,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    action = "CHECK PASSED" if args.check else "PACKAGED"
    print(
        f"{action}: {manifest['bundle_count']} bundles, {manifest['skill_count']} skills "
        f"(org_configured={manifest['org_configured']}) -> {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
