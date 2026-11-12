# Test Scenarios: `workforce-attrition-comp-audit`

## Scenario 1 — Live Enterprise Connectors: Workday Effective-Dated Multi-Snapshot
- **Prompt:** "Audit Workday roster where promoted employees have 3 historical effective_date rows plus 1 future-dated row and 4 CWKs."
- **Assertions:**
  - Selects latest effective_date <= as_of_date and excludes future rows.
  - Isolates CWKs so FTE headcount and compa-ratios are exact.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Sheet Small-Cell Redaction
- **Prompt:** "Check department compa-ratios from Drive Sheet where Legal has 3 FTEs and Engineering has hourly + EUR staff."
- **Assertions:**
  - Redacts Legal avg_compa_ratio and attrition_pct (suppressed_for_privacy=true).
  - Normalizes hourly * 2080 and EUR FX properly.

## Scenario 3 — Optional Local File Sandbox: Local HRIS CSV Compression Audit
- **Prompt:** "Analyze workers.csv for <0.80 compression and >1.25 ceiling outliers."
- **Assertions:**
  - Flags BELOW_BAND_COMPRESSION and ABOVE_BAND_CEILING outliers accurately.
  - Maintains baseline disclosure banner.
