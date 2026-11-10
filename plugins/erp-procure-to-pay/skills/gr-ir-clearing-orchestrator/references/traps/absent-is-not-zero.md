# Trap Guide: Absent Is Not Zero (`absent-is-not-zero`)

> **Applies to:** All cross-system reconciliation, BI analytics, ITSM SLA, retail inventory, HRIS, credit, and compliance engines. Missing records, partial API pages, empty search results, or `null` fields must never coerce silently to `$0`, `0%`, or `"Compliant"`.

## 1. Executive Summary Matrix

| Trap ID | Silent Failure Pattern | API / Export Symptom | Required Programmatic Guard |
| :--- | :--- | :--- | :--- |
| `TRAP-ANZ-01` | Pagination ceiling / top-N truncation | `len(rows) == 25`, `50`, `100`, `500`, or `1000` with `nextPageToken` or `total_available > len(rows)` | Emit `TRUNCATION_WARNING`; compute `completeness_pct` against `total_available` |
| `TRAP-ANZ-02` | Missing join row treated as `0` balance | PO has no Goods Receipt (`GR`), store has `pos_poll_status="MISSING"` | Emit sentinel `MISSING_GRN` / `UNPOLLED`; separate `UNKNOWN` from numeric `0` |
| `TRAP-ANZ-03` | Null resolution timestamp treated as `0h` MTTR | Open incident with `resolved_at: null` or policy with `last_reviewed_at: null` | Branch open backlog (`now - opened_at`) away from closed MTTR; flag unreviewed as overdue |
| `TRAP-ANZ-04` | Mixed summary and leaf rows summed together | P&L table mixes `row_type="summary"` and `row_type="leaf"` | Sum leaf rows only; reconcile against reported parent subtotal (`HIERARCHY_VARIANCE`) |
| `TRAP-ANZ-05` | Credit memos masking `90+` day delinquencies | `open_amount_usd < 0` netted against `90+` overdue AR invoices | Isolate credits into `unapplied_credits` before computing `90+` collections exposure |
| `TRAP-ANZ-06` | Permission/scope gap reported as `"No Issues"` | Missing connector scope returns HTTP `403` or `0` docs from partial corpus | Abstain and report `UNVERIFIED_INSUFFICIENT_SCOPE`; never claim zero findings |

## 2. Numerical Before-vs-After Failure Walkthroughs

### Case A — Silent Pagination Truncation on AP Invoice Batch

- **Scenario:** An SAP OData `/API_SUPPLIERINVOICE_PROCESS_SRV` query returns the default first page of `200` open invoices totaling `$1.42M`, while response envelope metadata reports `total_available = 1150` (`truncated = true`).
- **Naive Failure:** An unguarded script sums the `200` visible rows and certifies: *"Total open AP exposure is `$1.42M` across the enterprise."* Only `17.4%` of the ledger was examined, understating open payables by roughly `$6.7M`.
- **Guarded Outcome:** Engine inspects `truncated` and `total_available`, populates `truncation_warnings` with `"Analyzed 200 of 1,150 records (17.4% completeness); remaining pages uninspected"`, and blocks portfolio-level certification.

### Case B — Parent-Child Rollup Double-Counting in Departmental P&L

- **Scenario:** A monthly ERP GL export includes both parent subtotal row `OPEX` (`row_type = "summary"`, `actual_local = 310,000`) and its child leaf accounts `6100 Cloud` (`210,000`) and `6200 Travel` (`100,000`), evaluated against a `$250,000` OpEx budget.
- **Naive Failure:** Summing every row in `lines` produces `$620,000` (`2x` overstatement) and fabricates a `$370,000` (`+148%`) budget overrun instead of the actual `$60,000` (`+24%`) variance.
- **Guarded Outcome:** Filter strictly on `row_type == "leaf"`, check `abs(310000 - (210000 + 100000)) <= hierarchy_tolerance_amount ($1.00)`, and surface any residual discrepancy explicitly as `HIERARCHY_VARIANCE`.

### Case C — Store Shrinkage on Unpolled POS Registers

- **Scenario:** Store `STR-109` failed nightly POS polling (`pos_poll_status = "MISSING"`), showing `book_on_hand_qty = 12` (`$1,440` retail cost) and `0` recorded sales over `9` days (`zero_scan_days_threshold = 5`).
- **Naive Failure:** Treating missing POS poll telemetry as zero consumer purchases labels `$1,440` of inventory as phantom shrinkage / theft and routes Store Loss Prevention to audit an intact shelf.
- **Guarded Outcome:** Check `pos_poll_status` before zero-scan detection, isolate `STR-109` under `UNPOLLED_POS_SKIPPED` (`unpolled_pos_skipped = 1`), and exclude unpolled stores from shrink rankings until polling recovers.

### Case D — Unapplied Credit Memos Hiding `90+` Day AR Exposure

- **Scenario:** Customer `Northstar Retail` holds an undisputed `$45,000` invoice `132` days past due alongside a `-$38,000` unapplied credit memo (`doc_type = "CREDIT_MEMO"`).
- **Naive Failure:** Netting both rows shrinks the customer's `90+` aging bucket to `$7,000` — slipping underneath the `$10,000` collections escalation floor (`ar_escalation_90_plus_threshold`) and suppressing a priority dunning review.
- **Guarded Outcome:** Segregate negative adjustments and `CREDIT_MEMO` lines into `unapplied_credits` (`$38,000`), keep gross `90+` overdue exposure at `$45,000`, and flag the account for collections + credit memo offset review.

### Case E — Null Timestamps & Unpolled Scope Checks

- **Null Incident `resolved_at`:** Open P1 tickets with `resolved_at = null` must NEVER enter closed-ticket average MTTR (`0h` distortion). Compute age against `now_utc` (`as_of_time`) and report `open_backlog_count` alongside `max_open_age_hours`.
- **Null SOP `last_reviewed_at`:** Unreviewed SOPs with `last_reviewed_at = null` represent stale governance risk (`UNKNOWN_UNVERIFIED`), never freshly reviewed documentation.
- **Partial Connector Scopes:** When `Drive`, `SharePoint`, or `ServiceNow` returns HTTP `403` or `missing_scopes`, return `UNVERIFIED_INSUFFICIENT_SCOPE` rather than claiming `"No exceptions or policy violations found."`

## 3. Connector & Schema Detection Checklist

1. **Inspect pagination & count envelopes first:** Check `nextPageToken`, `@odata.nextLink`, `nextRecordsUrl`, `X-Total-Count`, `has_more`, `done`, `totalSize`, and `total_available`.
2. **Preserve three-state logic (`PRESENT`, `TRUE_ZERO`, `UNKNOWN`):**
   - Never apply `val or 0.0` blindly when `val is None` indicates missing telemetry, open state, or withheld access (`resolved_at`, `actual_total_minutes`, `physical_count_qty`).
   - Run numeric coercion helpers (`safe_float` / `safe_int`) only after testing explicit `None` and sentinel status branches.
3. **Require numerator and denominator parity:** Check whether denominators cover the identical time window and entity cohort (`active_fte`, `polled_stores`, `closed_tickets`) as numerators before rendering percentages.

## 4. Deterministic Programmatic Assertions (`Python` & `CEL`)

Every computation engine in this repository validates payload completeness inside `analyze()`:

```python
def collect_truncation_warnings(data: dict, analyzed_count: int) -> list[str]:
    warnings: list[str] = []
    total_raw = data.get("total_available")
    total = int(float(total_raw)) if isinstance(total_raw, (int, float)) else 0
    if bool(data.get("truncated", False)):
        if total > 0:
            pct = (analyzed_count / total) * 100.0
            warnings.append(
                f"TRUNCATION_WARNING: Input flagged truncated; analyzed {analyzed_count} of {total} records ({pct:.1f}%)."
            )
        else:
            warnings.append("TRUNCATION_WARNING: Input flagged truncated; totals reflect partial corpus only.")
    elif total > analyzed_count:
        pct = (analyzed_count / total) * 100.0
        warnings.append(
            f"TRUNCATION_WARNING: Analyzed {analyzed_count} of {total} total_available records ({pct:.1f}%)."
        )
    return warnings
```

- **CEL Policy Integration:** Pair completeness checks with `policy.cel` guardrails (`pnl.hierarchy_break_count == 0`, `absent_scope_error == false`) before permitting executive publication or downstream ERP release.
- **Markdown Rendering Standard:** Surface non-empty `truncation_warnings` immediately below the baseline banner so reviewers see exact coverage denominators prior to acting on any metric.

## 5. Exact Envelope Fields & Verification Checklist Across Connectors

| Connector / Format | Pagination / Truncation Envelope Key | Count / Completeness Signal | Fallback Action When Partial |
| :--- | :--- | :--- | :--- |
| **SAP OData v2 / v4** | `__next` / `@odata.nextLink` | `@odata.count` / `__count` | Fetch remaining pages or flag `truncated=true` |
| **BigQuery / Snowflake** | `pageToken`, `maxResults` | `totalRows`, `jobStatistics` | Paginate result cursors; assert row count matches |
| **Salesforce REST SOQL** | `nextRecordsUrl` | `done == false`, `totalSize` | Loop `queryMore` until `done == true` |
| **ServiceNow Table API** | `sysparm_offset`, `sysparm_limit` | `X-Total-Count` response header | Paginate until `len(rows) == X-Total-Count` |
| **Jira Cloud Search v3** | `startAt`, `maxResults` | `total`, `isLast` | Loop `startAt += len(issues)` until `total` |
| **Microsoft Graph / M365** | `@odata.nextLink`, `from`/`size` | `moreResultsAvailable`, `total` | Iterate `@odata.nextLink`; never assume top 25 is exhaustive |
| **Google Workspace Drive** | `nextPageToken` | `incompleteSearch == true` | Pass `corpora=allDrives`, check `incompleteSearch` |

Before certifying any cross-system total or `"0 findings"` verdict, confirm:
1. `len(truncation_warnings) == 0` OR executive header prints the exact coverage percentage (`analyzed / total_available`).
2. Zero missing-join entities (`MISSING_GRN`, `UNPOLLED`, `NO_EVIDENCE`) were coerced into `$0.00` or `100% compliant`.
3. Open items with `null` resolution/review timestamps remain isolated from closed SLA and freshness medians.
