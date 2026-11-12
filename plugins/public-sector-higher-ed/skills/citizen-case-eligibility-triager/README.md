# Citizen Benefits Eligibility & Cure Triager (`citizen-case-eligibility-triager`)

Evaluates citizen benefits eligibility against household FPL multipliers, enforces mandatory missing-document cure notices rather than automated denials, and flags raw SSN PII. Deterministic computation executes via [`scripts/statutory_eligibility_engine.py`](scripts/statutory_eligibility_engine.py). Domain guards enforced: Routes missing document packets strictly to PENDING_VERIFICATION_CURE_NOTICE; Detects and counts SSN patterns in applicant notes without echoing them. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Public Benefits Eligibility Supervisor**: Triggered when auditing citizen assistance intake packets against Federal Poverty Level (`200% FPL`) statutes; routes missing-document cases strictly to `PENDING_CURE_NOTICE` (`15d` cure window, never premature denial) and counts unredacted SSNs.
- **Agency Due-Process Compliance Officer**: Triggered when ensuring intake triage notes protect PII while adhering to statutory notice timelines; blocks improper case denials and flags raw SSN disclosures before constituent correspondence.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`citizen-case-eligibility-triager.zip`](../../../../dist/skills/citizen-case-eligibility-triager.zip) (or the full department bundle [`public-sector-higher-ed.zip`](../../../../dist/bundles/public-sector-higher-ed.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` + Customer BYO-MCP (`Grants Management & Procurement Portal MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/citizen-case-eligibility-triager` or `@citizen-case-eligibility-triager`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.statutory_eligibility_engine import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"cases": [{"case_id": r.get("Custom case_id"), "household_size": r.get("Custom household_size"), "annual_household_income_usd": r.get("Custom annual_household_income_usd")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/public-sector-higher-ed/skills/citizen-case-eligibility-triager/scripts/statutory_eligibility_engine.py \
  --input examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx \
  --config plugins/public-sector-higher-ed/skills/citizen-case-eligibility-triager/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `statutory_eligibility_engine.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` + Customer BYO-MCP (`Grants Management & Procurement Portal MCP server`) via `remote_cli mcp`):** "Triage CivicFirst Agency household-of-4 packet missing proof_of_income with an SSN in free-text notes."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Intake Case Sheet in Drive with eligible household under 200% FPL and over-income case."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx) and ask: "Triage the citizen benefit eligibility packets in `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` against `200% FPL` income thresholds, enforcing statutory 15-day cure notices instead of denials when income verification docs are missing and checking for raw SSN disclosures."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `2` household intake packets in `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`0` unredacted SSN leaks, `0` improper denials) **classified `CIV-APX-402` (`$31,000` for HH size `2`, `151.7%` FPL <= `$40,880`) as `ELIGIBLE_RECOMMEND_AWARD`** and **routed `CIV-APX-401` (`$42,000` for HH size `4`) to a `15`-day `PENDING_VERIFICATION_CURE_NOTICE`** because `proof_of_income` is missing.

- **Due-Process Cure Protection (`CIV-APX-401`):** Household income (`$42,000`) sits well under the `$62,400` (`200%` FPL) cap; rather than rejecting due to missing `proof_of_income`, policy triggers a mandatory `15`-day cure notice.
- **Verified Award Packet (`CIV-APX-402`):** Complete documents and verified `$31,000` income (`151.7%` FPL) qualify for award.
- **Approval Confirmation Prompt:** Confirm licensed caseworker authorization before issuing the award decision for `CIV-APX-402` or mailing the 15-day cure notice for `CIV-APX-401` via your connected case management MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx) (`138.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Statutory Case Eligibility & Document Completeness Triage

- **Cases:** 2 | **Eligible:** 1 | **Pending Cure Notice:** 1 | **Recommended Denials (HITL):** 0 | **PII Tokens Redacted:** 0

| Case | HH Size | Income | Max Threshold | Missing Docs | Determination | Rationale |
| :--- | ---: | ---: | ---: | :--- | :--- | :--- |
| `CIV-APX-401` | 4 | $42,000 | $62,400 | proof_of_income | `PENDING_VERIFICATION_CURE_NOTICE` | Missing mandatory document(s) (proof_of_income); issue 15-day cure notice. |
| `CIV-APX-402` | 2 | $31,000 | $40,880 | None | `ELIGIBLE_RECOMMEND_AWARD` | Verified household income $31,000 (151.7% FPL) <= 200% threshold $40,880. |

Final award or adverse action notices require licensed caseworker HITL approval.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Grant & Accreditation Evidence Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Grant & Accreditation Evidence Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly sponsored grant allowability and accreditation artifact freshness check via scripts/grant_accreditation_validator.py across active institutional packets."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `cases`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `cases` requires [`case_id`; `household_size`; `annual_household_income_usd` or `annual_income_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `base_fpl_single_usd` | `number` | `15060.0` | 100% Federal Poverty Level annual income baseline for single household. |
| `eligibility_fpl_multiplier` | `number` | `2.0` | FPL income threshold multiplier for statutory program qualification. |
| `statutory_cure_window_days` | `integer` | `15` | Statutory notice window in days to cure missing application documents. |

See [`../../README.md`](../../README.md) for the `public-sector-higher-ed` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
