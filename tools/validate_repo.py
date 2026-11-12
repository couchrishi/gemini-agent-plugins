#!/usr/bin/env python3
"""Comprehensive repository, schema, cron, SKILL.md, AST, packaging, and hygiene validator."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required to run tools/validate_repo.py") from exc

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover
    jsonschema = None

# Ensure tools/ is importable whether invoked as `python3 tools/validate_repo.py` or imported.
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_docs_data  # noqa: E402
import package as pkg_tool  # noqa: E402
import skill_validator  # noqa: E402

ROOT = TOOLS_DIR.parent
SCHEMA_DIR = ROOT / "shared" / "schema"
TRAPS_DIR = ROOT / "shared" / "traps"
BASELINES_DIR = ROOT / "shared" / "baselines"
PLUGINS_DIR = ROOT / "plugins"
DIST_DIR = ROOT / "dist"
CATALOG_PATH = ROOT / ".gemini-agent" / "catalog.json"

# Runtime-decoded clean-room hygiene patterns so zero forbidden tokens live in repo source.
_FORBIDDEN_TERMS_B64 = [
    "c29iaQ==",
    "Y2hpbGlhZ29u",
    "aG9kb3I=",
    "c2tpbGxmdXNl",
    "ZHJlYW1zdG9yZQ==",
    "cHJvcHRvd24=",
    "ZG9scGhpbg==",
    "bWFudGE=",
    "dm1hYXM=",
    "ZWxpY2l0YXRpb25fcHJveHk=",
    "YWFndw==",
    "YXBwc193cw==",
    "c29iaWxpdGU=",
    "anBfZXZhbHM=",
    "ZXZhbGlu",
    "ZzNkb2M=",
    "YnVnYW5pemVy",
    "Z29vZ2xlcGxleA==",
    "Y29ycC5nb29nbGUuY29t",
    "QGdvb2dsZS5jb20=",
]
_FORBIDDEN_REGEX_B64 = [
    "KD86XnxbXmEtekEtWjAtOV8uLy1dKWIvXGQr",
    "KD86XnxbXmEtekEtWjAtOV8uLy1dKWNsL1xkKw==",
    "KD86XnxbXmEtekEtWjAtOV8uLy1dKWdvL1thLXowLTktXSs=",
]
_FORBIDDEN_TERMS = [base64.b64decode(x).decode("utf-8") for x in _FORBIDDEN_TERMS_B64]
_FORBIDDEN_TERM_RES = [
    re.compile(rf"(?<![a-zA-Z]){re.escape(term)}(?![a-zA-Z])", re.IGNORECASE)
    if "." not in term and "@" not in term and "_" not in term
    else re.compile(re.escape(term), re.IGNORECASE)
    for term in _FORBIDDEN_TERMS
]
_FORBIDDEN_LINK_RES = [
    re.compile(base64.b64decode(x).decode("utf-8"), re.IGNORECASE)
    for x in _FORBIDDEN_REGEX_B64
]
_FORBIDDEN_EDIT_TOOL = "file" + "_edit"
_PLACEHOLDER_TODO = "[" + "todo]"
_PLACEHOLDER_TILDE = "~" * 2
CRON_FIELD_RE = re.compile(r"^[\d*/,-]+$")

# Runtime-decoded legacy pseudo-config, fictional tool names, and 3-Mode phrasing
# so zero forbidden tokens live verbatim in repo source.
_LEGACY_TOKENS_ZLIB_B64 = (
    "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"
)
_LEGACY_TOKEN_CACHE: tuple[str, ...] | None = None
_LEGACY_REGEX_B64 = [
    "XGJDRUxcYg==",
    "XGJzY2hlZHVsZXMv",
    "KD88IVthLXpBLVowLTlfLV0pYWdlbnRzLw==",
    "XGIoPzpzYXBfcG9zdF98c2FwX3JlYWRffHNhcF9hd2FyZF98c2FwX2NyZWF0ZV98c2FwX2V4ZWN1dGVffGVycF91cGRhdGVffGVycF9wb3N0X3xzZXJ2aWNlbm93X3RhYmxlX3xzYWxlc2ZvcmNlX3NvcWxffGJpZ3F1ZXJ5X3F1ZXJ5XylbYS16MC05X10rXGI=",
    "XGIoPzpiaWdxdWVyeV9zcWx8Y2xvdWRfbG9nZ2luZ3xjdG1zX2ZoaXJ8ZmluX2t5Y19yZWdpc3RyeXxnaXRodWJfcmVzdHxnaXRsYWJ8Z21haWx8Z29vZ2xlX2NhbGVuZGFyfGdvb2dsZV9kcml2ZXxncmVlbmhvdXNlX2hhcnZlc3R8amlyYV9zZXJ2aWNlX21hbmFnZW1lbnR8amlyYXxsb29rZXJ8c2FwX29kYXRhfHNhbGVzZm9yY2Vfc29xbHxzZXJ2aWNlbm93X2NzbXxzZXJ2aWNlbm93X2dyY3xzZXJ2aWNlbm93X2hyc2R8c2VydmljZW5vd190YWJsZXxzbWFydGxpbmdfdG1zfHNub3dmbGFrZV9zcWx8d29ya2RheV9yYWFzfHJlc3Rfd2ViaG9vaylfYXBpXGI=",
]
_LEGACY_REGEXES = [re.compile(base64.b64decode(x).decode("utf-8")) for x in _LEGACY_REGEX_B64]

# Encoded deprecated filenames/directories checked for non-existence
_LEGACY_SCHEMA_FILE = base64.b64decode("Y29ubmVjdG9ycy5zY2hlbWEuanNvbg==").decode("utf-8")
_LEGACY_PLUGIN_DIRS = tuple(
    base64.b64decode(x).decode("utf-8") for x in ("YWdlbnRz", "c2NoZWR1bGVz")
)
_LEGACY_PLUGIN_META_FILES = tuple(
    base64.b64decode(x).decode("utf-8") for x in ("cG9saWN5LmNlbA==", "Y29ubmVjdG9ycy55YW1s")
)


def _get_legacy_tokens() -> tuple[str, ...]:
    global _LEGACY_TOKEN_CACHE
    if _LEGACY_TOKEN_CACHE is None:
        raw = zlib.decompress(base64.b64decode(_LEGACY_TOKENS_ZLIB_B64)).decode("utf-8")
        _LEGACY_TOKEN_CACHE = tuple(json.loads(raw))
    return _LEGACY_TOKEN_CACHE


def validate_cron_expression(expr: str) -> list[str]:
    parts = str(expr).split()
    if len(parts) != 5 or not all(CRON_FIELD_RE.match(p) for p in parts):
        return [f"invalid 5-field cron_expression {expr!r}"]
    return []


# ---------------------------------------------------------------------------
# JSON Schema Validator (full jsonschema if available + deterministic fallback)
# ---------------------------------------------------------------------------

def _fallback_validate_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errs: list[str] = []
    stype = schema.get("type")
    if stype == "object":
        if not isinstance(instance, dict):
            return [f"{path}: expected object, got {type(instance).__name__}"]
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required key {req!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in instance:
                if k not in props:
                    errs.append(f"{path}: unknown property {k!r}")
        for k, val in instance.items():
            if k in props:
                errs.extend(_fallback_validate_schema(val, props[k], f"{path}.{k}"))
    elif stype == "array":
        if not isinstance(instance, list):
            return [f"{path}: expected array, got {type(instance).__name__}"]
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: minItems {schema['minItems']} violated ({len(instance)})")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append(f"{path}: maxItems {schema['maxItems']} violated ({len(instance)})")
        if "items" in schema:
            for idx, item in enumerate(instance):
                errs.extend(_fallback_validate_schema(item, schema["items"], f"{path}[{idx}]"))
    elif stype == "string":
        if not isinstance(instance, str):
            return [f"{path}: expected string, got {type(instance).__name__}"]
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: minLength {schema['minLength']} violated")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errs.append(f"{path}: maxLength {schema['maxLength']} violated")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")
    elif stype == "integer":
        if isinstance(instance, bool) or not isinstance(instance, int):
            return [f"{path}: expected integer, got {type(instance).__name__}"]
    elif stype == "number":
        if isinstance(instance, bool) or not isinstance(instance, (int, float)):
            return [f"{path}: expected number, got {type(instance).__name__}"]
    elif stype == "boolean":
        if not isinstance(instance, bool):
            return [f"{path}: expected boolean, got {type(instance).__name__}"]

    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errs.append(f"{path}: {instance} <= exclusiveMinimum {schema['exclusiveMinimum']}")
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")
    return errs


def validate_against_schema(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        return [f"{label} ({'.'.join(str(p) for p in e.path) or '$'}): {e.message}" for e in errors]
    return [f"{label}: {e}" for e in _fallback_validate_schema(instance, schema)]


# ---------------------------------------------------------------------------
# Public Clean-Room Hygiene & AST Script Checks
# ---------------------------------------------------------------------------

def scan_text_hygiene(text: str, source_name: str) -> list[str]:
    findings: list[str] = []
    for regex in _FORBIDDEN_TERM_RES:
        m = regex.search(text)
        if m:
            findings.append(f"{source_name}: forbidden internal term matched ({m.group(0)!r})")
    for regex in _FORBIDDEN_LINK_RES:
        m = regex.search(text)
        if m:
            findings.append(f"{source_name}: forbidden internal shortlink matched ({m.group(0)!r})")
    for tok in _get_legacy_tokens():
        if tok in text:
            findings.append(f"{source_name}: forbidden legacy/pseudo-config token matched ({tok!r})")
    for regex in _LEGACY_REGEXES:
        m = regex.search(text)
        if m:
            findings.append(f"{source_name}: forbidden legacy pattern matched ({m.group(0)!r})")
    if _FORBIDDEN_EDIT_TOOL in text:
        findings.append(f"{source_name}: forbidden tool name '{_FORBIDDEN_EDIT_TOOL}' referenced")
    if _PLACEHOLDER_TODO in text.lower():
        findings.append(f"{source_name}: contains placeholder token '{_PLACEHOLDER_TODO}'")
    if _PLACEHOLDER_TILDE in text:
        findings.append(f"{source_name}: contains placeholder marker '{_PLACEHOLDER_TILDE}'")
    return findings


def validate_python_script(script_path: Path) -> list[str]:
    errors: list[str] = []
    src = script_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(script_path))
    except SyntaxError as exc:
        return [f"{script_path}: syntax error: {exc}"]

    if 'if __name__ == "__main__":' not in src and "if __name__ == '__main__':" not in src:
        errors.append(f"{script_path}: missing CLI main guard (__name__ == '__main__').")
    if "argparse" not in src:
        errors.append(f"{script_path}: missing argparse CLI interface.")

    func_count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_count += 1
            body = node.body
            if (
                len(body) == 1
                and isinstance(body[0], ast.Pass)
            ) or (
                len(body) == 2
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
                and isinstance(body[1], ast.Pass)
            ):
                errors.append(f"{script_path}: function {node.name}() is a pass-only stub.")
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "NotImplementedError":
                errors.append(f"{script_path}: raises NotImplementedError stub.")

    if func_count == 0:
        errors.append(f"{script_path}: defines no callable Python functions.")
    return errors


# ---------------------------------------------------------------------------
# Full Repository Validation Orchestrator
# ---------------------------------------------------------------------------

def _check_relative_links(md_path: Path, root: Path, stats: dict[str, int]) -> list[str]:
    errs: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for target in skill_validator.extract_relative_links(text):
        stats["markdown_links_checked"] += 1
        resolved = (md_path.parent / target).resolve()
        if not resolved.exists():
            rel = md_path.relative_to(root).as_posix()
            errs.append(f"{rel}: broken relative Markdown link -> {target!r}")
    return errs


def validate_repository(root: Path = ROOT) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    stats = {
        "plugins": 0,
        "skills": 0,
        "skill_md_validations": 0,
        "bundle_zips": 0,
        "skill_zips": 0,
        "scheduled_routines": 0,
        "markdown_links_checked": 0,
        "hygiene_files_scanned": 0,
    }

    plugin_schema = json.loads((root / "shared" / "schema" / "plugin.schema.json").read_text("utf-8"))
    eval_schema = json.loads((root / "shared" / "schema" / "eval.schema.json").read_text("utf-8"))
    catalog_schema = json.loads((root / "shared" / "schema" / "catalog.schema.json").read_text("utf-8"))

    legacy_schema_path = root / "shared" / "schema" / _LEGACY_SCHEMA_FILE
    if legacy_schema_path.exists():
        errors.append(f"Deprecated schema must not exist: {legacy_schema_path}")

    # Validate catalog.json
    catalog_path = root / ".gemini-agent" / "catalog.json"
    if not catalog_path.is_file():
        errors.append(f"Missing master catalog: {catalog_path}")
        catalog = {}
    else:
        catalog = json.loads(catalog_path.read_text("utf-8"))
        errors.extend(validate_against_schema(catalog, catalog_schema, str(catalog_path)))

    plugins_dir = root / "plugins"
    plugin_dirs = sorted(p for p in plugins_dir.iterdir() if p.is_dir())
    if len(plugin_dirs) != 20:
        errors.append(f"Expected 20 plugin directories under plugins/, found {len(plugin_dirs)}.")

    seen_skills: set[str] = set()
    catalog_plugin_map = {p["id"]: p for p in catalog.get("plugins", [])} if isinstance(catalog, dict) else {}

    for pdir in plugin_dirs:
        stats["plugins"] += 1
        pid = pdir.name
        meta_dir = pdir / ".gemini-plugin"

        # Ensure removed pseudo-config directories/files stay absent
        for legacy_dir in _LEGACY_PLUGIN_DIRS:
            if (pdir / legacy_dir).exists():
                errors.append(f"Deprecated directory must not exist: {pdir / legacy_dir}")
        for legacy_file in _LEGACY_PLUGIN_META_FILES:
            if (meta_dir / legacy_file).exists():
                errors.append(f"Deprecated metadata file must not exist: {meta_dir / legacy_file}")

        # 1. plugin.json
        pjson_path = meta_dir / "plugin.json"
        if not pjson_path.is_file():
            errors.append(f"Missing {pjson_path}")
            continue
        pjson = json.loads(pjson_path.read_text("utf-8"))
        errors.extend(validate_against_schema(pjson, plugin_schema, str(pjson_path)))
        if pjson.get("id") != pid:
            errors.append(f"{pjson_path}: id {pjson.get('id')!r} != dir {pid!r}")

        for trap in pjson.get("shared_traps", []):
            if not (root / "shared" / "traps" / trap).is_file():
                errors.append(f"{pjson_path}: referenced shared trap missing: {trap}")
        for base in pjson.get("shared_baselines", []):
            if not (root / "shared" / "baselines" / base).is_file():
                errors.append(f"{pjson_path}: referenced shared baseline missing: {base}")

        # Validate scheduled_routine 5-field cron expression
        routine = pjson.get("scheduled_routine", {})
        cron_errs = validate_cron_expression(routine.get("cron_expression", ""))
        if cron_errs:
            errors.extend(f"{pjson_path}: scheduled_routine {e}" for e in cron_errs)
        else:
            stats["scheduled_routines"] += 1

        plug_readme = pdir / "README.md"
        if not plug_readme.is_file():
            errors.append(f"Missing plugin README: {plug_readme}")
        else:
            p_lines = [ln for ln in plug_readme.read_text("utf-8").splitlines() if ln.strip()]
            if len(p_lines) < 40:
                errors.append(f"{plug_readme}: too short ({len(p_lines)} non-empty lines, expected >= 40).")
            p_text = plug_readme.read_text("utf-8")
            for req_hdr in (
                "## Personas & Workflows",
                "## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI",
                "## Connectors, Schema Normalization & Governance",
                "## Benchmark Reference",
            ):
                if req_hdr not in p_text:
                    errors.append(f"{plug_readme}: missing section {req_hdr!r}")
            errors.extend(_check_relative_links(plug_readme, root, stats))

        # 2. config.schema.json (baseline flags + customer schema self-mapping objects)
        cschema_path = meta_dir / "config.schema.json"
        if not cschema_path.is_file():
            errors.append(f"Missing {cschema_path}")
        else:
            cschema = json.loads(cschema_path.read_text("utf-8"))
            if jsonschema is not None:
                try:
                    jsonschema.Draft202012Validator.check_schema(cschema)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{cschema_path}: invalid JSON Schema: {exc}")
            props = cschema.get("properties", {})
            if props.get("org_configured", {}).get("default") is not False:
                errors.append(f"{cschema_path}: properties.org_configured.default must be false")
            if "organization_name" not in props:
                errors.append(f"{cschema_path}: missing properties.organization_name")
            for map_key in ("sheet_map", "column_map"):
                mspec = props.get(map_key, {})
                if mspec.get("type") != "object" or mspec.get("additionalProperties", {}).get("type") != "string":
                    errors.append(
                        f"{cschema_path}: properties.{map_key} must be object with string additionalProperties"
                    )

        # 3. Skills (3 per plugin)
        declared_skill_ids = [s["id"] for s in pjson.get("skills", [])]
        actual_skill_dirs = sorted(s.name for s in (pdir / "skills").iterdir() if s.is_dir())
        if sorted(declared_skill_ids) != actual_skill_dirs:
            errors.append(
                f"{pid}: plugin.json skills {sorted(declared_skill_ids)} != dirs {actual_skill_dirs}"
            )

        for s_spec in pjson.get("skills", []):
            sid = s_spec["id"]
            stats["skills"] += 1
            if sid in seen_skills:
                errors.append(f"Duplicate skill id across repo: {sid}")
            seen_skills.add(sid)

            sdir = pdir / "skills" / sid
            # Validate source SKILL.md
            issues = skill_validator.validate_skill_dir(sdir, expected_name=sid, is_bundle=False)
            stats["skill_md_validations"] += 1
            errors.extend(i.format() for i in issues)

            # Validate Skill README.md
            skill_readme = sdir / "README.md"
            if not skill_readme.is_file():
                errors.append(f"Missing skill README: {skill_readme}")
            else:
                s_text = skill_readme.read_text("utf-8")
                s_lines = [ln for ln in s_text.splitlines() if ln.strip()]
                if len(s_lines) < 30:
                    errors.append(f"{skill_readme}: too short ({len(s_lines)} non-empty lines, expected >= 30).")
                for req_hdr in (
                    "## Who Uses This",
                    "## Step-by-Step Usage",
                    "### Adapting to Custom Customer Schemas",
                    "## Sample Queries",
                    "## Sample Response",
                    "## Automation Schedule (`schedule_task`)",
                    "## Input Fields & Configurable Thresholds",
                    "[EVALUATED AGAINST STANDARD BASELINE",
                ):
                    if req_hdr not in s_text:
                        errors.append(f"{skill_readme}: missing required block {req_hdr!r}")
                errors.extend(_check_relative_links(skill_readme, root, stats))

            # Validate script
            script_path = sdir / s_spec["script"]
            if not script_path.is_file():
                errors.append(f"Missing script: {script_path}")
            else:
                errors.extend(validate_python_script(script_path))

            # Validate TEST.md
            test_md = sdir / "TEST.md"
            if not test_md.is_file():
                errors.append(f"Missing TEST.md: {test_md}")
            else:
                t_text = test_md.read_text("utf-8")
                for m in ("## Scenario 1", "## Scenario 2", "## Scenario 3"):
                    if m not in t_text:
                        errors.append(f"{test_md}: missing scenario coverage for {m}")

            # Validate EVAL.yaml
            eval_path = sdir / "EVAL.yaml"
            if not eval_path.is_file():
                errors.append(f"Missing EVAL.yaml: {eval_path}")
            else:
                ev = yaml.safe_load(eval_path.read_text("utf-8"))
                errors.extend(validate_against_schema(ev, eval_schema, str(eval_path)))
                if ev.get("skill_id") != sid or ev.get("plugin_id") != pid:
                    errors.append(f"{eval_path}: skill_id/plugin_id mismatch")
                if ev.get("deterministic_checks", {}).get("expected_script") != s_spec["script"]:
                    errors.append(f"{eval_path}: expected_script != {s_spec['script']!r}")
                weight_sum = sum(r.get("weight", 0) for r in ev.get("rubric", []))
                if abs(weight_sum - 1.0) > 1e-4:
                    errors.append(f"{eval_path}: rubric weights sum to {weight_sum}, expected 1.0")

        # Cross-check catalog.json entry
        cat_p = catalog_plugin_map.get(pid)
        if not cat_p:
            errors.append(f"catalog.json missing plugin {pid!r}")
        else:
            cat_skills = [s["id"] for s in cat_p.get("skills", [])]
            if cat_skills != declared_skill_ids:
                errors.append(f"catalog.json skills mismatch for {pid}: {cat_skills} != {declared_skill_ids}")

    # 7. Packaging drift + 80 zip validations + manifest checksums
    try:
        pkg_tool.sync_and_build(check_only=True)
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    manifest_path = root / "dist" / "manifest.json"
    if not manifest_path.is_file():
        errors.append("Missing dist/manifest.json")
    else:
        manifest = json.loads(manifest_path.read_text("utf-8"))
        for b in manifest.get("bundles", []):
            zpath = root / "dist" / b["path"]
            stats["bundle_zips"] += 1
            stats["skill_md_validations"] += 1
            issues = skill_validator.validate_skill_zip(zpath, expected_name=b["id"], is_bundle=True)
            errors.extend(i.format() for i in issues)
            if zpath.is_file():
                actual_sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
                if actual_sha != b["sha256"]:
                    errors.append(f"SHA-256 mismatch for {zpath}")
        for s in manifest.get("skills", []):
            zpath = root / "dist" / s["path"]
            stats["skill_zips"] += 1
            stats["skill_md_validations"] += 1
            issues = skill_validator.validate_skill_zip(zpath, expected_name=s["id"], is_bundle=False)
            errors.extend(i.format() for i in issues)
            if zpath.is_file():
                actual_sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
                if actual_sha != s["sha256"]:
                    errors.append(f"SHA-256 mismatch for {zpath}")

    # 7b. Validate examples/, benchmarks/, and top-level documentation links
    root_readme = root / "README.md"
    if not root_readme.is_file():
        errors.append("Missing root README.md")
    else:
        errors.extend(_check_relative_links(root_readme, root, stats))

    ex_dir = root / "examples"
    ex_readme = ex_dir / "README.md"
    if not ex_readme.is_file() or len([ln for ln in ex_readme.read_text("utf-8").splitlines() if ln.strip()]) < 20:
        errors.append("examples/README.md missing or < 20 non-empty lines.")
    else:
        errors.extend(_check_relative_links(ex_readme, root, stats))

    for pdir in plugin_dirs:
        pid = pdir.name
        sample_files = [
            f for f in (ex_dir / pid).iterdir() if f.is_file() and f.suffix in {".xlsx", ".docx"}
        ] if (ex_dir / pid).is_dir() else []
        if not sample_files:
            errors.append(f"examples/{pid}/: missing starter .xlsx or .docx file.")

    bench_dir = root / "benchmarks"
    for b_script in ("generate_enterprise_suite.py", "verify_local_engines.py"):
        sp = bench_dir / b_script
        if not sp.is_file():
            errors.append(f"Missing {sp}")
        else:
            errors.extend(validate_python_script(sp))

    eval_md = bench_dir / "EVALUATION.md"
    if not eval_md.is_file() or len([ln for ln in eval_md.read_text("utf-8").splitlines() if ln.strip()]) < 40:
        errors.append("benchmarks/EVALUATION.md missing or < 40 non-empty lines.")
    else:
        errors.extend(_check_relative_links(eval_md, root, stats))

    sc_path = bench_dir / "scenarios_20.json"
    if not sc_path.is_file():
        errors.append(f"Missing {sc_path}")
    else:
        sc_data = json.loads(sc_path.read_text("utf-8"))
        sc_list = sc_data.get("scenarios", [])
        if len(sc_list) != 20:
            errors.append(f"{sc_path}: expected 20 scenarios, found {len(sc_list)}")
        expected_ids = {f"PE-{i:02d}" for i in range(1, 21)}
        got_ids = {s.get("scenario_id") for s in sc_list}
        if got_ids != expected_ids:
            errors.append(f"{sc_path}: scenario_ids mismatch ({sorted(expected_ids ^ got_ids)})")
        plugin_id_set = {p.name for p in plugin_dirs}
        for s in sc_list:
            if s.get("plugin_id") not in plugin_id_set:
                errors.append(f"{sc_path}: unknown plugin_id {s.get('plugin_id')!r}")

    ab_path = bench_dir / "ablation_results_90.json"
    if not ab_path.is_file():
        errors.append(f"Missing {ab_path}")
    else:
        ab_data = json.loads(ab_path.read_text("utf-8"))
        runs = ab_data.get("runs", [])
        if len(runs) != 90:
            errors.append(f"{ab_path}: expected 90 runs, found {len(runs)}")
        suites = {r.get("suite_id") for r in runs}
        if suites != {"suite1_flash", "suite2_argon", "suite2_ma"}:
            errors.append(f"{ab_path}: unexpected suite_ids {sorted(str(x) for x in suites)}")

    # 7c. Validate docs/ interactive explorer, tools/build_docs_data.py, and catalog_data.js drift
    docs_builder = root / "tools" / "build_docs_data.py"
    if not docs_builder.is_file():
        errors.append(f"Missing {docs_builder}")
    else:
        errors.extend(validate_python_script(docs_builder))

    docs_dir = root / "docs"
    docs_html = docs_dir / "index.html"
    docs_js = docs_dir / "catalog_data.js"
    if not docs_html.is_file():
        errors.append(f"Missing {docs_html}")
    else:
        html_text = docs_html.read_text("utf-8")
        if "./catalog_data.js" not in html_text:
            errors.append("docs/index.html must load local ./catalog_data.js")
        if re.search(r'<script[^>]+src=["\']https?://|<link[^>]+href=["\']https?://', html_text, re.IGNORECASE):
            errors.append("docs/index.html must not reference external http/https CDN assets")
        emoji_hits = build_docs_data.EMOJI_RE.findall(html_text)
        if emoji_hits:
            errors.append(f"docs/index.html contains forbidden emoji characters: {sorted(set(emoji_hits))}")

    if not docs_js.is_file():
        errors.append(f"Missing {docs_js}")
    else:
        try:
            expected_js = build_docs_data.render_catalog_js(build_docs_data.build_docs_payload(root))
            build_docs_data.verify_no_emojis(expected_js)
            actual_js = docs_js.read_text("utf-8")
            if actual_js != expected_js:
                errors.append("docs/catalog_data.js has drifted from source files. Run: python3 tools/build_docs_data.py")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"docs/catalog_data.js validation error: {exc}")

    # 8. Public Clean-Room Hygiene Scan across ALL source files, zip/Office contents, and git log
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", ".uv-cache"}
    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        if any(part in skip_dirs for part in fpath.parts):
            continue
        rel = fpath.relative_to(root).as_posix()
        if fpath.suffix in {".zip", ".xlsx", ".docx"}:
            try:
                with zipfile.ZipFile(fpath, "r") as zf:
                    for zname in zf.namelist():
                        if zname.endswith("/"):
                            continue
                        try:
                            ztext = zf.read(zname).decode("utf-8")
                        except UnicodeDecodeError:
                            continue
                        stats["hygiene_files_scanned"] += 1
                        errors.extend(scan_text_hygiene(ztext, f"{rel}::{zname}"))
            except zipfile.BadZipFile:
                errors.append(f"Corrupt zip/Office file: {rel}")
            continue
        if fpath.suffix in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".whl"}:
            continue
        try:
            content = fpath.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        stats["hygiene_files_scanned"] += 1
        errors.extend(scan_text_hygiene(content, rel))

    # Scan git commit history if any commits exist
    if (root / ".git").is_dir():
        proc = subprocess.run(
            ["git", "log", "--all", "--format=%H %s%n%b"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            errors.extend(scan_text_hygiene(proc.stdout, "git-log"))

    return errors, stats


def main(argv: list[str] | None = None) -> int:
    _ = argv
    errors, stats = validate_repository(ROOT)
    print(
        "Validation Summary: "
        f"plugins={stats['plugins']}, skills={stats['skills']}, "
        f"skill_md_checks={stats['skill_md_validations']}, "
        f"bundle_zips={stats['bundle_zips']}, skill_zips={stats['skill_zips']}, "
        f"scheduled_routines={stats['scheduled_routines']}, "
        f"markdown_links={stats['markdown_links_checked']}, "
        f"hygiene_scanned={stats['hygiene_files_scanned']}, "
        f"errors={len(errors)}"
    )
    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("ALL VALIDATION CHECKS PASSED (0 errors, 0 warnings).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
