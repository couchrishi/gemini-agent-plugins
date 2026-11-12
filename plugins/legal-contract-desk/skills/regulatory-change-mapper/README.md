# Regulatory Change Mapper (`regulatory-change-mapper`)

Maps regulatory articles against internal security and privacy controls, flags missing controls and stale or null audit evidence, and ranks remediation queues. Deterministic computation executes via [`scripts/control_gap_mapper.py`](scripts/control_gap_mapper.py). Domain guards enforced: Treats null last_tested_date or missing evidence_uri as UNVERIFIED_MISSING_EVIDENCE; Flags test evidence older than max_control_evidence_days as STALE_EVIDENCE. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **GRC / InfoSec Compliance Lead**: Triggered when mapping incoming EU AI Act, GDPR, DORA, or SOC2 obligations onto internal controls; flags stale control test evidence (`>365d`), uncovered regulatory gaps, and failing continuous checks.
- **Chief Information Security Officer (CISO) Staff**: Triggered when generating board compliance posture readouts from live control registries; calculates weighted compliance readiness and queues remediation tickets under human sign-off.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`regulatory-change-mapper.zip`](../../../../dist/skills/regulatory-change-mapper.zip) (or the full department bundle [`legal-contract-desk.zip`](../../../../dist/bundles/legal-contract-desk.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx).
4. Ask naturally in chat or invoke directly with `/regulatory-change-mapper` or `@regulatory-change-mapper`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.control_gap_mapper import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"controls": [{"control_id": r.get("Source control_id"), "control_status": r.get("Source control_status")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/legal-contract-desk/skills/regulatory-change-mapper/scripts/control_gap_mapper.py \
  --input examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx \
  --config plugins/legal-contract-desk/skills/regulatory-change-mapper/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `control_gap_mapper.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail` via `remote_cli mcp`):** "Map EU DORA operational resilience articles against our ServiceNow GRC control register for Cymbal Financial."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate our Drive Compliance Control Register Sheet where `CTRL-204` has a blank `last_tested_date` and `CTRL-205` is 490 days old."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx) and ask: "Map the EU AI Act and GDPR regulatory obligations in `Apex_MSA_Obligations_and_Compliance_Sample.docx` against our internal control register as of `2026-11-10`, flagging stale test evidence (>365 days) and uncovered control gaps."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `3` regulatory articles in `Apex_MSA_Obligations_and_Compliance_Sample.docx` as of `2026-11-10` yielded **`33.3%` overall readiness (`1 / 3` compliant)**: `ART-32` (`GDPR`) passed via `CTRL-ENC-01` & `CTRL-IAM-04`, while **`ART-17` failed on stale evidence** and **`EU-AI-14` remains completely uncovered**.

- **Highest-Priority Remediation (`7.5` each):** `ART-17` (`GDPR`, `HIGH`) holds stale/failing evidence on `CTRL-GDPR-17`, and `EU-AI-14` (`EU_AI_ACT`, `MEDIUM`) has `NONE` mapped controls for `ai_governance`.
- **Compliant Baseline Control:** `ART-32` (`COMPLIANT_COVERED`) retains current evidence across encryption and IAM controls.
- **Approval Confirmation Prompt:** Confirm if you would like to update control gap owners and queue remediation tasks in GRC via your connected `ServiceNow` / GRC connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_MSA_Obligations_and_Compliance_Sample.docx`](../../../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx) (`145.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Regulatory Change & Control Gap Matrix (As Of 2026-11-10)

- **Articles Evaluated:** 3 | **Compliance Rate:** 33.3%
- **Uncovered Gaps:** 1 | **Failing/Stale Controls:** 1 | **Partial:** 0

| Article | Regulation | Severity | Status | Mapped Controls | Missing Domains | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | ---: |
| `ART-17` | GDPR | HIGH | `FAILING_OR_STALE_EVIDENCE` | CTRL-GDPR-17 | — | 7.5 |
| `ART-32` | GDPR | HIGH | `COMPLIANT_COVERED` | CTRL-ENC-01, CTRL-IAM-04 | — | 0.0 |
| `EU-AI-14` | EU_AI_ACT | MEDIUM | `UNCOVERED_GAP` | NONE | ai_governance | 7.5 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Renewal & Notice Deadline Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Renewal & Notice Deadline Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly executed contract renewal and obligation watch via scripts/obligation_calendar_builder.py. Compute exact opt-out notice deadlines (`renewal_date - notice_days`), surface urgent <=30 day windows and uncapped CPI escalators, and generate a draft reminder pack without emailing counterparties."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `articles`, `controls`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `controls` requires [`control_id`; `control_status` or `mapped_articles` or `domain`] | `articles` requires [`article_id` or `regulation`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_control_evidence_days` | `integer` | `365` | Maximum age of compliance control test evidence before flagging stale. |

See [`../../README.md`](../../README.md) for the `legal-contract-desk` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
