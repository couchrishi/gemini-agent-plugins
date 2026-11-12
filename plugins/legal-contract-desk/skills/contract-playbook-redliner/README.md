# Contract Playbook Redliner (`contract-playbook-redliner`)

Evaluates NDA, SaaS MSA, and DPA clauses on a 1/3/9 risk scale against legal playbooks, flags Score 9 walk-away blockers and untrusted counterparty prompt injections, and drafts fallback redlines. Deterministic computation executes via [`scripts/clause_risk_matrix.py`](scripts/clause_risk_matrix.py). Domain guards enforced: Quarantines indirect prompt injection attempts inside counterparty clauses; Never defaults missing breach notification hours to compliant. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Commercial Counsel / Contracts Manager**: Triggered when redlining counterparty MSAs and DPAs against corporate risk tolerances; scores clauses `1/3/9`, flags Sec `14.3(b)` unilateral caps and `96h` breach notices, and quarantines injected instructions.
- **Privacy & AI Governance Counsel**: Triggered when reviewing vendor data-processing addenda for AI model training language; enforces Score-9 zero-training covenants (`forbid_customer_data_training = true`) and approved governing law.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`contract-playbook-redliner.zip`](../../../../dist/skills/contract-playbook-redliner.zip) (or the full department bundle [`legal-contract-desk.zip`](../../../../dist/bundles/legal-contract-desk.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx).
4. Ask naturally in chat or invoke directly with `/contract-playbook-redliner` or `@contract-playbook-redliner`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.clause_risk_matrix import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"clauses": [{"clause_id": r.get("Source clause_id"), "clause_text": r.get("Source clause_text")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/legal-contract-desk/skills/contract-playbook-redliner/scripts/clause_risk_matrix.py \
  --input examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx \
  --config plugins/legal-contract-desk/skills/contract-playbook-redliner/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `clause_risk_matrix.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail` via `remote_cli mcp`):** "Review Cymbal Financial's incoming vendor MSA draft in Drive for 1/3/9 playbook compliance."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate the Meridian BioPharma DPA in Google Docs against our Legal Playbook Doc."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx) and ask: "Redline the counterparty MSA and DPA clauses in the attached `Apex_MSA_Obligations_and_Compliance_Sample.docx` document on a 1/3/9 risk scale, quarantine any hidden prompt injections, and prepare fallback positions for Score-9 blockers."

## Sample Response

### What You See in Gemini Enterprise Chat

Reviewing `5` clauses (`31` total risk points) in **`MSA-APX-MRD-2026`** (Meridian Enterprise Systems Inc.) from `Apex_MSA_Obligations_and_Compliance_Sample.docx` **blocked signature readiness (`BLOCKED_BY_SCORE_9`)** with **`3` Score-9 walk-away blockers**, **`1` Score-3 negotiable jurisdiction gap**, and **`1` quarantined prompt injection (`DPA-AI-114`)**.

- **Score-9 Walk-Away Blockers (`3`):** `MSA-LOL-14B` (uncapped consequential/general liability), `DPA-INC-82` (`vagueh` breach notice failing `<=72h` rule), and `DPA-AI-114` (unrestricted AI training rights + `QUARANTINED` prompt injection).
- **Negotiable vs. Compliant Clauses:** `MSA-LAW-221` (`Score 3`, jurisdiction `'Unspecified'` outside approved DE/NY/England & Wales/SG) needs fallback replacement; `MSA-REN-182` (`Score 1`) complies.
- **Approval Confirmation Prompt:** Confirm if you would like to send this fallback redline package to Meridian counsel via your connected `Gmail`, `Outlook`, or SharePoint/Drive sharing connector (gated by `Auto-Guardian`); final contract execution stays blocked pending Legal sign-off.

### Verified Deterministic Engine Output

Executed directly against [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx) (`149.2 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Contract Playbook Redline Matrix — `MSA-APX-MRD-2026` (Meridian Enterprise Systems Inc.)

- **Contract Type:** MSA | **Signature Readiness:** `BLOCKED_BY_SCORE_9`
- **Clauses Reviewed:** 5 | **Score 9 Blockers:** 3 | **Score 3 Redlines:** 1 | **Injection Quarantined:** 1

| Clause ID | Family | Score | Band | IPI Flag | Finding |
| :--- | :--- | ---: | :--- | :--- | :--- |
| `MSA-LOL-14B` | `limitation_of_liability` | **9** | Critical / Walk-Away Blocker | Clean | General liability is uncapped or exposes consequential damages. |
| `DPA-INC-82` | `dpa_breach_notification` | **9** | Critical / Walk-Away Blocker | Clean | Breach notification window (vagueh) fails statutory <= 72h threshold. |
| `DPA-AI-114` | `data_rights_ai_training` | **9** | Critical / Walk-Away Blocker | QUARANTINED | Counterparty claims customer pre-existing IP or unrestricted AI training rights. |
| `MSA-REN-182` | `auto_renewal` | **1** | Low / Acceptable | Clean | Renewal notice window and escalator cap comply with baseline limits. |
| `MSA-LAW-221` | `governing_law` | **3** | Moderate / Negotiable | Clean | Jurisdiction 'Unspecified' is outside approved list (delaware, england and wales, new york, singapore). |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Renewal & Notice Deadline Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Renewal & Notice Deadline Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly executed contract renewal and obligation watch via scripts/obligation_calendar_builder.py. Compute exact opt-out notice deadlines (`renewal_date - notice_days`), surface urgent <=30 day windows and uncapped CPI escalators, and generate a draft reminder pack without emailing counterparties."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `clauses`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `clauses` requires [`clause_id` or `id`; `clause_text` or `text` or `clause_family`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `lol_cap_months_min` | `integer` | `12` | Minimum acceptable Limitation of Liability cap in months of trailing fees. |
| `lol_cap_months_max` | `integer` | `24` | Maximum preferred Limitation of Liability cap in months of fees. |
| `super_cap_multiplier_max` | `number` | `3.0` | Maximum acceptable super-cap multiple over general LoL for data/IP/confidentiality. |
| `max_renewal_notice_days` | `integer` | `60` | Maximum auto-renewal advance notice window before flagging a redline. |
| `max_price_escalator_pct` | `number` | `5.0` | Maximum annual renewal price uplift / CPI cap percentage. |
| `max_breach_notify_hours` | `integer` | `72` | Maximum allowed DPA security incident notification window in hours. |
| `forbid_customer_data_training` | `boolean` | `True` | When true, clauses granting vendor AI model training rights on customer data score Score 9. |
| `approved_jurisdictions` | `array` | `["Delaware", "New York", "England and Wales", "Singapore"]` | Approved governing law jurisdictions. |
| `max_control_evidence_days` | `integer` | `365` | Maximum age of compliance control test evidence before flagging stale. |

See [`../../README.md`](../../README.md) for the `legal-contract-desk` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
