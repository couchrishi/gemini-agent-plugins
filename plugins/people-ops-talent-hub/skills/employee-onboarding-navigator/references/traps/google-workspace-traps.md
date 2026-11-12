# Trap Guide: Google Workspace API & Export Traps (`google-workspace-traps`)

> **Applies to:** Google Workspace 1P connectors and exported Workspace files across Drive, Docs, Sheets, Slides, Gmail, Calendar, and Meet (`enterprise-knowledge-hub`, `executive-briefing-ops`, `legal-contract-desk`, `finance-variance-recon`, `people-ops-talent-hub`, `brand-campaign-studio`, `gsi-proposal-ip-factory`, `healthcare-clinical-regulatory`).

## 1. Executive Summary Matrix

| Trap ID | Workspace Surface | Silent Failure Pattern | Required API Parameter / Python Guard |
| :--- | :--- | :--- | :--- |
| `TRAP-GWS-01` | Google Drive | Shared Drives omitted; trashed & shortcut files misread | Pass `includeItemsFromAllDrives=true`, `supportsAllDrives=true`, `corpora=allDrives`, `trashed=false`; resolve `shortcutDetails.targetId` |
| `TRAP-GWS-02` | Google Docs | Multi-tab appendices & child tabs ignored | Pass `includeTabsContent=true`; traverse `tabs` & nested `childTabs` (`[Doc > Tab]`) |
| `TRAP-GWS-03` | Google Sheets | `"$1.5M"` display rounding, `"###"` truncation, hidden rows | Read `valueRenderOption=UNFORMATTED_VALUE` (+ `FORMULA` check); coerce `"12,500.00"` safely; filter status columns explicitly |
| `TRAP-GWS-04` | Google Slides | Speaker notes & grouped diagrams omitted | Inspect both `pageElements` text runs AND `notesPage` speaker notes for action commitments |
| `TRAP-GWS-05` | Gmail | Thread snippets hide latest attachments or mix `DRAFT`/`SENT` | Read chronological `messages[]` sorted by `internalDate`; verify `From` vs `Reply-To` spoofing |
| `TRAP-GWS-06` | Drive / Gmail / Cal | Unauthorized external emails, calendar invites, or ACL grants | Restrict autonomous execution to private drafts; require Agent Gateway (`Auto-Guardian`) and explicit user confirmation before external mutations |

## 2. Detailed Workspace API Traps & Walkthroughs

### Case A — Drive Shared Drives, Shortcuts & Trashed Files

- **Symptom:** Running a Workspace Drive search with default My Drive parameters skips organizational **Shared Drives** (`Finance Close`, `Legal Playbooks`, `SOP Vault`) and returns `0` matches, causing an agent to falsely conclude *"No corporate policy exists."*
- **Additional File-Level Hazards:**
  1. **Trashed Revisions:** Queries missing `trashed = false` retrieve superseded contracts sitting in Trash alongside live policies.
  2. **Drive Shortcuts (`mimeType == 'application/vnd.google-apps.shortcut'`):** Shortcut entries contain zero body text; you MUST follow `shortcutDetails.targetId` and inspect permissions on the destination object before reading.
  3. **Permission Denials (`403`):** If a Shared Drive denies read scope, emit `UNVERIFIED_INSUFFICIENT_SCOPE` under [absent-is-not-zero.md](absent-is-not-zero.md).

### Case B — Google Docs Multi-Tab Architecture (`includeTabsContent=true`)

- **Scenario:** Modern Google Docs organize PRDs, playbooks, and customer contracts across multiple tabs and nested child tabs. Tab 1 (`Summary`) states `Limitation of Liability: 12 months fees`, while **Tab 3 (`Data Processing Schedule > AI Addendum`)** embeds an override granting vendor rights to train foundation models on Customer Data!
- **Naive Failure:** Calling `documents.get` without `includeTabsContent=true` (or reading only `document.body`) parses Tab 1 exclusively and approves a `Score 9` AI-training blocker!
- **Guarded Traversal Rule:** Recursively walk `document["tabs"]` and `tab.get("childTabs", [])`, prefixing every extracted clause or obligation citation with `[<Doc Title> > <Tab Title>]`.

### Case C — Google Sheets Unformatted Formulas, Merged Headers & Hidden Rows

- **Numerical Precision Walkthrough:** A budget Sheet cell contains `=SUM(D2:D40)` evaluating to `1498762.487`, formatted in UI as `"$1.5M"` (or `"###"` if narrow, or `"#REF!"` if a cross-sheet `IMPORTRANGE` broke). Reading `FORMATTED_VALUE` loses `$1,237.51` and breaks GL tie-out tolerance (`$1.00`)!
- **API & Structural Safeguards:**
  1. Always fetch `valueRenderOption=UNFORMATTED_VALUE` for numbers and run a secondary `valueRenderOption=FORMULA` check when auditing spreadsheet formulas (`=SUM(...)` vs manual overrides).
  2. **Merged Cells:** Merged group headers populate only the top-left coordinate (`A2="EMEA"`), leaving `B2=""` (`None`). Forward-fill merged dimension headers in Python before grouping.
  3. **Hidden / Filtered Rows:** Sheets API `values.get` and `.csv` exports include hidden and filtered rows (`Status = "VOID"`, `Status = "ARCHIVED"`, `RowType = "Draft"`). Filter explicitly on status flags in Python RAM rather than assuming filter UI hides rows from API consumers.
  4. **Formatted Strings (`"12,500.00"`, `"$1,200.50"`, `"N/A"`):** Always use defensive parsing helpers so human-formatted Sheet/CSV cells never raise `ValueError`.

### Case D — Gmail Thread Granularity & BEC Spoofing Checks

- Fetching `threads.list` surfaces a single summary snippet from older messages and hides attached revised invoices, counter-redlines, or unapproved `DRAFT` replies sitting inside the thread.
- Inspect every message sorted by `internalDate` ascending, verify `labelIds` (`SENT` vs `DRAFT`), and validate raw `From` vs `Reply-To` headers before accepting vendor remittance changes (`FRAUD_HOLD_BANK_CHANGE`).

## 3. Workspace Execution & HITL Boundary Rules

1. **Read-Only Discovery First:** Pull Workspace Sheets/Docs/Gmail records into Python RAM (`pyrepl` or CLI `--input`) rather than pasting multi-hundred-row CSV text directly into prompt tokens.
2. **Private Drafts vs. External Sends:** Creating private working Google Docs or local Markdown summaries avoids external side effects; creating or sending external messages stays governed by Workspace connector scopes.
3. **Mandatory External Mutation Hold:** Any action visible outside the user's private sandbox — sending Gmail/Outlook messages, modifying external Calendar invites, or changing Drive sharing (`anyoneWithLink`) — requires Agent Gateway (`Auto-Guardian`) approval and explicit human confirmation with full recipient and diff preview.

## 4. Programmatic Sheet / CSV Coercion Template

```python
def parse_workspace_number(val: object, default: float = 0.0) -> float:
    """Safely coerce Google Sheets unformatted floats or comma/currency formatted strings."""
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip().replace(",", "").replace("$", "")
    if not text or text.upper() in {"N/A", "NA", "#N/A", "#REF!", "#VALUE!", "#DIV/0!", "-"}:
        return default
    return float(text)
```

## 5. Exact Workspace Query & Parsing Specifications

| Surface | API Call / Endpoint Flag | Default Trap Behavior | Mandatory Safe Parameter |
| :--- | :--- | :--- | :--- |
| **Drive `files.list`** | `supportsAllDrives`, `includeItemsFromAllDrives`, `corpora` | Queries My Drive only (`corpora='user'`), drops Shared Drives | Set `corpora='allDrives'`, `supportsAllDrives=true`, `includeItemsFromAllDrives=true`, `trashed = false` |
| **Drive Shortcuts** | `mimeType='application/vnd.google-apps.shortcut'` | Body extraction returns `0 bytes` on shortcut pointer | Inspect `shortcutDetails.targetId` and fetch referenced target file directly |
| **Docs `documents.get`** | `includeTabsContent` | Returns Tab 1 `body` only; drops Tab 2+ exceptions/playbooks | Set `includeTabsContent=true`; recurse `tabs[].childTabs[]` |
| **Sheets `values.get`** | `valueRenderOption` | `FORMATTED_VALUE` returns `"$1.5M"`, `"###"`, or `""` | Pull `UNFORMATTED_VALUE` for math + `FORMULA` for audit integrity |
| **Gmail `messages.get`** | `threads.list` vs `messages.get` | Snippet summarizes stale message #1; misses latest attachment | Sort individual `messages` by `internalDate`; check `SENT` vs `DRAFT` labels |
| **Slides `presentations.get`** | `slides[].pageElements` | Skips speaker notes & nested table cells | Traverse `notesPage` elements + table cell runs cleanly |

## 6. Pre-Delivery Workspace Hygiene Checklist

1. Cite sources accurately using `[Doc Title > Tab Name]` or `[Sheet Title > Tab Name!Range]` rather than ambiguous filenames.
2. Forward-fill merged dimension columns and strip `"VOID"` / `"Draft"` / `"Archived"` rows before aggregating Sheet exports.
3. Redact sensitive customer/employee PII extracted from Docs/Gmail/Forms per [untrusted-content-and-pii.md](untrusted-content-and-pii.md).
4. Hold every external email send, external Calendar update, or Drive permission share behind Agent Gateway (`Auto-Guardian`) and explicit human confirmation with exact diff/recipient preview.
5. Propagate `incompleteSearch` or `nextPageToken` truncation telemetry into `truncation_warnings` rather than implying full-corpus scan coverage.

## 7. Multi-Tab & Shortcut Inspection Pseudo-Flow

```python
def extract_all_doc_tabs(doc: dict) -> list[tuple[str, dict]]:
    """Recursively flatten Google Doc tabs and childTabs so appendices are never dropped."""
    collected: list[tuple[str, dict]] = []
    def _walk(nodes: list[dict], prefix: str = "") -> None:
        for tab in nodes or []:
            title = tab.get("tabProperties", {}).get("title") or "Untitled Tab"
            label = f"{prefix} > {title}" if prefix else title
            if "documentTab" in tab:
                collected.append((label, tab["documentTab"]))
            _walk(tab.get("childTabs", []), label)
    _walk(doc.get("tabs", []))
    return collected
```
