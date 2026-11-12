# Grant Budget Allowability & Accreditation Pack (`grant-accreditation-evidence-pack`)

Audits university and public research grant budgets against F&A indirect rate caps, unallowable cost categories, cost-share match ratios, 100% PI effort caps, and accreditation evidence freshness. Deterministic computation executes via [`scripts/grant_accreditation_validator.py`](scripts/grant_accreditation_validator.py). Domain guards enforced: Excludes mtdc_exempt items from F&A ceiling calculation accurately; Catches >100% combined PI effort, unallowables, and stale artifacts. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Sponsored Research / University Grants Controller**: Triggered when validating federal/institutional grant budgets before submission or audit drawdowns; excludes unallowable lobbying and capital equipment from Modified Total Direct Cost (MTDC) prior to `26%/52%` F&A cap math, catching `115%` PI effort overcaps.
- **Accreditation & Academic Compliance Director**: Triggered when auditing institutional accreditation evidence packets for missing or expired (`>365d`) artifacts; verifies matching cost-share compliance and document freshness prior to peer-review submission.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`grant-accreditation-evidence-pack.zip`](../../../../dist/skills/grant-accreditation-evidence-pack.zip) (or the full department bundle [`public-sector-higher-ed.zip`](../../../../dist/bundles/public-sector-higher-ed.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` + Customer BYO-MCP (`Grants Management & Procurement Portal MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/grant-accreditation-evidence-pack` or `@grant-accreditation-evidence-pack`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.grant_accreditation_validator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"budget_lines": [{"line_id": r.get("Custom line_id"), "category": r.get("Custom category"), "amount_usd": r.get("Custom amount_usd")} for r in wb["Source_Tab"]], "pi_effort_allocations": wb["pi_effort_allocations"], "accreditation_artifacts": wb["accreditation_artifacts"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/public-sector-higher-ed/skills/grant-accreditation-evidence-pack/scripts/grant_accreditation_validator.py \
  --input examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx \
  --config plugins/public-sector-higher-ed/skills/grant-accreditation-evidence-pack/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `grant_accreditation_validator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` + Customer BYO-MCP (`Grants Management & Procurement Portal MCP server`) via `remote_cli mcp`):** "Audit Cascade State University grant packet with $4k lobbying line, excess F&A above 52% MTDC, and 115% PI effort."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Verify Accreditation Evidence Folder Sheet in Drive with 420-day-old lab safety certification."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx) and ask: "Audit the sponsored research grant budget, PI effort allocations, and accreditation evidence binder in `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`CSU-BIO-440`) to exclude unallowable lobbying/equipment from MTDC, check `26%/52%` F&A indirect caps, and flag expired compliance docs (>365 days)."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing grant and accreditation packet **`CSU-BIO-440`** in `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` **blocked submission (`BLOCKED_REMEDIATE_BEFORE_SUBMISSION`) with `5` compliance blockers**: **`$8,500.00` unallowable lobbying (`ADV-LOB`)**, **excess F&A indirect request (`$52,000.00` vs. `$36,400.00` cap at `26.0%` of `$140,000.00` MTDC)**, **`4.0%` vs `10.0%` cost-share shortfall (`$12,000.00`)**, **`115.0%` PI effort over-allocation (`Dr. Aris Chen`)**, and **`678`-day stale biosafety proof (`BSL2-BIOSAFE`)**.

- **Budget & F&A Violations (`3`):** Excludes `$8,500.00` unallowable lobbying from MTDC, flags `$15,600.00` excessive F&A indirect charge above the `$36,400.00` `26%` cap, and surfaces a `$12,000.00` cost-share deficit (`4.0% < 10.0%`).
- **Compliance & Effort Hard Stops (`2`):** Caps PI effort (`Dr. Aris Chen` at `115.0% > 100%`) and holds expired `BSL2-BIOSAFE` evidence (`678d > 365d` threshold).
- **Approval Confirmation Prompt:** Sponsor submission via your connected grants MCP server is blocked while `blocker_count > 0`; remediate all `5` budget/effort/evidence blockers first before confirming submission.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx) (`136.6 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Grant Budget Compliance & Accreditation Evidence Audit (`CSU-BIO-440`)

- **Readiness:** `BLOCKED_REMEDIATE_BEFORE_SUBMISSION` | **Blockers:** 5 | **MTDC Base:** $140,000.00 | **Indirect Requested vs Allowed:** $52,000.00 / $36,400.00

| Scope | ID | Issue | Amount / Metric |
| :--- | :--- | :--- | ---: |
| Budget | `ADV-LOB` | UNALLOWABLE_COST_CATEGORY (lobbying) | $8,500.00 |
| Budget | `INDIRECT_FA_ROLLUP` | FA_CAP_EXCEEDED ($52,000.00 > $36,400.00 @ 26.0% MTDC) | $15,600.00 |
| Budget | `COST_SHARE_MATCH` | COST_SHARE_SHORTFALL (4.0% < 10.0% required) | $12,000.00 |
| PI Effort | Dr. Aris Chen | PI_OVERALLOCATED_GT_100_PCT | 115.0% |
| Evidence | `BSL2-BIOSAFE` | STALE_EVIDENCE (678d > 365d) | 678d |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Grant & Accreditation Evidence Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Grant & Accreditation Evidence Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly sponsored grant allowability and accreditation artifact freshness check via scripts/grant_accreditation_validator.py across active institutional packets."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `grant_id`, `required_cost_share_pct`, `budget_lines`, `pi_effort_allocations`, `accreditation_artifacts`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `budget_lines` requires [`line_id`; `category`; `amount_usd`] | `pi_effort_allocations` requires [`pi_name`; `proposed_effort_pct`] | `accreditation_artifacts` requires [`artifact_id`; `status`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_indirect_fa_rate_pct` | `number` | `52.0` | University/agency negotiated F&A indirect cost ceiling % on MTDC base. |
| `max_evidence_age_days` | `integer` | `365` | Maximum allowed age in days for accreditation evidence artifacts. |

See [`../../README.md`](../../README.md) for the `public-sector-higher-ed` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
