# Trap Guide: Absent Is Not Zero (`absent-is-not-zero`)

## Why This Trap Breaks Enterprise Agents

Enterprise connectors, REST endpoints, search APIs, and spreadsheet exports silently omit, truncate, or null-out records. An agent that equates **missing rows, partial pages, or empty search hits** with `0`, `"clean"`, or `"compliant"` produces confident, dangerously wrong executive reports.

## Six Canonical Failure Modes

1. **Silent Pagination Ceilings & Top-N Caps**
   - Connectors and REST endpoints often default to `page_size=25`, `limit=100`, `maxResults=50`, or `TOP 1000` without raising an error.
   - **Rule:** Always compare `len(fetched_records)` against API `total_count`, `nextPageToken`, `@odata.nextLink`, or `X-Total-Count`. If `total_available > len(fetched_records)` or `truncated == True`, emit a `TRUNCATION_WARNING` and state the exact coverage denominator (`"Analyzed 250 of 1,420 records (17.6%)"`) rather than extrapolating totals.

2. **Missing Row != Zero Balance (`0` vs `UNKNOWN`)**
   - If a cost center, store ID, or vendor has no matching row in a Goods Receipt (`GR`), Invoice (`IR`), or Inventory export, the true state is `UNMATCHED` or `UNREPORTED`, never `$0` spend or `0` shrinkage.
   - **Rule:** Preserve explicit sentinel states (`UNMATCHED`, `MISSING_FEED`, `PENDING_SYNC`) and report missing entity counts separately from true numeric zeros.

3. **Null / Blank Timestamp != "No Breach" or "Never Occurred"**
   - In ITSM, HRIS, and Clinical datasets, `resolved_at = null` means the incident is **still open**, not `MTTR = 0h`. Similarly, `last_review_date = null` on an SOP means **unverified / overdue review**, not "fresh".
   - **Rule:** Compute age against `now_utc` for open records (`resolved_at is None`) and exclude open items from closed-ticket average MTTR (report open backlog age separately).

4. **Parent-Child Double-Counting & Unreconciled Rollups**
   - Financial P&L exports and multi-level BOM files frequently include both summary rows (`is_summary=True`, `parent_account=None`) and leaf rows in the same table. Conversely, filtering out a child region makes summary totals appear clean while leaf rows fail materiality.
   - **Rule:** Never mix summary rows and leaf rows in a single `sum()`. Reconcile `sum(leaf_rows)` against reported parent subtotals and surface any variance as `HIERARCHY_VARIANCE`.

5. **Credit Memos Masking Overdue Debt or Spend**
   - Netting unapplied credit memos (`amount < 0`) into an `AR` or `AP` bucket hides `90+` day delinquent invoices behind a false low net balance.
   - **Rule:** Segregate negative credit memos into an isolated `unapplied_credits` ledger before aging positive receivables/payables.

6. **Incomplete Source Scope Reported as Universal Negative ("No Risks Found")**
   - Running a search across `Drive` only when the policy lives in `SharePoint`, or auditing `Production` tickets while `Security` tickets require an elevated scope, produces 0 hits.
   - **Rule:** When an authority check hits 0 documents or returns a `403`/`scope_missing` connector status, abstain and report `UNVERIFIED_INSUFFICIENT_SCOPE`, never `"No conflicts or exceptions exist."`

## Required Script Guardrails

Every analytical engine in this repository checks completeness metadata (`total_available`, `truncated`, `null_counts`, `missing_required_fields`) and surfaces `truncation_warnings` and `completeness_pct` in its JSON output and Markdown summary.
