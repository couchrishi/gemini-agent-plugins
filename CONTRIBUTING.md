# Contributing to `gemini-agent-plugins`

We welcome new enterprise domain workflows, trap guides, starter baselines, and deterministic computation improvements under the [Apache-2.0 License](LICENSE).

## Authoring Rules

1. **Deterministic Engines Only (No Toy Placeholders):**
   - Every skill script under `skills/<skill-id>/scripts/` must execute cleanly with Python 3.11+ using standard-library modules (`pandas`/`openpyxl` may be used only as optional accelerations).
   - Import `scripts/enterprise_io.py`, export `load_config`, `load_payload`, `analyze`, `render_markdown`, and an `argparse` `main` entrypoint supporting `--input`, `--config`, `--format json|markdown`, and `--output`.
   - Accept normalized Python `payload` dicts, `.xlsx`/`.docx`/`.csv`/`.json` file paths, and empty `0`-row inputs cleanly while failing closed on malformed or incomplete non-empty inputs.
   - Zero pass-only stubs, zero `NotImplementedError`, and zero unimplemented markers.

2. **`SKILL.md` Compliance (`tools/skill_validator.py`):**
   - YAML frontmatter requires:
     - `name`: kebab-case `^[a-z0-9-]+$`, max 64 characters, matching its skill directory name.
     - `description`: max 1024 characters, **zero `<` or `>` characters**, and must include both a positive trigger (`Use when...`) and a negative anti-trigger (`Don't use for...`).
     - `created_by: gemini-agent-plugins`
   - Body must document the 4-step Gemini Enterprise (`/work`) flow:
     1. Live managed 1P / BYO-MCP connector discovery (`remote_cli`) with Workspace/attached file fallback (`view_file`).
     2. Inspecting source shapes in `pyrepl` via `scripts/enterprise_io.py`, shaping messy custom fields into canonical `payload` dicts (`ask_question` only when ambiguous), and calling `analyze(payload, config=...)`.
     3. `org_configured` inspection, verbatim baseline banner `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`, `pyrepl` + `python3` CLI execution.
     4. Agent Gateway (`Auto-Guardian`) + explicit user confirmation write governance, plus optional conversational scheduling via `schedule_task`.
   - Zero deprecated pseudo-config or fictional tool identifiers; use `view_file` and `write_to_file` when referencing file tools.
   - Every file under `scripts/` and `references/` must be cited as an inline backtick code span outside fenced code blocks inside `SKILL.md` (use Markdown links `[text](https://...)` strictly for web URLs).

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
