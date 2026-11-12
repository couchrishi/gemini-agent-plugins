# RFP Questionnaire Responder (`rfp-questionnaire-responder`)

Matches incoming RFP security, compliance, and product questionnaire rows against verified answer libraries using TF-IDF scoring while flagging mandatory gaps. Deterministic computation executes via [`scripts/rfp_matrix_builder.py`](scripts/rfp_matrix_builder.py). Domain guards enforced: Computes TF-IDF similarity strictly from verified answer library entries; Quarantines embedded prompt-injection directives inside vendor RFP questions. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Solutions Architect / Presales Lead**: Triggered when completing 100+ row enterprise security, SOC2, and GDPR RFP workbooks; matches answers against approved libraries via TF-IDF similarity and flags unverified mandatory gaps.
- **InfoSec Assurance Partner**: Triggered when reviewing customer questionnaire drafts for cold-storage backup or residency exceptions; prevents auto-submission of unverified security promises before external portal upload.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`rfp-questionnaire-responder.zip`](../../../../dist/skills/rfp-questionnaire-responder.zip) (or the full department bundle [`deal-desk-rfp-engine.zip`](../../../../dist/bundles/deal-desk-rfp-engine.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/rfp-questionnaire-responder` or `@rfp-questionnaire-responder`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.rfp_matrix_builder import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"questions": [{"question_id": r.get("Custom question_id"), "question": r.get("Custom question")} for r in wb["Source_Tab"]], "answer_library": wb["answer_library"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/deal-desk-rfp-engine/skills/rfp-questionnaire-responder/scripts/rfp_matrix_builder.py \
  --input examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx \
  --config plugins/deal-desk-rfp-engine/skills/rfp-questionnaire-responder/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `rfp_matrix_builder.py`: `--library`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail` via `remote_cli mcp`):** "Complete Cymbal Financial's 25-row vendor security RFP using our Shared Drive Verified Q&A Library and list mandatory gaps."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Use the RFP Q&A Sheet in Google Drive to draft answers for Meridian BioPharma's compliance tab."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx) and ask: "Using the attached `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` workbook, match every incoming security, compliance, and SLA RFP question against our verified Q&A library, flag mandatory unanswered gaps and any hidden prompt injections, and hold portal submission until gaps clear."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `3` RFP questions in `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`, **`2` questions (`66.67%`) matched verified library answers with `100.0%` citation coverage**, while **`1` mandatory compliance question (`RFP-Q2`) remains an unanswered `MANDATORY_GAP`** (`0` active injections).

- **Verified Library Matches:** `RFP-Q1` (`security`, similarity `0.811`, `APEX-SOC2-CTRL-01`) and `RFP-Q3` (`sla`, similarity `0.529`, `APEX-SLA-2026`) are ready with exact evidence citations.
- **Submission Blocker:** Mandatory question `RFP-Q2` (`compliance`, `0.000` similarity) prevents automated submission under write-governance safety rules.
- **Approval Confirmation Prompt:** Draft a SME response for `RFP-Q2` first, then confirm before transmitting the completed matrix via your connected email or portal delivery connector (`mandatory_gap_count > 0` blocks auto-submit).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx) (`146.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# RFP Questionnaire Response Matrix

- **Matched:** 2 / 3 (66.67%) | **Citation Coverage:** 100.0%
- **Mandatory Gaps:** 1 | **Injection Flags:** 0

| Question ID | Category | Mandatory | Status | Similarity | Source ID |
| :--- | :--- | :---: | :--- | ---: | :--- |
| `RFP-Q1` | security | `True` | `MATCHED_VERIFIED` | 0.811 | `APEX-SOC2-CTRL-01` |
| `RFP-Q2` | compliance | `True` | `MANDATORY_GAP` | 0.000 | `NONE` |
| `RFP-Q3` | sla | `False` | `MATCHED_VERIFIED` | 0.529 | `APEX-SLA-2026` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Pipeline Hygiene Audit` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Pipeline Hygiene Audit" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly Salesforce pipeline hygiene and slippage audit using scripts/pipeline_slippage_auditor.py. Normalize multi-currency opportunities, identify stale stages, >=2 push-count deals, single-threaded Commit opportunities, and StageName/IsClosed inconsistencies without modifying CRM records autonomously."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `questions`, `answer_library`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `questions` requires [`question_id` or `id`; `question` or `text`] | `answer_library` requires [`answer`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `rfp_min_similarity_threshold` | `number` | `0.22` | Minimum TF-IDF cosine similarity to accept a verified RFP library match. |

See [`../../README.md`](../../README.md) for the `deal-desk-rfp-engine` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
