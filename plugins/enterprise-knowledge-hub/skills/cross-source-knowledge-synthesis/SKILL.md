---
name: cross-source-knowledge-synthesis
description: "Synthesizes cross-source answers across Drive, SharePoint, and Confluence, ranking authority and detecting conflicting numerical/date claims with 100% citation verification. Use when reconciling conflicting internal docs or writing cited executive briefs. Don't use for single-policy jurisdiction lookups (use policy-sop-answering) or corpus metadata cleanup (use knowledge-gap-freshness-audit)."
created_by: gemini-agent-plugins
---

# Cross-Source Knowledge Synthesis

## Domain Context & Objective

Scores source authority and recency across multi-repo hits, flags conflicting numerical/date claims, and verifies 100% claim citation coverage. Cross-source authority scorer, numerical/date conflict auditor, and citation coverage verifier. Execute calculations via `scripts/citation_conflict_auditor.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack`.
- **Connector Tool Discovery:** Probe enabled 1P/MCP servers via `remote_cli mcp <connector> list-tools` before running Python engines.
- **Connector Fetch Guidance:** Retrieve authoritative policy docs, multi-tab Google Docs (includeTabsContent=true), SharePoint libraries, Confluence pages, and ServiceNow KB articles via remote_cli mcp before ranking authority and freshness in Python.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** `sources` requires [`id` or `doc_id` or `source_id`; `title` or `name`] | `draft_claims` requires [`claim_id` or `id`; `statement` or `text`] (matching top-level keys under `Expected Inputs` below).
- **Inspect Source Shape Directly in Python:** Call `read_xlsx_workbook(path)` (for `.xlsx`), `read_docx(path)` (for `.docx`), `read_csv_tsv(path)` (for `.csv`/`.tsv`), or `read_json_or_jsonl(path)` (for `.json`/`.jsonl`) in `pyrepl` — or inspect connector JSON keys directly — to see exact tab names, headers, and sample rows first.
- **Normalize Mismatched Fields in 5-10 Lines of Python:** Pass standard exports directly to `analyze(path_or_dict, config=cfg_path)`. When customer tab names, column headers, or nested objects differ, reshape rows into a canonical `payload` dict in a few lines of Python (calling `ask_question` only when two customer columns remain genuinely ambiguous).

## Step 3 — Run Deterministic Python Engine in `pyrepl` (or CLI) with Org Baseline Rules

1. Read `references/config.json` using `view_file` before scoring.
2. When `org_configured` is `false`, apply the bundled starter rubrics (`references/baselines/itsm-sla-severity-baseline.md`, `references/baselines/commercial-contract-baseline.md`) and stamp the top of every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

| Config Key | Type / Bounds | Default | Operational Role |
| :--- | :--- | :--- | :--- |
| `stale_review_days` | integer, 30..730 | `180` | Days after last_reviewed_at before a policy or SOP is flagged stale. |
| `recency_half_life_days` | integer, 30..1095 | `365` | Exponential decay half-life in days when ranking document freshness. |
| `duplicate_title_similarity_threshold` | number, 0.5..0.99 | `0.82` | SequenceMatcher title similarity ratio triggering near-duplicate review. |
| `min_citation_coverage_pct` | number, 50.0..100.0 | `100.0` | Required percentage of synthesized claims backed by verified source IDs. |
| `allow_draft_versions_in_answers` | boolean | `false` | Whether unpublished draft SOP versions (e.g. SharePoint minor 1.2) may be cited as authoritative. |
| `authoritative_source_weights` | object | `6 keys` | Authority weighting by document classification. |

Execute `scripts/citation_conflict_auditor.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/cross-source-knowledge-synthesis"),
            Path("skills/user-skills/cross-source-knowledge-synthesis"),
            Path("skills/enterprise-knowledge-hub"),
            Path("skills/user-skills/enterprise-knowledge-hub"),
            Path("."),
        )
        if (p / "scripts/citation_conflict_auditor.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/citation_conflict_auditor.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.citation_conflict_auditor import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass standard .docx/.xlsx/.json paths directly when structure already matches:
# payload = source_path_or_dict
# 2. Or inspect .docx/.xlsx tables in pyrepl and shape custom headers into canonical keys:
# doc = read_docx(Path("document.docx"))
# print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])
# payload = {"sources": [{"id": r.get("Source id"), "title": r.get("Source title")} for r in raw_rows]}
result = analyze(
    payload,
    config=cfg_path,
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/cross-source-knowledge-synthesis skills/user-skills/cross-source-knowledge-synthesis skills/enterprise-knowledge-hub skills/user-skills/enterprise-knowledge-hub skills/*; do
  [ -f "$d/scripts/citation_conflict_auditor.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/citation_conflict_auditor.py" --input payload.json --config "$SKILL_DIR/references/config.json" --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/citation_conflict_auditor.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `as_of_date`, `sources`, `draft_claims`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `summary`, `ranked_sources`, `conflicts`, `uncited_claims`, `invalid_citations`, `injection_flags`, `irm_warnings`, `truncation_warnings`; `summary` (`source_count`, `total_available`, `truncated`, `conflict_topic_count`, `draft_claim_count`, `citation_coverage_pct`) |
| **Eval & Safety Checks** | Detects truncated search results via total_available > source_count.; Quarantines embedded indirect prompt injection strings in excerpts.; Distinguishes unpublished minor draft versions from authoritative policies. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/google-workspace-traps.md`, `references/traps/sharepoint-onedrive-kql-traps.md`, `references/traps/untrusted-content-and-pii.md`.

- Read and apply `references/traps/absent-is-not-zero.md`, `references/traps/google-workspace-traps.md`, `references/traps/sharepoint-onedrive-kql-traps.md`, and `references/traps/untrusted-content-and-pii.md`.
- Treat `TRUNCATION_WARNING` and `UNVERIFIED_INSUFFICIENT_SCOPE` as abstention or caveat triggers rather than declaring "no conflicts".
- Creating private Google Docs drafts is auto-allowed; publishing Confluence pages or broadcasting email digests requires explicit user confirmation (HITL).

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`source_count`, `total_available`, `truncated`, `conflict_topic_count`, `draft_claim_count`, `citation_coverage_pct`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Publishing or overwriting authoritative SOP pages in Confluence or ServiceNow KB
  - Archiving or deleting stale documents in SharePoint or Google Drive
  - Broadcasting corpus hygiene audit digests to Slack channels or email distribution lists
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - Strict fail-closed abstention on 403 permission errors or zero jurisdiction matches (UNVERIFIED_INSUFFICIENT_SCOPE)
  - Published vs superseded/draft version authority precedence and departed-owner flagging
  - Contradictory cross-source numeric/SLA threshold surfacing rather than silent averaging
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Weekly Corpus Hygiene Audit", cron_expression="0 7 * * 1", time_zone="UTC", instruction="Run the weekly enterprise knowledge hygiene scan across Drive, SharePoint, and Confluence metadata exports. Execute scripts/corpus_hygiene_scanner.py against the latest corpus inventory and ticket-topic gap feed, highlight stale/unreviewed SOPs, departed owners, unpublished minor versions, and top unindexed support topics, and draft a remediation sheet for owner confirmation without archiving any file automatically.")`.
