# Security & Migration PR Readiness Gate (`security-pr-readiness-gate`)

Scans unified pull/merge request diffs and dependency manifests for hardcoded credentials, removed authz decorators, destructive or locking DB migrations, and breaking API route removals. Deterministic computation executes via [`scripts/diff_risk_inspector.py`](scripts/diff_risk_inspector.py). Domain guards enforced: Catches hardcoded credential patterns, removed authz decorators, and destructive DDL; Refuses to merge PRs or run production migrations autonomously. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **AppSec / DevSecOps Reviewer**: Triggered when auditing high-risk authentication, billing, and schema-migration pull requests; detects removed authz decorators, hardcoded credential patterns, and unsafe non-concurrent DDL locks.
- **Staff Backend Engineer**: Triggered when pre-screening release-branch diffs and CVE dependency advisories before merge; blocks unguarded production index locks and unpinned critical CVEs behind explicit approval.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`security-pr-readiness-gate.zip`](../../../../dist/skills/security-pr-readiness-gate.zip) (or the full department bundle [`sdlc-modernization-sre.zip`](../../../../dist/bundles/sdlc-modernization-sre.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/security-pr-readiness-gate` or `@security-pr-readiness-gate`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_json_or_jsonl
from scripts.diff_risk_inspector import analyze, render_markdown

raw = Path("customer_input.txt").read_text(encoding="utf-8")
meta_rows = read_json_or_jsonl(Path("customer_metadata.json"))
payload = {"diff": raw, "dependencies": [{"name": r["Source name"], "version": r["Source version"]} for r in meta_rows]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/sdlc-modernization-sre/skills/security-pr-readiness-gate/scripts/diff_risk_inspector.py \
  --input examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx \
  --config plugins/sdlc-modernization-sre/skills/security-pr-readiness-gate/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `diff_risk_inspector.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack` via `remote_cli mcp`):** "Review PR #412 on Veloce SuperApp's checkout service before I approve and merge it."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Inspect the uploaded diff Doc and dependency table in Engineering Shared Drive for unpinned packages."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx) and ask: "Audit pull request `PR-APX-142`, its dependency advisories, and schema migration diffs in `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` for removed authorization decorators, hardcoded secrets, and blocking DDL locks before merge."

## Sample Response

### What You See in Gemini Enterprise Chat

Security and migration review on **`PR-APX-142`** in `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` **failed release readiness (`pr_gate_passed: False`)**, identifying **`1` CRITICAL hardcoded secret**, **`1` CRITICAL removed `@require_auth` decorator**, **`1` blocking non-concurrent DDL index lock**, and **`2` dependency risks**.

- **CRITICAL Blockers (`app/settlement_api.py`):** Hardcoded secret assignment at line `4` (`hardcoded_secret_assign`) and removal of authorization guard `@require_auth` at line `3` require immediate revert.
- **Migration & Dependency Risks:** Non-concurrent `CREATE INDEX` (line `5`) risks production table locking alongside `2` flagged package dependency findings.
- **Approval Confirmation Prompt:** Merge and DDL execution are held (`pr_gate_passed: False`); remediate `app/settlement_api.py` first before requesting human authorization via your connected `GitHub` connector (gated by `Auto-Guardian`) or an authorized DDL migration tool after remediation.

### Verified Deterministic Engine Output

Executed directly against [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx) (`149.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Security & Migration PR Readiness Gate (PR-APX-142)

- **Gate Passed:** `False`
- **Secrets:** 1 | **Removed Authz:** 1 | **Migration Risks:** 1
- **Breaking API Routes:** 0 | **Dependency Risks:** 2

- **CRITICAL Secret (`hardcoded_secret_assign`)** at `app/settlement_api.py:4`
- **CRITICAL Removed Authz** at `app/settlement_api.py:3`: `@require_auth`
- **MEDIUM Migration Risk** at `app/settlement_api.py:5`: Blocking CREATE INDEX without CONCURRENTLY
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly SRE SLO & Postmortem Review` routine via `schedule_task`:

```text
Schedule recurring job "Weekly SRE SLO & Postmortem Review" on cron `0 9 * * 1` (`UTC`) with instruction: "Run the weekly SRE reliability and postmortem action-item SLA audit via scripts/slo_timeline_calculator.py. Compute 30-day error-budget consumption across P1/P2 incidents, report TTD/TTM/TTR trends, and flag overdue postmortem corrective actions without mutating Jira issues autonomously."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `pr_id`, `diff`, `dependencies`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** top-level `diff` text | `dependencies` requires [`name` or `package`; `version` or `source_url`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `organization_name` | `string` | `"Standard Industry Baseline"` | Organization label stamped into JSON/Markdown reports when bound |

See [`../../README.md`](../../README.md) for the `sdlc-modernization-sre` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
