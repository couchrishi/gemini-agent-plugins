# Insurance Claims Coverage & Reserve Triage (`insurance-claims-triage-pack`)

Evaluates insurance claims against policy effective windows, peril exclusions, deductibles, coinsurance retention, peril sublimits, and $100k high-value reserve escalation caps. Deterministic computation executes via [`scripts/coverage_limit_evaluator.py`](scripts/coverage_limit_evaluator.py). Domain guards enforced: Rejects out-of-period and excluded-peril claims with $0 net payable; Applies deductible before coinsurance and peril sublimit/aggregate caps. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Complex Claims Adjuster (Cyber & Property)**: Triggered when triaging incoming loss notifications against policy exclusions, deductibles, and sublimits; applies policy sublimit caps (`$150k` cyber ransomware), enforces named exclusions (`flood -> $0`), and calculates net payable indemnity.
- **Claims Reserve Authority Manager**: Triggered when reviewing high-value reserve postings exceeding adjuster authority (`>$100k`); escalates high-reserve cyber claims (`CLM-APX-701`) to Senior Adjuster approval before reserve posting.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`insurance-claims-triage-pack.zip`](../../../../dist/skills/insurance-claims-triage-pack.zip) (or the full department bundle [`fsi-credit-kyc-claims.zip`](../../../../dist/bundles/fsi-credit-kyc-claims.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` + Customer BYO-MCP (`KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/insurance-claims-triage-pack` or `@insurance-claims-triage-pack`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.coverage_limit_evaluator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"claims": [{"claim_id": r.get("Custom claim_id"), "claimed_amount_usd": r.get("Custom claimed_amount_usd"), "peril": r.get("Custom peril")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/fsi-credit-kyc-claims/skills/insurance-claims-triage-pack/scripts/coverage_limit_evaluator.py \
  --input examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx \
  --config plugins/fsi-credit-kyc-claims/skills/insurance-claims-triage-pack/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `coverage_limit_evaluator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` + Customer BYO-MCP (`KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`) via `remote_cli mcp`):** "Evaluate $350k ransomware claim with $25k deductible, $150k cyber sublimit, and 80% coinsurance."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Drive Claims Sheet where CLM-2 occurred after policy expiration and CLM-3 claims excluded flood damage."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx) and ask: "Triage the First Notice of Loss (FNOL) claims batch in `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` against policy perils, exclusions, deductibles, and cyber sublimits, separating adjuster-ready payouts from reserve escalations and denied claims."

## Sample Response

### What You See in Gemini Enterprise Chat

Triaging `3` FNOL claims totaling **`$650,000.00` claimed** in `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` computed **`$182,000.00` net payable indemnity**: **`CLM-APX-701` (`$150,000.00`)** capped at the cyber sublimit for Senior Adjuster reserve escalation, **`CLM-APX-702` (`$0.00`)** denied under the flood exclusion, and **`CLM-APX-703` (`$32,000.00`)** cleared for sign-off.

- **Sublimit & Reserve Authority Gate (`CLM-APX-701`):** `$420,000.00` cyber ransomware loss capped deterministically at `$150,000.00`, exceeding the `$100,000` frontline authority cap (`RESERVE_ESCALATION_SENIOR_ADJUSTER`).
- **Exclusion Denial vs. Standard Approval:** `CLM-APX-702` (`$185,000` flood claim) returned `$0.00` (`COVERAGE_DENIED_EXCLUSION`), while `CLM-APX-703` (`$45,000` property water loss) netted `$32,000.00` (`ELIGIBLE_FOR_ADJUSTER_SIGN_OFF`).
- **Approval Confirmation Prompt:** Confirm Senior Adjuster reserve sign-off and authorized disbursement for the `$182,000.00` net payable pool (`$32,000` immediate + `$150,000` escalated) via your connected claims / clearinghouse MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx) (`139.0 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Insurance Claims Coverage, Sublimit & Reserve Triage

- **Claims Triaged:** 3 | **Denied:** 1 | **Reserve Escalations:** 1
- **Total Claimed:** $650,000.00 | **Calculated Net Payable:** $182,000.00

| Claim ID | Peril | Claimed | Net Payable | Decision | Notes |
| :--- | :--- | ---: | ---: | :--- | :--- |
| `CLM-APX-701` | cyber_ransomware | $420,000.00 | **$150,000.00** | `RESERVE_ESCALATION_SENIOR_ADJUSTER` | Net payable $150,000.00 >= $100,000 authority cap. |
| `CLM-APX-702` | flood | $185,000.00 | **$0.00** | `COVERAGE_DENIED_EXCLUSION` | Peril 'flood' is explicitly excluded under policy POL-CYBER-26. |
| `CLM-APX-703` | property_water | $45,000.00 | **$32,000.00** | `ELIGIBLE_FOR_ADJUSTER_SIGN_OFF` | Covered |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily KYB Velocity & Structuring Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily KYB Velocity & Structuring Watch" on cron `0 5 * * *` (`UTC`) with instruction: "Run the daily AML transaction velocity and structuring sweep via scripts/ubo_velocity_screener.py across active corporate banking accounts and flag EDD alerts for MLRO review."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `claims`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `claims` requires [`claim_id`; `claimed_amount_usd`; `peril` or `policy` or `policy_id`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `high_value_claim_threshold` | `number` | `100000.0` | Net claim reserve escalation authority ceiling in USD. |

See [`../../README.md`](../../README.md) for the `fsi-credit-kyc-claims` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
