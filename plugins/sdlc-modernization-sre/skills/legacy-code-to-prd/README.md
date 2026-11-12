# Legacy Code to PRD & Traceability Matrix (`legacy-code-to-prd`)

Parses legacy codebase inventories for entrypoints, SQL read/write table couplings, cyclomatic complexity hotspots, and requirement-to-test traceability coverage. Deterministic computation executes via [`scripts/spec_traceability_matrix.py`](scripts/spec_traceability_matrix.py). Domain guards enforced: Separates DB reads vs writes and detects cyclomatic complexity hotspots; Flags untested critical requirements explicitly. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Principal Modernization Architect**: Triggered when decomposing monolithic services and database tables into target microservices; identifies cyclomatic-complexity hotspots (`>=15`), maps DB ownership, and checks PRD test traceability (`>=85%`).
- **Engineering Delivery Manager**: Triggered when scoping regression test backlog before cutting legacy traffic over; highlights uncovered functional requirements before scheduling migration cutover.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`legacy-code-to-prd.zip`](../../../../dist/skills/legacy-code-to-prd.zip) (or the full department bundle [`sdlc-modernization-sre.zip`](../../../../dist/bundles/sdlc-modernization-sre.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/legacy-code-to-prd` or `@legacy-code-to-prd`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.spec_traceability_matrix import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"modules": [{"path": r.get("Custom path"), "source": r.get("Custom source")} for r in wb["Source_Tab"]], "requirements": wb["requirements"], "tests": wb["tests"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/sdlc-modernization-sre/skills/legacy-code-to-prd/scripts/spec_traceability_matrix.py \
  --input examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx \
  --config plugins/sdlc-modernization-sre/skills/legacy-code-to-prd/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `spec_traceability_matrix.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack` via `remote_cli mcp`):** "Parse Cymbal Financial's legacy settlement service modules in GitHub and extract DB couplings and complexity hotspots."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Read our Legacy Inventory Sheet in Drive and generate a PRD traceability report."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx) and ask: "Inspect the legacy codebase modules, database ownership map, and PRD requirements in `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` to isolate complexity hotspots, table couplings, and untested requirements before opening Jira workstreams."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing `2` codebase modules and `3` PRD requirements in `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` surfaced **`1` complexity hotspot (`src/billing/settlement_sync.py`, cyclomatic complexity `24`) coupled to `3` DB tables** and **`66.67%` PRD test traceability (`2 / 3` covered, `traceability_gate_passed: False`)**.

- **Coupling Hotspot:** `src/billing/settlement_sync.py` (complexity `24`) both reads `prod_retail.invoices` and writes `prod_retail.gl_clearing_ledger`, blocking safe cutover without decoupled read/write contracts.
- **Coverage Shortfall:** Only `2` of `3` PRD requirements (`66.67%`) carry linked verification tests (`<85%` threshold); `src/auth/token_verifier.py` stays cleanly below complexity limits (`8`).
- **Approval Confirmation Prompt:** Confirm if you would like to create Jira modernization/testing remediation tickets for the `1` uncovered requirement via your connected `Jira` connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx) (`148.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Legacy Code-to-PRD Traceability & Coupling Matrix

- **Modules Parsed:** 2 | **Complexity Hotspots:** 1 | **DB Tables Coupled:** 3
- **Traceability Coverage:** 66.67% (2/3) | **Gate Passed:** `False`

| Module | Complexity | Hotspot | Entrypoints | DB Reads | DB Writes |
| :--- | ---: | :---: | ---: | :--- | :--- |
| `src/billing/settlement_sync.py` | 24 | `True` | 1 | prod_retail.invoices | prod_retail.gl_clearing_ledger |
| `src/auth/token_verifier.py` | 8 | `False` | 1 | prod_iam.sessions | — |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly SRE SLO & Postmortem Review` routine via `schedule_task`:

```text
Schedule recurring job "Weekly SRE SLO & Postmortem Review" on cron `0 9 * * 1` (`UTC`) with instruction: "Run the weekly SRE reliability and postmortem action-item SLA audit via scripts/slo_timeline_calculator.py. Compute 30-day error-budget consumption across P1/P2 incidents, report TTD/TTM/TTR trends, and flag overdue postmortem corrective actions without mutating Jira issues autonomously."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `modules`, `requirements`, `tests`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `modules` requires [`path` or `module`; `source` or `entrypoints` or `cyclomatic_complexity`] | `requirements` requires [`req_id` or `title`] | `tests` requires [`test_id`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `complexity_hotspot_threshold` | `integer` | `15` | Cyclomatic complexity score flagging legacy modernization hotspots. |
| `min_requirement_traceability_pct` | `number` | `85.0` | Minimum percentage of extracted requirements covered by verified test cases. |

See [`../../README.md`](../../README.md) for the `sdlc-modernization-sre` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
