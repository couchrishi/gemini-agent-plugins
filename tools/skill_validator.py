#!/usr/bin/env python3
"""Validator for Gemini Agent SKILL.md manifests and packaged skill/bundle archives."""

from __future__ import annotations

import argparse
import dataclasses
import posixpath
import re
import sys
import zipfile
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
        ("Mode A", "3-mode degradation guide (Mode A)"),
        ("Mode B", "3-mode degradation guide (Mode B)"),
        ("Mode C", "3-mode degradation guide (Mode C)"),
        ("org_configured", "org_configured check instruction"),
        (
            "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]",
            "mandatory starter baseline stamp",
        ),
        ("pyrepl", "persistent Python RAM execution pattern (pyrepl)"),
        ("python3", "CLI fallback pattern (python3)"),
    ]
    for marker, label in required_markers:
        if marker not in body:
            issues.append(
                ValidationIssue("ERROR", location, f"SKILL.md body is missing required {label}: {marker!r}.")
            )

    if not any(tok in body.lower() for tok in ("hitl", "explicit user confirmation", "explicit confirmation")):
        issues.append(
            ValidationIssue("ERROR", location, "SKILL.md body must specify HITL confirmation gate.")
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
