# Executed Obligation Extractor (`executed-obligation-extractor`)

Extracts renewal dates, calculates exact opt-out notice deadlines (renewal_date minus notice_days), detects uncapped CPI escalators, and compiles executed obligation calendars. Deterministic computation executes via [`scripts/obligation_calendar_builder.py`](scripts/obligation_calendar_builder.py). Domain guards enforced: Flags missing renewal_date or notice_days as UNVERIFIED rather than zero; Computes renewal_date minus notice_days deterministically using timedelta. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Legal Ops / Contract Administrator**: Triggered when monitoring executed vendor renewals, auto-renewal opt-out deadlines, and CPI uplifts; surfaces imminent opt-out windows (`<=60d`), expired notice cliffs, and annual price escalators above `5%`.
- **Procurement & Vendor Governance Lead**: Triggered when validating post-signature deliverable and notice calendars ahead of Q4 renewals; prevents unapproved evergreen lock-ins caused by missed advance cancellation dates.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`executed-obligation-extractor.zip`](../../../../dist/skills/executed-obligation-extractor.zip) (or the full department bundle [`legal-contract-desk.zip`](../../../../dist/bundles/legal-contract-desk.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx).
4. Ask naturally in chat or invoke directly with `/executed-obligation-extractor` or `@executed-obligation-extractor`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.obligation_calendar_builder import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"contracts": [{"contract_id": r.get("Source contract_id"), "counterparty": r.get("Source counterparty")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/legal-contract-desk/skills/executed-obligation-extractor/scripts/obligation_calendar_builder.py \
  --input examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx \
  --config plugins/legal-contract-desk/skills/executed-obligation-extractor/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `obligation_calendar_builder.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail` via `remote_cli mcp`):** "Audit all Apex Manufacturing executed supplier MSAs in SharePoint for upcoming opt-out deadlines."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Scan our Executed Contract Registry Sheet in Drive where two auto-renewing agreements have blank `notice_days`."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx) and ask: "Extract all renewal dates, advance opt-out deadlines, and annual CPI price escalators from `Apex_MSA_Obligations_and_Compliance_Sample.docx` as of `2026-11-10`, highlighting expired cliffs and renewals closing within 60 days."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing `3` executed vendor agreements in `Apex_MSA_Obligations_and_Compliance_Sample.docx` as of `2026-11-10` exposed **`$420,000.00` in urgent or expired annual exposure**: `CON-APX-088` (`$180,000`) is already **`24` days past its opt-out window**, `CON-APX-092` (`$240,000`) closes in **`23` days**, and **`1` CPI escalator breached the `5.0%` cap**.

- **Missed & Urgent Deadlines:** `CON-APX-088` (`Apex Cloud Storage`, `$180k`, `90d` notice) expired `2026-10-17` (`-24d`), while `CON-APX-092` (`Meridian Analytics`, `$240k`, `60d` notice) hits `CRITICAL_URGENT` on `2026-12-03` (`23d` left).
- **Unverified Notice Date Flagged:** `CON-APX-105` (`Nordic Logistics Software`, `$95k`) lacks a verified notice trigger (`UNVERIFIED`) rather than guessing a date.
- **Approval Confirmation Prompt:** Confirm if you would like to dispatch external non-renewal notices for `CON-APX-092` (`23d` left) via your connected `Gmail`, `Outlook`, or SharePoint/Drive sharing connector before the `2026-12-03` deadline.

### Verified Deterministic Engine Output

Executed directly against [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx) (`163.5 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Executed Contract Obligation & Renewal Calendar (As Of 2026-11-10)

- **Contracts Audited:** 3 | **Urgent/Action Windows:** 1 | **Expired:** 1 | **Unverified:** 0
- **Urgent/Expired Annual Exposure:** $420,000.00 | **CPI Escalator Breaches:** 1

| Contract | Counterparty | Annual Value | Renewal Date | Notice Days | Opt-Out Deadline | Days Left | Urgency |
| :--- | :--- | ---: | :--- | ---: | :--- | ---: | :--- |
| `CON-APX-088` | Apex Cloud Storage | $180,000.00 | 2027-01-15 | 90 | 2026-10-17 | -24 | `EXPIRED_WINDOW` |
| `CON-APX-092` | Meridian Analytics | $240,000.00 | 2027-02-01 | 60 | 2026-12-03 | 23 | `CRITICAL_URGENT` |
| `CON-APX-105` | Nordic Logistics Software | $95,000.00 | 2027-06-30 | 30 | UNVERIFIED | — | `NONE` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Renewal & Notice Deadline Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Renewal & Notice Deadline Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly executed contract renewal and obligation watch via scripts/obligation_calendar_builder.py. Compute exact opt-out notice deadlines (`renewal_date - notice_days`), surface urgent <=30 day windows and uncapped CPI escalators, and generate a draft reminder pack without emailing counterparties."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `contracts`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `contracts` requires [`contract_id`; `counterparty` or `renewal_date` or `annual_value_usd`] | `obligations` requires [`contract_id` or `obligation_type`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_renewal_notice_days` | `integer` | `60` | Maximum auto-renewal advance notice window before flagging a redline. |
| `max_price_escalator_pct` | `number` | `5.0` | Maximum annual renewal price uplift / CPI cap percentage. |
| `max_breach_notify_hours` | `integer` | `72` | Maximum allowed DPA security incident notification window in hours. |

See [`../../README.md`](../../README.md) for the `legal-contract-desk` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
