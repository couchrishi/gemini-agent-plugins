# KYB/UBO Ownership & AML Velocity Screener (`kyc-aml-screening-dossier`)

Resolves cumulative indirect Ultimate Beneficial Ownership percentages across corporate holding layers, lowers EDD threshold to 10% for PEP/high-risk jurisdictions, and flags transaction velocity or structuring alerts. Deterministic computation executes via [`scripts/ubo_velocity_screener.py`](scripts/ubo_velocity_screener.py). Domain guards enforced: Sums multi-hop fractional ownership paths accurately for individuals across holding layers; Flags structured $8,000-$9,999 deposits >= 5 as structuring_alert=true. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **KYB / AML Financial Crimes Investigator**: Triggered when tracing multi-hop corporate shell ownership and cross-border wire patterns; applies lowered `10%` EDD UBO threshold for high-risk jurisdictions/PEPs (`28%`, `12%`) and flags sub-`$10k` smurfing velocity spikes (`3.84x`).
- **MLRO / BSA Compliance Officer**: Triggered when deciding whether high-risk corporate onboardings trigger Enhanced Due Diligence or SAR drafting; quarantines EDD triggers deterministically and gates formal SAR/block actions behind MLRO confirmation.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`kyc-aml-screening-dossier.zip`](../../../../dist/skills/kyc-aml-screening-dossier.zip) (or the full department bundle [`fsi-credit-kyc-claims.zip`](../../../../dist/bundles/fsi-credit-kyc-claims.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` + Customer BYO-MCP (`KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/kyc-aml-screening-dossier` or `@kyc-aml-screening-dossier`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.ubo_velocity_screener import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"ownership_edges": [{"owner_id": r.get("Custom owner_id"), "target_id": r.get("Custom target_id"), "direct_pct": r.get("Custom direct_pct")} for r in wb["Source_Tab"]], "transactions": wb["transactions"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/fsi-credit-kyc-claims/skills/kyc-aml-screening-dossier/scripts/ubo_velocity_screener.py \
  --input examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx \
  --config plugins/fsi-credit-kyc-claims/skills/kyc-aml-screening-dossier/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `ubo_velocity_screener.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` + Customer BYO-MCP (`KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`) via `remote_cli mcp`):** "Trace Cymbal Financial onboarding entity owned via two 60%/50% indirect holding layers registered in KY."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Drive AML Transaction Sheet with 4.2x 30d volume spike and 6 cash deposits between $9,100-$9,800."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx) and ask: "Trace multi-hop beneficial ownership and 30-day transaction velocity patterns in `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` for `MERIDIAN-HOLDINGS-KY`, applying the tightened `10%` EDD UBO threshold for high-risk jurisdictions/PEPs and screening for sub-`$10k` wire structuring."

## Sample Response

### What You See in Gemini Enterprise Chat

Screening **`MERIDIAN-HOLDINGS-KY`** (`0` ownership cycles) in `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` triggered **`EDD_MLRO_ESCALATION_REQUIRED`** under the tightened **`10.0%` high-risk UBO floor**, identifying **`2` beneficial owners (`Elena Rostova` PEP `28.00%`, `Victor Tan` `12.00%`)**, a **`3.84x` 30-day wire velocity spike**, and **`6` sub-`$10k` (`$8k-$9.99k`) structuring transactions**.

- **Multi-Hop UBO Threshold Catch:** `Victor Tan` (`12.00%`, SG) would evade a naive `25%` UBO check but is surfaced immediately by the jurisdiction/PEP-triggered `10.0%` EDD threshold alongside PEP `Elena Rostova` (`28.00%`, US).
- **AML Structuring & Velocity Alerts:** `6` near-threshold cash/wire events between `$8,000` and `$9,999` coincided with a `3.84x` 30-day volume spike.
- **Approval Confirmation Prompt:** Confirm MLRO authorization before filing a Suspicious Activity Report or placing an onboarding account block via your connected AML / KYC compliance MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx) (`139.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# KYB Beneficial Ownership & AML Screening Dossier — `MERIDIAN-HOLDINGS-KY`

- **KYC Tier:** `EDD_MLRO_ESCALATION_REQUIRED` | **Active UBO Threshold:** 10.0% | **Identified UBOs:** 2
- **30d Velocity Multiplier:** 3.84x (Alert: `True`) | **Structuring ($8k-$9.99k) Count:** 6 (Alert: `True`)

| UBO ID | Beneficial Owner | Jurisdiction | PEP | Effective Ownership % | Threshold Hit |
| :--- | :--- | :--- | :--- | ---: | :--- |
| `UBO-IND-401` | Elena Rostova | US | YES | **28.00%** | YES |
| `UBO-IND-402` | Victor Tan | SG | No | **12.00%** | YES |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily KYB Velocity & Structuring Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily KYB Velocity & Structuring Watch" on cron `0 5 * * *` (`UTC`) with instruction: "Run the daily AML transaction velocity and structuring sweep via scripts/ubo_velocity_screener.py across active corporate banking accounts and flag EDD alerts for MLRO review."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `target_entity_id`, `rolling_30d_volume_usd`, `trailing_90d_monthly_avg_usd`, `ownership_edges`, `transactions`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `ownership_edges` requires [`owner_id`; `target_id`; `direct_pct`] | `transactions` requires [`tx_id`; `amount_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `ubo_standard_pct` | `number` | `25.0` | Standard cumulative beneficial ownership disclosure threshold %. |
| `ubo_edd_pct` | `number` | `10.0` | Reduced UBO threshold % when high-risk jurisdiction or PEP triggers EDD. |
| `velocity_spike_multiplier` | `number` | `3.0` | 30d-to-90d transaction velocity ratio triggering AML alert. |
| `structuring_count_threshold` | `integer` | `5` | Near-$10k deposit count threshold for structuring flag. |

See [`../../README.md`](../../README.md) for the `fsi-credit-kyc-claims` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
