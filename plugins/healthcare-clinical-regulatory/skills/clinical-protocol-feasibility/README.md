# Clinical Protocol SoA & Enrollment Feasibility (`clinical-protocol-feasibility`)

Cross-checks clinical trial Schedule of Assessments visit windows against primary/secondary endpoints and calculates screen-fail-adjusted enrollment capacity across IRB sites. Deterministic computation executes via [`scripts/soa_endpoint_validator.py`](scripts/soa_endpoint_validator.py). Domain guards enforced: Verifies required_procedures match visits covering target_visit_day; Excludes unapproved IRB sites and applies screen-fail discount. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Clinical Operations / Study Feasibility Lead**: Triggered when auditing Phase II/III Schedule of Assessments (SoA) visits against primary efficacy endpoints; catches missing mandatory visit procedures (`Day-180` biopsy), filters unapproved IRB sites, and models screen-fail adjusted enrollment.
- **Biostatistics & Protocol Design Director**: Triggered when stress-testing site accrual feasibility before locking global trial protocols; quantifies randomized-participant shortfalls (`204 vs 240` target) before site initiation.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`clinical-protocol-feasibility.zip`](../../../../dist/skills/clinical-protocol-feasibility.zip) (or the full department bundle [`healthcare-clinical-regulatory.zip`](../../../../dist/bundles/healthcare-clinical-regulatory.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` + Customer BYO-MCP (`Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/clinical-protocol-feasibility` or `@clinical-protocol-feasibility`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.soa_endpoint_validator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"visits": [{"visit_id": r.get("Custom visit_id"), "procedures": r.get("Custom procedures")} for r in wb["Source_Tab"]], "endpoints": wb["endpoints"], "sites": wb["sites"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/healthcare-clinical-regulatory/skills/clinical-protocol-feasibility/scripts/soa_endpoint_validator.py \
  --input examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx \
  --config plugins/healthcare-clinical-regulatory/skills/clinical-protocol-feasibility/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `soa_endpoint_validator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` + Customer BYO-MCP (`Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`) via `remote_cli mcp`):** "Audit Meridian BioPharma Phase III protocol where Day-180 Visit omits the biopsy required for the Primary Endpoint."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate Drive Site Feasibility Sheet with 40% screen failure rates and 2 sites awaiting IRB approval."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx) and ask: "Cross-check the Phase III Schedule of Assessments against efficacy endpoints and site screen-fail rates in `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` (`APX-ONC-301`) to expose missing mandatory endpoint procedures and enrollment shortfalls."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing oncology protocol **`APX-ONC-301`** (`target_sample_size: 240`) in `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` triggered **`PROTOCOL_AMENDMENT_REQUIRED_PRIMARY_GAP`** after finding **`2 / 2` SoA endpoint assessment gaps** (`EP-PRIMARY` Day 84 missing `ct_scan`; `EP-SEC-PK` Day 18 missing `pk_draw`) plus a **`36`-patient projected enrollment shortfall (`204.0 / 240`, `85.0%`)**.

- **Schedule-to-Endpoint Disconnects (`2/2`):** Primary endpoint (`Day 84`) omits `ct_scan` and secondary PK endpoint (`Day 18`) omits `pk_draw` in the Schedule of Assessments matrix.
- **Accrual Shortfall (`-36` subjects):** Screen-fail adjusted site capacity reaches only `204.0` randomized patients vs. `240` powered target (`0` unapproved IRB sites).
- **Approval Confirmation Prompt:** Amend the Schedule of Assessments and adjust site capacity before progressing protocol or regulatory submissions via your connected safety / regulatory MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx) (`134.2 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Clinical Protocol SoA & Enrollment Feasibility — `APX-ONC-301`

- **Feasibility Status:** `PROTOCOL_AMENDMENT_REQUIRED_PRIMARY_GAP` | **SoA Endpoint Gaps:** 2/2
- **Projected Enrollment:** 204.0 / 240 (85.0% coverage; Shortfall: 36)

## Schedule of Assessments vs Endpoint Conflicts
- `EP-PRIMARY` (PRIMARY Day 84): `MISSING_ENDPOINT_ASSESSMENT` — missing ['ct_scan']
- `EP-SEC-PK` (SECONDARY Day 18): `MISSING_ENDPOINT_ASSESSMENT` — missing ['pk_draw']
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Pharmacovigilance ICSR SLA Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Pharmacovigilance ICSR SLA Watch" on cron `0 7 * * *` (`UTC`) with instruction: "Run the daily pharmacovigilance intake check via scripts/icsr_completeness_checker.py to watch 7-day fatal SUSAR clocks, incomplete 4-criteria cases, and raw PHI alerts."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `protocol_id`, `target_sample_size`, `enrollment_window_months`, `visits`, `endpoints`, `sites`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `visits` requires [`visit_id`; `procedures`] | `endpoints` requires [`endpoint_id`; `required_procedures`] | `sites` requires [`site_id`; `projected_monthly_screened` or `irb_approved`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_enrollment_coverage_pct` | `number` | `100.0` | Minimum projected-vs-target sample enrollment coverage %. |
| `max_screen_fail_warn_pct` | `number` | `35.0` | Site screen failure rate warning threshold %. |

See [`../../README.md`](../../README.md) for the `healthcare-clinical-regulatory` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
