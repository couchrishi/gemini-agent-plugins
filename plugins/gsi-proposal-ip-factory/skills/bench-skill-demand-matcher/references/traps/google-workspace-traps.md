# Trap Guide: Google Workspace API & Export Traps (`google-workspace-traps`)

## Common Pitfalls Across Drive, Docs, Sheets & Gmail

1. **Google Drive Shared Drive vs. My Drive Scoping**
   - Drive search without `includeItemsFromAllDrives=true` and `supportsAllDrives=true` silently misses Shared Drives (`corpora='allDrives'`), returning incomplete results and triggering false negatives.
   - **Trashed & Shortcut Traps:** Always include `trashed = false` in query predicates and resolve `application/vnd.google-apps.shortcut` (`shortcutDetails.targetId`) rather than treating shortcut metadata as file content.

2. **Google Docs Multi-Tab Structure (`includeTabsContent=true`)**
   - Modern Google Docs organize PRDs, playbooks, and RFCs across **multiple document tabs and child tabs**. Reading only `document.body` returns just Tab 1 and silently omits appendix tables, clause matrices, or regional exceptions stored on Tab 2+.
   - **Mitigation:** Always enumerate all `tabs` (and nested `childTabs`) recursively, recording `[Doc Title > Tab Name]` in citations.

3. **Google Sheets Formatted Display Values vs. Unformatted Formulas**
   - `valueRenderOption=FORMATTED_VALUE` returns `"$1.2M"` or `"###"` (truncated column width) or `""` when formulas error (`#N/A`, `#REF!`), whereas `UNFORMATTED_VALUE` returns raw float precision (`1248392.41`) and `FORMULA` exposes `=SUM(...)` vs hardcoded overrides.
   - **Merged Cells & Hidden Rows:** Sheet exports flatten merged headers into the top-left cell and leave sibling cells empty (`None`), and standard CSV exports include hidden/filtered-out rows (`"Draft"` or `"Excluded"` rows). Always inspect status/filter columns explicitly in Python.

4. **Gmail Thread vs. Message Granularity**
   - Searching by `threads.list` groups older messages with newer replies under one thread snippet, causing agents to miss the latest attachment or read an earlier unapproved draft state.
   - **Mitigation:** Always inspect individual `messages` sorted chronologically by `internalDate`, distinguish `SENT` vs `DRAFT` labels, and verify sender authentication (`From` header spoofing vs verified domain).

5. **Workspace Permissions Before External Sharing**
   - Mutating Drive permissions (`anyoneWithLink`) or sending external Gmail/Calendar invites requires explicit `hitl_gated_mutations` approval under `policy.cel`. Default to drafting (`gmail_create_draft`, creating private Docs/Sheets in user workspace) unless explicitly approved.
