# Prior Authorization Medical Necessity Reviewer (`prior-auth-medical-necessity`)

Evaluates healthcare prior authorization clinical packets deterministically against payer CPT medical policies, ICD-10 diagnosis prefixes, prior step-therapy trials, and required diagnostic labs. Deterministic computation executes via [`scripts/medical_criteria_matcher.py`](scripts/medical_criteria_matcher.py). Domain guards enforced: Validates both step-therapy count AND minimum duration days; Flags unmapped CPT policies safely rather than guessing approval. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Utilization Management Nurse / Medical Reviewer**: Triggered when evaluating biologic/specialty prior-authorization packets against payer clinical policies; verifies completed vs ongoing step-therapy duration (`>=30d` fallback or policy rule), contraindications, and lab thresholds.
- **Health Plan Appeals Coordinator**: Triggered when preparing payer medical-necessity determination drafts with auditable criteria proof; routes gap-incomplete requests to peer-to-peer review instead of premature clinical denials.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`prior-auth-medical-necessity.zip`](../../../../dist/skills/prior-auth-medical-necessity.zip) (or the full department bundle [`healthcare-clinical-regulatory.zip`](../../../../dist/bundles/healthcare-clinical-regulatory.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` + Customer BYO-MCP (`Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/prior-auth-medical-necessity` or `@prior-auth-medical-necessity`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.medical_criteria_matcher import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"requests": [{"auth_id": r.get("Custom auth_id"), "cpt_code": r.get("Custom cpt_code"), "icd10_codes": r.get("Custom icd10_codes")} for r in wb["Source_Tab"]], "policies": wb["policies"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/healthcare-clinical-regulatory/skills/prior-auth-medical-necessity/scripts/medical_criteria_matcher.py \
  --input examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx \
  --config plugins/healthcare-clinical-regulatory/skills/prior-auth-medical-necessity/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `medical_criteria_matcher.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` + Customer BYO-MCP (`Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`) via `remote_cli mcp`):** "Evaluate prior auth PA-401 for biologic therapy requiring two >=30-day step failures when patient completed only one 14-day trial."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Drive Prior Auth packet PA-402 missing required MRI report documentation."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx) and ask: "Review the prior authorization packets in `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` against clinical policy criteria—checking step-therapy trial completions, durations (`>=30d`), and mandatory diagnostic attachments—to separate clinical approvals from peer-review holds."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `2` prior authorization requests (`CPT 72148`) in `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` cleared **`PA-APX-1101` as `RECOMMEND_CLINICAL_APPROVAL` (`1 / 2` criteria met)** while routing **`PA-APX-1102` to `PEER_REVIEW_MISSING_DOCS`** due to a qualifying step-therapy shortfall (`0` >=30d trials) and missing `neuro_exam` documentation.

- **Ready for Clinical Sign-Off (`PA-APX-1101`):** Verified all required step-therapy durations and clinical documentation cleanly.
- **Non-Denial Peer-Review Route (`PA-APX-1102`):** Avoids premature automated denial while requesting the missing `neuro_exam` and `>=30`-day trial proof.
- **Approval Confirmation Prompt:** Confirm Medical Director authorization to issue the approval determination for `PA-APX-1101` and peer-review notice for `PA-APX-1102` via your connected payer / EHR clearinghouse MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx`](../../../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx) (`147.9 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Prior Authorization Medical Necessity Checklist

- **Requests Evaluated:** 2 | **All Criteria Met (HITL Ready):** 1 | **Gaps / Director Review:** 1

| Auth ID | CPT | Criteria Met | Recommendation | Gaps |
| :--- | :--- | :--- | :--- | :--- |
| `PA-APX-1101` | `72148` | YES | `RECOMMEND_CLINICAL_APPROVAL` | None |
| `PA-APX-1102` | `72148` | NO | `PEER_REVIEW_MISSING_DOCS` | Step therapy shortfall: 0 qualifying trials (>= 30d), need 1.; Missing required diagnostic documentation: neuro_exam. |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Pharmacovigilance ICSR SLA Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Pharmacovigilance ICSR SLA Watch" on cron `0 7 * * *` (`UTC`) with instruction: "Run the daily pharmacovigilance intake check via scripts/icsr_completeness_checker.py to watch 7-day fatal SUSAR clocks, incomplete 4-criteria cases, and raw PHI alerts."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `policies`, `requests`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `requests` requires [`auth_id`; `cpt_code`; `icd10_codes`] | `policies` requires [`cpt_code`; `covered_icd10_prefixes`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_min_step_days` | `integer` | `30` | Fallback minimum prior step-therapy duration in days. |

See [`../../README.md`](../../README.md) for the `healthcare-clinical-regulatory` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
