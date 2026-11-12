# CSAT & NPS Verbatim Churn Signal Miner (`csat-churn-signal-miner`)

Quantifies CSAT/NPS survey driver themes weighted by detractor ARR while keeping unrated null responses out of rating denominators and alerting on churn-intent verbatims. Deterministic computation executes via [`scripts/verbatim_driver_quantifier.py`](scripts/verbatim_driver_quantifier.py). Domain guards enforced: Excludes null ratings from avg_csat and NPS denominators cleanly; Weights driver_pareto by detractor ARR and flags churn phrases. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Voice of Customer (VoC) & CX Lead**: Triggered when auditing high blended CSAT averages (`4.99`) that hide high-ARR cancellation risk; filters unrated surveys safely, pairs quantitative CSAT/NPS (`<=2` / `<=6`) with verbatim churn intent, and flags executive save targets.
- **Customer Retention Strategist**: Triggered when identifying thematic product friction drivers before renewal outreach; quantifies weighted ARR churn exposure behind promoter-skewed averages.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`csat-churn-signal-miner.zip`](../../../../dist/skills/csat-churn-signal-miner.zip) (or the full department bundle [`customer-operations-escalation.zip`](../../../../dist/bundles/customer-operations-escalation.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/csat-churn-signal-miner` or `@csat-churn-signal-miner`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.verbatim_driver_quantifier import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"responses": [{"response_id": r.get("Custom response_id"), "csat_score": r.get("Custom csat_score")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/customer-operations-escalation/skills/csat-churn-signal-miner/scripts/verbatim_driver_quantifier.py \
  --input examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx \
  --config plugins/customer-operations-escalation/skills/csat-churn-signal-miner/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `verbatim_driver_quantifier.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack` via `remote_cli mcp`):** "Analyze Veloce SuperApp CSAT responses where 2 of 6 rows omitted csat_score."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Quantify latency vs support responsiveness ARR exposure in Drive CSAT Sheet."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx) and ask: "Analyze the customer survey scores and verbatim comments in `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`—filtering unrated blanks safely—to expose detractor churn intent and ARR exposure by root-cause theme."

## Sample Response

### What You See in Gemini Enterprise Chat

Mining `3` rated CSAT/NPS survey verbatims in `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` (`0` unrated excluded) surfaced **`2.67` average CSAT, `-33.3` NPS, and `1` explicit churn cancellation alert exposing `$1,420,000.00` ARR**, led by `latency_reliability` and `security_compliance` drivers (`$2,100,000.00` ARR each).

- **Top Detractor Themes (`$2,100,000.00` Exposed ARR each):** `latency_reliability` (`2/2` detractors) and `security_compliance` (`2/2` detractors) outrank `billing_pricing` and `missing_product_feature` (`$1,420,000.00` each).
- **Explicit Save Alert:** `$1,420,000.00` ARR carries explicit verbatim churn wording requiring immediate account intervention despite any positive aggregate score averages.
- **Approval Confirmation Prompt:** Confirm if you would like to escalate the `$1,420,000.00` ARR churn-alert account to executive support review via your connected `ServiceNow` or `Slack` escalation connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx) (`132.9 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# CSAT/NPS Verbatim Driver & Churn Signal Report

- **Responses:** 3 (Rated CSAT: 3, Null Excluded: 0) | **Avg CSAT:** 2.67 | **NPS:** -33.3
- **Explicit Churn Alerts:** 1 ($1,420,000.00 ARR)

| Driver Theme | Mentions | Detractor Mentions | Exposed ARR (USD) |
| :--- | ---: | ---: | ---: |
| `latency_reliability` | 2 | 2 | $2,100,000.00 |
| `security_compliance` | 2 | 2 | $2,100,000.00 |
| `billing_pricing` | 1 | 1 | $1,420,000.00 |
| `missing_product_feature` | 1 | 1 | $1,420,000.00 |
| `support_responsiveness` | 1 | 0 | $0.00 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly VIP Escalation Radar` routine via `schedule_task`:

```text
Schedule recurring job "Hourly VIP Escalation Radar" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly VIP escalation exposure check via scripts/escalation_exposure_scorer.py across open Sev1/Sev2 accounts and renewal windows."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `responses`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `responses` requires [`response_id` or `account_id`; `csat_score` or `nps_score` or `verbatim`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `detractor_csat_max` | `integer` | `2` | Maximum CSAT rating (1-5) treated as detractor. |
| `detractor_nps_max` | `integer` | `6` | Maximum NPS rating (0-10) treated as detractor. |

See [`../../README.md`](../../README.md) for the `customer-operations-escalation` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
