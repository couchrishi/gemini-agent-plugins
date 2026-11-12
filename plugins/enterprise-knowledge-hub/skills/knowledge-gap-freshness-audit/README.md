# Knowledge Gap & Freshness Audit (`knowledge-gap-freshness-audit`)

Audits enterprise Drive, SharePoint, and Confluence inventories for overdue review dates, null timestamps, departed owners, near-duplicate titles, and unindexed ticket gaps. Deterministic computation executes via [`scripts/corpus_hygiene_scanner.py`](scripts/corpus_hygiene_scanner.py). Domain guards enforced: Null last_reviewed_at timestamps are classified as unverified_null_reviews, never fresh; Never archives or deletes documents without explicit HITL approval. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Intranet & Confluence Owner**: Triggered when running Monday corpus hygiene sweeps before quarterly internal audits; flags stale articles (>180d), departed owners, and near-duplicate titles before archiving.
- **Support Documentation Manager**: Triggered when eliminating conflicting duplicate troubleshooting runbooks; consolidates redundant articles while gating SharePoint deletions behind human sign-off.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`knowledge-gap-freshness-audit.zip`](../../../../dist/skills/knowledge-gap-freshness-audit.zip) (or the full department bundle [`enterprise-knowledge-hub.zip`](../../../../dist/bundles/enterprise-knowledge-hub.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx).
4. Ask naturally in chat or invoke directly with `/knowledge-gap-freshness-audit` or `@knowledge-gap-freshness-audit`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.corpus_hygiene_scanner import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"documents": [{"doc_id": r.get("Source doc_id"), "title": r.get("Source title")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/enterprise-knowledge-hub/skills/knowledge-gap-freshness-audit/scripts/corpus_hygiene_scanner.py \
  --input examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx \
  --config plugins/enterprise-knowledge-hub/skills/knowledge-gap-freshness-audit/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `corpus_hygiene_scanner.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack` via `remote_cli mcp`):** "Run a quarterly hygiene audit across our SharePoint SOP library and ServiceNow L1 ticket topics to find stale SOPs and top undocumented issues."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit the Drive Policy Inventory Sheet in Shared Drives for Cymbal Financial docs owned by departed employees or duplicated across folders."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx) and ask: "Audit the attached `Apex_Policy_SOP_and_KB_Sample.docx` knowledge inventory to identify stale documents past the 180-day review window, departed owners, near-duplicate pages, and top unresolved ticket topics lacking documentation."

## Sample Response

### What You See in Gemini Enterprise Chat

Reviewing `4` knowledge articles in `Apex_Policy_SOP_and_KB_Sample.docx` flagged `2` overdue pages exceeding the review threshold, `2` articles with departed or missing owners, `1` near-duplicate pair, and `3` undocumented ticket topics (`vpn`, `mfa reset`, `sso`).

- **Corpus Hygiene Risks:** `2 / 4` articles (`50.0%`) require overdue review and owner reassignment before upcoming internal compliance audits.
- **Undocumented Ticket Gaps:** Customer/IT support queues logged recurring volume for `vpn`, `mfa reset`, and `sso` with `0` verified self-service guides.
- **Approval Confirmation Prompt:** Confirm if you would like to archive duplicate/stale records via your connected `Microsoft 365 (SharePoint)` or `Google Drive` connector or publish gap-remediation pages via your connected `Confluence` connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx) (`154.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Corpus Hygiene & Knowledge Gap Audit

- **Documents Scanned:** 4 / 4
- **Overdue Review (>Threshold):** 2
- **Null / Unverified Review Date:** 0
- **Departed / Missing Owner:** 2
- **Near-Duplicate Pairs:** 1
- **Unindexed Ticket Topics:** 3

## Top Unindexed Ticket Topics

| Topic | Ticket Volume |
| :--- | ---: |
| vpn | 1 |
| mfa reset | 1 |
| sso | 1 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Corpus Hygiene Audit` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Corpus Hygiene Audit" on cron `0 7 * * 1` (`UTC`) with instruction: "Run the weekly enterprise knowledge hygiene scan across Drive, SharePoint, and Confluence metadata exports. Execute scripts/corpus_hygiene_scanner.py against the latest corpus inventory and ticket-topic gap feed, highlight stale/unreviewed SOPs, departed owners, unpublished minor versions, and top unindexed support topics, and draft a remediation sheet for owner confirmation without archiving any file automatically."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `documents`, `ticket_topics`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `documents` requires [`doc_id` or `id`; `title`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `stale_review_days` | `integer` | `180` | Days after last_reviewed_at before a policy or SOP is flagged stale. |
| `duplicate_title_similarity_threshold` | `number` | `0.82` | SequenceMatcher title similarity ratio triggering near-duplicate review. |

See [`../../README.md`](../../README.md) for the `enterprise-knowledge-hub` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
