# Test Scenarios: `policy-sop-answering`

## Scenario 1 — Live Enterprise Connectors: Jurisdiction-Scoped Lookup with Superseded Clause Filtering
- **Prompt:** "What is Apex Manufacturing's parental leave duration in Singapore as of 2026-11-10? Check SharePoint and Drive policies."
- **Assertions:**
  - Filters out `US` and `superseded` / `draft` versions via `policy_scope_matcher.py`.
  - Returns exact active Singapore clause with version and effective date.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Workspace Fallback with Abstention on Uncovered Jurisdiction
- **Prompt:** "Using our HR Policy Google Sheet in Drive, tell me the meal reimbursement cap for Brazil contractors."
- **Assertions:**
  - Finds zero active clauses matching `BR` / `contractor`.
  - Emits `abstained: true` (`ABSTENTION_NO_EFFECTIVE_COVERAGE`) rather than extrapolating US/Global FTE limits.

## Scenario 3 — Optional Local File Sandbox: Uploaded Policy Table with Future-Dated Amendment
- **Prompt:** "Evaluate `policy_clauses.json` as of `2026-11-10` for `Cymbal Financial` in `DE` where a 2027 amendment is already uploaded."
- **Assertions:**
  - Rejects clauses with `effective_date > 2026-11-10` (`not_yet_effective`).
  - Includes `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.
