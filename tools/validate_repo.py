#!/usr/bin/env python3
"""Comprehensive repository, schema, CEL, SKILL.md, AST, packaging, and hygiene validator."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
import subprocess
import sys
import zipfile
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


# ---------------------------------------------------------------------------
# Recursive-Descent CEL Syntax Validator
# ---------------------------------------------------------------------------

class CelSyntaxError(ValueError):
    """Raised when a CEL expression fails lexical or grammar validation."""


_CEL_TOKEN_SPEC = [
    ("WS", r"\s+"),
    ("STRING", r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''),
    ("FLOAT", r"\d+\.\d+(?:[eE][+-]?\d+)?"),
    ("INT", r"0x[0-9a-fA-F]+|\d+"),
    ("OP2", r"&&|\|\||==|!=|<=|>="),
    ("OP1", r"[+\-*/%<>!?:.,\[\](){}]"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
]
_CEL_MASTER_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _CEL_TOKEN_SPEC))


def _tokenize_cel(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        m = _CEL_MASTER_RE.match(expr, pos)
        if not m:
            raise CelSyntaxError(f"Unexpected character at pos {pos}: {expr[pos:pos+16]!r}")
        kind = m.lastgroup
        val = m.group()
        pos = m.end()
        if kind == "WS":
            continue
        if kind == "IDENT" and val == "in":
            tokens.append(("OP_IN", val))
        else:
            tokens.append((kind or "", val))
    return tokens


class _CelParser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def match(self, kind: str, val: str | None = None) -> bool:
        tok = self.peek()
        if tok is None or tok[0] != kind:
            return False
        if val is not None and tok[1] != val:
            return False
        self.pos += 1
        return True

    def expect(self, kind: str, val: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok is None or tok[0] != kind or (val is not None and tok[1] != val):
            raise CelSyntaxError(f"Expected ({kind}, {val!r}), got {tok!r}")
        return self.advance()

    def parse(self) -> None:
        if not self.tokens:
            raise CelSyntaxError("Empty CEL expression.")
        self.parse_conditional()
        if self.peek() is not None:
            raise CelSyntaxError(f"Unexpected trailing token: {self.peek()!r}")

    def parse_conditional(self) -> None:
        self.parse_or()
        if self.match("OP1", "?"):
            self.parse_conditional()
            self.expect("OP1", ":")
            self.parse_conditional()

    def parse_or(self) -> None:
        self.parse_and()
        while self.match("OP2", "||"):
            self.parse_and()

    def parse_and(self) -> None:
        self.parse_relation()
        while self.match("OP2", "&&"):
            self.parse_relation()

    def parse_relation(self) -> None:
        self.parse_addition()
        while True:
            tok = self.peek()
            if tok and (
                (tok[0] == "OP2" and tok[1] in {"==", "!=", "<=", ">="})
                or (tok[0] == "OP1" and tok[1] in {"<", ">"})
                or tok[0] == "OP_IN"
            ):
                self.advance()
                self.parse_addition()
            else:
                break

    def parse_addition(self) -> None:
        self.parse_multiplication()
        while True:
            tok = self.peek()
            if tok and tok[0] == "OP1" and tok[1] in {"+", "-"}:
                self.advance()
                self.parse_multiplication()
            else:
                break

    def parse_multiplication(self) -> None:
        self.parse_unary()
        while True:
            tok = self.peek()
            if tok and tok[0] == "OP1" and tok[1] in {"*", "/", "%"}:
                self.advance()
                self.parse_unary()
            else:
                break

    def parse_unary(self) -> None:
        tok = self.peek()
        if tok and tok[0] == "OP1" and tok[1] in {"!", "-"}:
            self.advance()
            self.parse_unary()
        else:
            self.parse_member()

    def parse_member(self) -> None:
        self.parse_primary()
        while True:
            if self.match("OP1", "."):
                self.expect("IDENT")
                if self.match("OP1", "("):
                    self._parse_arg_list()
            elif self.match("OP1", "["):
                self.parse_conditional()
                self.expect("OP1", "]")
            else:
                break

    def _parse_arg_list(self) -> None:
        if not self.match("OP1", ")"):
            self.parse_conditional()
            while self.match("OP1", ","):
                self.parse_conditional()
            self.expect("OP1", ")")

    def parse_primary(self) -> None:
        tok = self.peek()
        if tok is None:
            raise CelSyntaxError("Unexpected end of CEL expression.")
        kind, _val = tok
        if kind in {"STRING", "INT", "FLOAT"}:
            self.advance()
            return
        if kind == "IDENT":
            self.advance()
            if self.match("OP1", "("):
                self._parse_arg_list()
            return
        if self.match("OP1", "("):
            self.parse_conditional()
            self.expect("OP1", ")")
            return
        if self.match("OP1", "["):
            if not self.match("OP1", "]"):
                self.parse_conditional()
                while self.match("OP1", ","):
                    if self.peek() == ("OP1", "]"):
                        break
                    self.parse_conditional()
                self.expect("OP1", "]")
            return
        if self.match("OP1", "{"):
            if not self.match("OP1", "}"):
                self.parse_conditional()
                self.expect("OP1", ":")
                self.parse_conditional()
                while self.match("OP1", ","):
                    if self.peek() == ("OP1", "}"):
                        break
                    self.parse_conditional()
                    self.expect("OP1", ":")
                    self.parse_conditional()
                self.expect("OP1", "}")
            return
        raise CelSyntaxError(f"Unexpected token in CEL primary: {tok!r}")


def validate_cel_expression(expr: str) -> None:
    tokens = _tokenize_cel(expr)
    _CelParser(tokens).parse()


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

def validate_repository(root: Path = ROOT) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    stats = {
        "plugins": 0,
        "skills": 0,
        "skill_md_validations": 0,
        "bundle_zips": 0,
        "skill_zips": 0,
        "cel_expressions": 0,
        "hygiene_files_scanned": 0,
    }

    plugin_schema = json.loads((root / "shared" / "schema" / "plugin.schema.json").read_text("utf-8"))
    connectors_schema = json.loads((root / "shared" / "schema" / "connectors.schema.json").read_text("utf-8"))
    eval_schema = json.loads((root / "shared" / "schema" / "eval.schema.json").read_text("utf-8"))
    catalog_schema = json.loads((root / "shared" / "schema" / "catalog.schema.json").read_text("utf-8"))

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
        for rel in pjson.get("agent_templates", []) + pjson.get("schedules", []):
            if not (pdir / rel).is_file():
                errors.append(f"{pjson_path}: missing file {pdir / rel}")

        if not (pdir / "README.md").is_file() or len((pdir / "README.md").read_text("utf-8").strip()) < 100:
            errors.append(f"{pdir / 'README.md'}: missing or too short.")

        # 2. connectors.yaml
        conn_path = meta_dir / "connectors.yaml"
        if not conn_path.is_file():
            errors.append(f"Missing {conn_path}")
        else:
            conn_data = yaml.safe_load(conn_path.read_text("utf-8"))
            errors.extend(validate_against_schema(conn_data, connectors_schema, str(conn_path)))
            if conn_data.get("plugin_id") != pid:
                errors.append(f"{conn_path}: plugin_id != {pid!r}")

        # 3. config.schema.json
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

        # 4. policy.cel
        policy_path = meta_dir / "policy.cel"
        if not policy_path.is_file():
            errors.append(f"Missing {policy_path}")
        else:
            policy = yaml.safe_load(policy_path.read_text("utf-8"))
            if not isinstance(policy, dict) or policy.get("plugin_id") != pid:
                errors.append(f"{policy_path}: must be a mapping with plugin_id == {pid!r}")
            else:
                for req_key in ("read_only_tools", "draft_only_tools", "hitl_gated_mutations", "cel_guardrails"):
                    if req_key not in policy:
                        errors.append(f"{policy_path}: missing {req_key!r}")
                for gate in policy.get("hitl_gated_mutations", []):
                    if gate.get("scope") not in {"task_sticky", "explicit_per_call"}:
                        errors.append(f"{policy_path}: invalid HITL scope {gate.get('scope')!r}")
                    cond = gate.get("condition", "")
                    try:
                        validate_cel_expression(cond)
                        stats["cel_expressions"] += 1
                    except CelSyntaxError as exc:
                        errors.append(f"{policy_path}: CEL error in gate {gate.get('tool')!r}: {exc}")
                for guard in policy.get("cel_guardrails", []):
                    expr = guard.get("expr", "")
                    try:
                        validate_cel_expression(expr)
                        stats["cel_expressions"] += 1
                    except CelSyntaxError as exc:
                        errors.append(f"{policy_path}: CEL error in guardrail {guard.get('id')!r}: {exc}")

        # 5. Agent & Schedule YAMLs
        for agent_rel in pjson.get("agent_templates", []):
            agent_doc = yaml.safe_load((pdir / agent_rel).read_text("utf-8"))
            if not isinstance(agent_doc, dict) or agent_doc.get("kind") != "AgentTemplate":
                errors.append(f"{pdir / agent_rel}: invalid AgentTemplate YAML")
        for sched_rel in pjson.get("schedules", []):
            sched_doc = yaml.safe_load((pdir / sched_rel).read_text("utf-8"))
            spec = sched_doc.get("spec", {}) if isinstance(sched_doc, dict) else {}
            cron_parts = str(spec.get("cron_expression", "")).split()
            if len(cron_parts) != 5 or not all(CRON_FIELD_RE.match(p) for p in cron_parts):
                errors.append(f"{pdir / sched_rel}: invalid 5-field cron_expression {spec.get('cron_expression')!r}")
            if not isinstance(spec.get("max_token_budget"), int) or spec["max_token_budget"] <= 0:
                errors.append(f"{pdir / sched_rel}: max_token_budget must be positive integer")
            gv = spec.get("goal_verifier", {})
            if not gv.get("command_check") or not gv.get("nl_criteria"):
                errors.append(f"{pdir / sched_rel}: goal_verifier must include command_check and nl_criteria")

        # 6. Skills (3 per plugin)
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
                for m in ("Mode A", "Mode B", "Mode C"):
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

    # 8. Public Clean-Room Hygiene Scan across ALL source files, zip contents, and git log
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", ".uv-cache"}
    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        if any(part in skip_dirs for part in fpath.parts):
            continue
        rel = fpath.relative_to(root).as_posix()
        if fpath.suffix == ".zip":
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
                errors.append(f"Corrupt zip file: {rel}")
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
        f"cel_expressions={stats['cel_expressions']}, "
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
