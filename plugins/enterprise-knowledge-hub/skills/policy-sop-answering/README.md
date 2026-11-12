# Policy & SOP Answering (`policy-sop-answering`)

Answers policy and SOP questions by filtering clauses strictly by jurisdiction, legal entity, effective date, and published status, enforcing abstention on missing coverage. Deterministic computation executes via [`scripts/policy_scope_matcher.py`](scripts/policy_scope_matcher.py). Domain guards enforced: Rejects superseded, archived, expired, future-dated, and unpublished draft clauses; Abstains explicitly when no active clause matches jurisdiction and entity. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **HR & Workplace Partner**: Triggered when answering country- or entity-specific leave, stipend, or SOP inquiries; delivers active effective-dated clauses or formally abstains when jurisdiction coverage is absent.
- **Regional Compliance Officer**: Triggered when checking whether draft or superseded regional policies leaked into self-service; isolates superseded minor drafts (`v1.x`) from currently effective (`published`) standards.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`policy-sop-answering.zip`](../../../../dist/skills/policy-sop-answering.zip) (or the full department bundle [`enterprise-knowledge-hub.zip`](../../../../dist/bundles/enterprise-knowledge-hub.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx).
4. Ask naturally in chat or invoke directly with `/policy-sop-answering` or `@policy-sop-answering`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.policy_scope_matcher import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"clauses": [{"clause_id": r.get("Source clause_id"), "text": r.get("Source text")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/enterprise-knowledge-hub/skills/policy-sop-answering/scripts/policy_scope_matcher.py \
  --input examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx \
  --config plugins/enterprise-knowledge-hub/skills/policy-sop-answering/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `policy_scope_matcher.py`: `--query`, `--jurisdiction`, `--entity`, `--as-of-date`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack` via `remote_cli mcp`):** "What is Apex Manufacturing's parental leave duration in Singapore as of 2026-11-10? Check SharePoint and Drive policies."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Using our HR Policy Google Sheet in Drive, tell me the meal reimbursement cap for Brazil contractors."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx) and ask: "Check the attached `Apex_Policy_SOP_and_KB_Sample.docx` policy pack as of `2026-11-10` to determine which regional travel or expense SOP clauses are currently effective, filter out superseded drafts and future-dated amendments, and confirm whether an official answer can be issued."

## Sample Response

### What You See in Gemini Enterprise Chat

Out of `4` evaluated policy clauses in `Apex_Policy_SOP_and_KB_Sample.docx` as of `2026-11-10`, only `1` published clause (`POL-TRV-US-32`, US Corporate Travel Lodging Standard `v3.2`, effective `2026-01-01`, score `1.4000`) is active after rejecting `3` superseded or out-of-scope entries (`abstained: False`).

- **Active Policy Match:** `POL-TRV-US-32` (`US`, version `3.2`) passed effective-date, entity, and publish-state gates cleanly.
- **Superseded & Scope Filtering:** `3` draft, retired, or out-of-window policy entries were excluded automatically so stale limits never leak into employee guidance.
- **Approval Confirmation Prompt:** Confirm if you would like to publish the verified `POL-TRV-US-32` guidance page via your connected `Confluence` connector (gated by `Auto-Guardian`) or broadcast the update to HR stakeholders via your connected `Slack` or `Gmail` / `Outlook` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx) (`147.8 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Scoped Policy & SOP Determination

- **Jurisdiction / Entity / As-Of:** `US` / `all` / `2026-11-10`
- **Active Matching Clauses:** 1 (Rejected: 3)
- **Abstained:** `False` (`NONE`)

| Clause ID | Policy | Version | Jurisdiction | Effective | Score |
| :--- | :--- | :--- | :--- | :--- | ---: |
| `POL-TRV-US-32` | US Corporate Travel Lodging Standard | 3.2 | US | 2026-01-01 | 1.4000 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Corpus Hygiene Audit` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Corpus Hygiene Audit" on cron `0 7 * * 1` (`UTC`) with instruction: "Run the weekly enterprise knowledge hygiene scan across Drive, SharePoint, and Confluence metadata exports. Execute scripts/corpus_hygiene_scanner.py against the latest corpus inventory and ticket-topic gap feed, highlight stale/unreviewed SOPs, departed owners, unpublished minor versions, and top unindexed support topics, and draft a remediation sheet for owner confirmation without archiving any file automatically."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `query`, `jurisdiction`, `as_of_date`, `clauses`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `clauses` requires [`clause_id` or `id`; `text` or `clause_text` or `title`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `stale_review_days` | `integer` | `180` | Days after last_reviewed_at before a policy or SOP is flagged stale. |
| `allow_draft_versions_in_answers` | `boolean` | `False` | Whether unpublished draft SOP versions (e.g. SharePoint minor 1.2) may be cited as authoritative. |

See [`../../README.md`](../../README.md) for the `enterprise-knowledge-hub` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
