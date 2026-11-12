#!/usr/bin/env python3
"""Validator for Gemini Agent SKILL.md manifests and packaged skill/bundle archives."""

from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import posixpath
import re
import sys
import zipfile
import zlib
from pathlib import Path
from typing import Iterable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - stdlib fallback only used if PyYAML missing
    yaml = None

KEBAB_RE = re.compile(r"^[a-z0-9-]+$")
FENCED_CODE_RE = re.compile(
    r"^[ \t]*(`{3,}|~{3,})[\s\S]*?^[ \t]*\1[ \t]*$", re.MULTILINE
)
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1)[^\n])+\1")
INLINE_CODE_CAPTURE_RE = re.compile(r"`([^`\n]+)`")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\n]*)\)")
WEB_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
FORBIDDEN_TOOL_NAME = "file" + "_edit"
PLACEHOLDER_TODO = "[" + "todo]"
PLACEHOLDER_TILDE = "~" * 2
_CEL_WORD_RE = re.compile(r"\b" + "C" + "EL" + r"\b")
_FAKE_ACTION_RE = re.compile(
    r"\b(?:sap_post_|sap_read_|sap_award_|sap_create_|sap_execute_|erp_update_|erp_post_|servicenow_table_|salesforce_soql_|bigquery_query_)[a-z0-9_]+\b"
)
# Zlib+base64 encoded list of legacy pseudo-config/three-mode markers and deprecated placeholder tool names
_BANNED_TOKENS_ZLIB_B64 = (
    "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"
)
_BANNED_TOKEN_CACHE: tuple[str, ...] | None = None


def _get_banned_tokens() -> tuple[str, ...]:
    global _BANNED_TOKEN_CACHE
    if _BANNED_TOKEN_CACHE is None:
        raw = zlib.decompress(base64.b64decode(_BANNED_TOKENS_ZLIB_B64)).decode("utf-8")
        _BANNED_TOKEN_CACHE = tuple(json.loads(raw))
    return _BANNED_TOKEN_CACHE


@dataclasses.dataclass(frozen=True)
class ValidationIssue:
    level: str  # "ERROR" | "WARNING"
    location: str
    message: str

    def format(self) -> str:
        return f"[{self.level}] {self.location}: {self.message}"


def _parse_yaml_frontmatter(raw_yaml: str) -> dict:
    if yaml is not None:
        loaded = yaml.safe_load(raw_yaml)
        if not isinstance(loaded, dict):
            raise ValueError("Frontmatter YAML must parse to a mapping/dict.")
        return loaded

    # Minimal deterministic YAML key: scalar fallback when PyYAML is unavailable.
    data: dict[str, str] = {}
    for line in raw_yaml.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(f"Invalid frontmatter line: {line!r}")
        key, val = stripped.split(":", 1)
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        data[key.strip()] = val
    return data


def _strip_code_spans(markdown_text: str) -> str:
    without_fences = FENCED_CODE_RE.sub("", markdown_text)
    return INLINE_CODE_RE.sub("code", without_fences)


def _check_markdown_links(body: str) -> str:
    """Verify that markdown links in body are only used for web links (http:// or https://)."""
    cleaned = _strip_code_spans(body)
    for match in MD_LINK_RE.finditer(cleaned):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")].strip()
        else:
            target = raw_target.split()[0] if raw_target else ""
        if not WEB_URL_RE.match(target):
            return (
                f"SKILL.md body contains non-web markdown link target '{target}'."
                " Markdown links may only be used for web links (http:// or"
                " https://); format skill files and paths as code strings instead"
                " (e.g. `scripts/foo.py`)."
            )
    return ""


def extract_relative_links(markdown_text: str) -> list[str]:
    """Return normalized relative file targets referenced by Markdown links outside code blocks."""
    cleaned = _strip_code_spans(markdown_text)
    targets: list[str] = []
    for match in MD_LINK_RE.finditer(cleaned):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")].strip()
        else:
            target = raw_target.split()[0] if raw_target else ""
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_no_frag = target.split("#", 1)[0]
        if target_no_frag:
            targets.append(target_no_frag)
    return targets


def extract_code_path_references(markdown_text: str) -> list[str]:
    """Return skill-relative file paths formatted as inline code spans outside fenced code blocks."""
    without_fences = FENCED_CODE_RE.sub("", markdown_text)
    targets: list[str] = []
    for code_text in INLINE_CODE_CAPTURE_RE.findall(without_fences):
        candidate = code_text.strip()
        if (
            candidate.startswith(("scripts/", "references/"))
            and " " not in candidate
            and "*" not in candidate
        ):
            targets.append(candidate)
    return targets


def validate_skill_content(
    skill_md_text: str,
    file_inventory: Iterable[str],
    expected_name: str | None = None,
    *,
    location: str = "SKILL.md",
    is_bundle: bool = False,
    extra_markdown_files: dict[str, str] | None = None,
) -> list[ValidationIssue]:
    """Validate a SKILL.md string and its file inventory against Gemini Agent constraints."""
    issues: list[ValidationIssue] = []
    text = skill_md_text.replace("\r\n", "\n")
    inventory = {posixpath.normpath(p) for p in file_inventory}

    if not text.startswith("---\n"):
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md must start with '---' YAML frontmatter.")
        )
        return issues

    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md frontmatter is missing closing '---'.")
        )
        return issues

    raw_frontmatter = text[4:end_idx]
    body = text[end_idx + 5 :]

    try:
        meta = _parse_yaml_frontmatter(raw_frontmatter)
    except Exception as exc:  # noqa: BLE001
        issues.append(ValidationIssue("ERROR", location, f"Invalid YAML frontmatter: {exc}"))
        return issues

    # 1. Validate `name`
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        issues.append(ValidationIssue("ERROR", location, "Frontmatter 'name' must be a non-empty string."))
    else:
        if len(name) > 64:
            issues.append(
                ValidationIssue("ERROR", location, f"Frontmatter 'name' exceeds 64 chars ({len(name)}).")
            )
        if not KEBAB_RE.match(name):
            issues.append(
                ValidationIssue("ERROR", location, f"Frontmatter 'name' ({name!r}) must match ^[a-z0-9-]+$.")
            )
        if expected_name and name != expected_name:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    f"Frontmatter 'name' ({name!r}) does not match expected slug ({expected_name!r}).",
                )
            )

    # 2. Validate `description`
    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        issues.append(
            ValidationIssue("ERROR", location, "Frontmatter 'description' must be a non-empty string.")
        )
    else:
        if len(desc) > 1024:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    f"Frontmatter 'description' exceeds 1024 chars ({len(desc)}).",
                )
            )
        if "<" in desc or ">" in desc:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    "Frontmatter 'description' must not contain '<' or '>' characters.",
                )
            )
        if PLACEHOLDER_TODO in desc.lower() or PLACEHOLDER_TILDE in desc:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    "Frontmatter 'description' contains forbidden placeholder tokens.",
                )
            )
        desc_lower = desc.lower()
        if "use when" not in desc_lower:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    "Frontmatter 'description' must include a positive trigger ('Use when...').",
                )
            )
        if "don't use for" not in desc_lower and "do not use for" not in desc_lower:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    "Frontmatter 'description' must include a negative anti-trigger ('Don't use for...').",
                )
            )

    # 3. Validate `created_by`
    if meta.get("created_by") != "gemini-agent-plugins":
        issues.append(
            ValidationIssue(
                "ERROR",
                location,
                "Frontmatter 'created_by' must be 'gemini-agent-plugins'.",
            )
        )

    # 4. Validate body content
    if len(body.strip()) < 200:
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md body is empty or too short (< 200 chars).")
        )
    if PLACEHOLDER_TODO in body.lower() or PLACEHOLDER_TILDE in body:
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md body contains placeholder markers.")
        )
    if FORBIDDEN_TOOL_NAME in text:
        issues.append(
            ValidationIssue(
                "ERROR",
                location,
                f"SKILL.md references forbidden tool name '{FORBIDDEN_TOOL_NAME}'; use 'write_to_file' / 'view_file'.",
            )
        )

    required_markers = [
        ("remote_cli", "/work connector CLI lookup pattern (remote_cli)"),
        ("analyze(", "deterministic Python analyze() entry point"),
        ("payload", "canonical Python payload dict pattern"),
        ("ask_question", "ambiguity disambiguation gate (ask_question)"),
        ("org_configured", "org_configured check instruction"),
        (
            "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]",
            "mandatory starter baseline stamp",
        ),
        ("pyrepl", "persistent Python RAM execution pattern (pyrepl)"),
        ("python3", "CLI fallback pattern (python3)"),
        ("schedule_task", "conversational scheduling contract (schedule_task)"),
    ]
    for marker, label in required_markers:
        if marker not in body:
            issues.append(
                ValidationIssue("ERROR", location, f"SKILL.md body is missing required {label}: {marker!r}.")
            )

    if "auto-guardian" not in body.lower():
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md body must document Agent Gateway (Auto-Guardian) governance.")
        )

    if not any(tok in body.lower() for tok in ("explicit user confirmation", "explicit confirmation")):
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md body must specify explicit user confirmation gate.")
        )

    banned_hits = [tok for tok in _get_banned_tokens() if tok in text]
    if _CEL_WORD_RE.search(text):
        banned_hits.append("deprecated-rule-engine-acronym")
    m_fake = _FAKE_ACTION_RE.search(text)
    if m_fake:
        banned_hits.append(m_fake.group(0))
    if banned_hits:
        issues.append(
            ValidationIssue(
                "ERROR",
                location,
                f"SKILL.md references forbidden legacy or pseudo-tool identifier(s): {banned_hits[:5]}.",
            )
        )

    # 5. Enforce web-only markdown links and code-path completeness bijection
    link_error = _check_markdown_links(body)
    if link_error:
        issues.append(ValidationIssue("ERROR", location, link_error))

    code_paths = extract_code_path_references(body)
    referenced_paths: set[str] = set()
    for target in code_paths:
        norm = posixpath.normpath(target)
        if norm.startswith("..") or norm.startswith("/"):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    f"Skill code path {target!r} escapes skill root directory.",
                )
            )
            continue
        if norm not in inventory:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    f"Broken skill path reference in SKILL.md: {target!r} -> {norm!r} not found in package.",
                )
            )
        else:
            referenced_paths.add(norm)

    managed_files = sorted(
        p
        for p in inventory
        if (p.startswith("scripts/") or p.startswith("references/"))
        and "__pycache__" not in p.split("/")
        and not p.endswith(".pyc")
    )
    if not managed_files:
        issues.append(
            ValidationIssue(
                "ERROR",
                location,
                "Skill/bundle must contain scripts/ and references/ files.",
            )
        )
    for rel_file in managed_files:
        if rel_file not in referenced_paths:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    f"Unreferenced resource in skill package: {rel_file!r} must be explicitly formatted as a code path in SKILL.md.",
                )
            )

    if is_bundle:
        workflow_files = [p for p in managed_files if p.startswith("references/workflows/")]
        if len(workflow_files) != 3:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    location,
                    f"Department bundle must contain 3 workflow files under references/workflows/, found {len(workflow_files)}.",
                )
            )

    # 6. Validate links and code paths inside extra markdown files (e.g., references/workflows/*.md in bundles)
    if extra_markdown_files:
        for md_rel, md_content in sorted(extra_markdown_files.items()):
            md_dir = posixpath.dirname(md_rel)
            for target in extract_relative_links(md_content):
                resolved = posixpath.normpath(posixpath.join(md_dir, target))
                if resolved.startswith("..") or resolved not in inventory:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            f"{location}::{md_rel}",
                            f"Broken relative link {target!r} (resolved to {resolved!r}).",
                        )
                    )
            for target in extract_code_path_references(md_content):
                norm = posixpath.normpath(target)
                if norm.startswith("..") or norm not in inventory:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            f"{location}::{md_rel}",
                            f"Broken skill path reference {target!r} (resolved to {norm!r}).",
                        )
                    )

    return issues


def validate_skill_dir(
    skill_dir: Path,
    expected_name: str | None = None,
    *,
    is_bundle: bool = False,
) -> list[ValidationIssue]:
    """Validate an unpacked skill directory on disk."""
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.is_file():
        return [ValidationIssue("ERROR", str(skill_dir), "Missing SKILL.md at root of skill directory.")]

    inventory: set[str] = set()
    for item in skill_dir.rglob("*"):
        if item.is_file():
            rel = item.relative_to(skill_dir).as_posix()
            if "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
                continue
            inventory.add(rel)

    return validate_skill_content(
        skill_md_path.read_text(encoding="utf-8"),
        inventory,
        expected_name=expected_name or skill_dir.name,
        location=str(skill_md_path),
        is_bundle=is_bundle,
    )


def validate_skill_zip(
    zip_path: Path,
    expected_name: str | None = None,
    *,
    is_bundle: bool = False,
) -> list[ValidationIssue]:
    """Validate a packaged skill or bundle .zip archive."""
    if not zip_path.is_file():
        return [ValidationIssue("ERROR", str(zip_path), "Zip archive does not exist.")]

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [info.filename for info in zf.infolist() if not info.is_dir()]
            if "SKILL.md" not in names:
                return [
                    ValidationIssue(
                        "ERROR",
                        str(zip_path),
                        "Missing root SKILL.md inside zip archive.",
                    )
                ]
            skill_md_text = zf.read("SKILL.md").decode("utf-8")
            extra_md: dict[str, str] = {}
            for name in names:
                if name.startswith("references/workflows/") and name.endswith(".md"):
                    extra_md[name] = zf.read(name).decode("utf-8")
    except (zipfile.BadZipFile, UnicodeDecodeError) as exc:
        return [ValidationIssue("ERROR", str(zip_path), f"Corrupt or non-UTF8 zip archive: {exc}")]

    return validate_skill_content(
        skill_md_text,
        names,
        expected_name=expected_name or zip_path.stem,
        location=str(zip_path),
        is_bundle=is_bundle,
        extra_markdown_files=extra_md,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Gemini Agent SKILL.md directory or zip archive.")
    parser.add_argument("target", type=Path, help="Path to skill directory or .zip archive")
    parser.add_argument("--expected-name", help="Expected skill/bundle kebab-case slug")
    parser.add_argument("--bundle", action="store_true", help="Validate as a 3-skill department router bundle")
    args = parser.parse_args(argv)

    target: Path = args.target
    if target.suffix == ".zip":
        issues = validate_skill_zip(target, expected_name=args.expected_name, is_bundle=args.bundle)
    else:
        issues = validate_skill_dir(target, expected_name=args.expected_name, is_bundle=args.bundle)

    if issues:
        for issue in issues:
            print(issue.format(), file=sys.stderr)
        return 1
    print(f"OK: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
