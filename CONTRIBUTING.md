# Contributing to `gemini-agent-plugins`

We welcome new enterprise domain workflows, trap guides, starter baselines, and deterministic computation improvements under the [Apache-2.0 License](LICENSE).

## Authoring Rules

1. **Deterministic Engines Only (No Toy Placeholders):**
   - Every skill script under `skills/<skill-id>/scripts/` must execute cleanly with Python 3.11+ using standard-library modules (`pandas`/`openpyxl` may be used only as optional accelerations).
   - Export `load_config`, `load_payload`, `analyze`, `render_markdown`, and an `argparse` `main` entrypoint supporting `--input`, `--config`, `--format json|markdown`, and `--output`.
   - Zero pass-only stubs, zero `NotImplementedError`, and zero unimplemented markers.

2. **`SKILL.md` Compliance (`tools/skill_validator.py`):**
   - YAML frontmatter requires:
     - `name`: kebab-case `^[a-z0-9-]+$`, max 64 characters, matching its skill directory name.
     - `description`: max 1024 characters, **zero `<` or `>` characters**, and must include both a positive trigger (`Use when...`) and a negative anti-trigger (`Don't use for...`).
     - `created_by: gemini-agent-plugins`
   - Body must document Mode A, Mode B, Mode C degradation, `org_configured` inspection, verbatim standard baseline banner `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`, `pyrepl` + `python3` execution usage, and explicit HITL confirmation gates.
   - Use `view_file` and `write_to_file` when referencing file tools.
   - Every file under `scripts/` and `references/` must have an exact relative Markdown link inside `SKILL.md`, and zero broken links are permitted.

3. **Public Clean-Room Hygiene & Synthetic Test Data:**
   - Never commit proprietary customer names, internal tracking URLs, confidential codenames, or corporate email addresses.
   - Use approved synthetic organizations for all fixtures and examples (`Cymbal Financial`, `Apex Manufacturing`, `Meridian BioPharma`, `Northstar Retail`, `Veloce SuperApp`, `Stratos Telecom`, `CivicFirst Agency`, `Cascade State University`).
   - Run `python3 tools/validate_repo.py` locally to verify clean-room compliance across both workspace files and commit messages.

## Validation & Pull Request Checklist

Before opening a pull request:

1. Update or add source manifests under `plugins/<plugin-id>/` and update `.gemini-agent/catalog.json` if adding plugins/skills.
2. Materialize references and regenerate `dist/` archives:
   ```bash
   python3 tools/package.py
   ```
3. Run the full repository validator and confirm **0 errors, 0 warnings**:
   ```bash
   python3 tools/validate_repo.py
   ```
4. Add unit tests and synthetic fixtures under `tests/` covering edge cases, baseline banner emission vs `--org-config` customization, and run:
   ```bash
   pytest -v
   ```
