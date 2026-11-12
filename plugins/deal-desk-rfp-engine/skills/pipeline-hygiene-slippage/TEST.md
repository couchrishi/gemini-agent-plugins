# Test Scenarios: `pipeline-hygiene-slippage`

## Scenario 1 — Live Enterprise Connectors: Multi-Currency SOQL Pipeline Audit
- **Prompt:** "Audit our Q4 Salesforce Commit and BestCase deals across US (USD), EU (EUR), and Japan (JPY) against $4.0M remaining quota."
- **Assertions:**
  - Normalizes `JPY` and `EUR` amounts using `fx_rates` rather than summing nominal figures.
  - Flags `done=false` / `totalSize > fetched` as `TRUNCATION_WARNING`.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Pipeline Sheet Commit Integrity Check
- **Prompt:** "Review our Revenue Ops Pipeline Sheet in Drive for single-threaded Commit deals and chronic pushers."
- **Assertions:**
  - Flags `Commit` deals with `< 2` contacts, missing `economic_buyer`, or `push_count >= 2`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local CSV Upload with Missing FX Rate & Stage Contradiction
- **Prompt:** "Run `pipeline_slippage_auditor.py` on `pipeline.json` containing an unmapped `AUD` deal and a Closed Lost stage marked `is_closed=false`."
- **Assertions:**
  - Emits `FX_CONVERSION_GAP` and excludes unmapped `AUD` deal from USD total instead of mixing currencies.
  - Flags `STAGE_CONTRADICTION` explicitly.
