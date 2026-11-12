# Pharmacovigilance E2B ICSR Completeness & SLA (`pharmacovigilance-safety-intake`)

Validates Adverse Event intake reports against the 4 mandatory ICH ICSR criteria, computes exact 7-day fatal and 15-day expedited statutory due dates, and detects raw SSN/email/phone PHI. Deterministic computation executes via [`scripts/icsr_completeness_checker.py`](scripts/icsr_completeness_checker.py). Domain guards enforced: Checks all 4 ICH minimum criteria strictly without defaulting missing reporter/patient; Applies 7-day fatal/LT SUSAR vs 15-day serious unexpected SLA clocks. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Pharmacovigilance / Drug Safety Specialist**: Triggered when screening incoming E2B Individual Case Safety Reports (ICSRs) for regulatory clocks; enforces mandatory 4-element E2B validity, detects `7`-day fatal/life-threatening unexpected SUSAR deadlines, and flags unredacted PHI emails/phones.
- **Medical Safety Officer**: Triggered when triaging urgent expedited safety filings ahead of FDA/EMA statutory windows; quarantines subject identifiers before downstream distribution or regulator gateway submission.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`pharmacovigilance-safety-intake.zip`](../../../../dist/skills/pharmacovigilance-safety-intake.zip) (or the full department bundle [`healthcare-clinical-regulatory.zip`](../../../../dist/bundles/healthcare-clinical-regulatory.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` + Customer BYO-MCP (`Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/pharmacovigilance-safety-intake` or `@pharmacovigilance-safety-intake`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.icsr_completeness_checker import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"cases": [{"case_id": r.get("Custom case_id"), "adverse_event_term": r.get("Custom adverse_event_term"), "awareness_date": r.get("Custom awareness_date")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/healthcare-clinical-regulatory/skills/pharmacovigilance-safety-intake/scripts/icsr_completeness_checker.py \
  --input examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx \
  --config plugins/healthcare-clinical-regulatory/skills/pharmacovigilance-safety-intake/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `icsr_completeness_checker.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` + Customer BYO-MCP (`Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`) via `remote_cli mcp`):** "Screen Meridian BioPharma safety cases including a fatal unexpected SUSAR aware on 2026-11-05 as of 2026-11-10."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Drive Safety Intake Sheet where a reporter pasted an SSN (123-45-6789) and email in the narrative."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx) and ask: "Screen incoming E2B Individual Case Safety Reports (ICSRs) in `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` as of `2026-11-10` for 4-element ICH validity, `7`-day fatal/life-threatening SUSAR deadlines, and unredacted patient PHI."

## Sample Response

### What You See in Gemini Enterprise Chat

Screening `2` valid 4-element ICH ICSRs in `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` as of `2026-11-10` flagged **`1` overdue `7`-day fatal/life-threatening SUSAR (`ICSR-APX-9041`, due `2026-11-08`, `-2d` `REGULATORY_SLA_OVERDUE`)** and **`1` case containing unredacted Email/Phone PHI (`ICSR-APX-9042`, `PHI_REDACTION_REQUIRED`)**.

- **Urgent Statutory SLA Breach (`ICSR-APX-9041`):** 7-day fatal/LT SUSAR crossed its `2026-11-08` regulatory clock by `2` days (`Clean` of raw PHI) and requires immediate medical-officer expedited handling.
- **PHI Redaction Gate (`ICSR-APX-9042`):** 90-day periodic report (`85d` left) contains unredacted patient Email and Phone identifiers blocked from downstream transmission.
- **Approval Confirmation Prompt:** Confirm redaction of `ICSR-APX-9042` PHI and medical safety sign-off before submitting `ICSR-APX-9041` to health authorities via your connected safety / regulatory MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx) (`134.8 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Pharmacovigilance E2B ICSR Completeness & SLA Watch (As Of 2026-11-10)

- **Cases Screened:** 2 | **Valid 4-Criteria ICSRs:** 2 | **PHI Redaction Alerts:** 1 | **Urgent/Overdue:** 1

| Case ID | Valid 4-ICH | Reporting Class | Due Date | Days Left | PHI Alerts | Status |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| `ICSR-APX-9041` | YES | 7-Day Fatal/LT SUSAR | 2026-11-08 | -2 | Clean | `REGULATORY_SLA_OVERDUE` |
| `ICSR-APX-9042` | YES | 90-Day Periodic PBRER | 2027-02-03 | 85 | Email, Phone | `PHI_REDACTION_REQUIRED` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Pharmacovigilance ICSR SLA Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Pharmacovigilance ICSR SLA Watch" on cron `0 7 * * *` (`UTC`) with instruction: "Run the daily pharmacovigilance intake check via scripts/icsr_completeness_checker.py to watch 7-day fatal SUSAR clocks, incomplete 4-criteria cases, and raw PHI alerts."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `cases`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `cases` requires [`case_id`; `adverse_event_term`; `awareness_date`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `fatal_lt_susar_days` | `integer` | `7` | Regulatory reporting SLA days for fatal/life-threatening unexpected SUSAR. |
| `serious_unexpected_days` | `integer` | `15` | Regulatory reporting SLA days for serious unexpected SUSAR. |
| `periodic_report_days` | `integer` | `90` | Standard periodic safety reporting cycle days. |

See [`../../README.md`](../../README.md) for the `healthcare-clinical-regulatory` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
