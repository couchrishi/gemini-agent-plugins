# Starter Baseline: Finance Materiality, 3-Way Match & Aging Rubric (`finance-materiality-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, stamp the deliverable header verbatim with:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. P&L Budget & Variance Materiality Thresholds

| Metric | Standard Baseline Default | Escalation Condition | Override Key in `config.json` |
| :--- | :--- | :--- | :--- |
| **Line-Item Dollar Materiality** | `$25,000` | `abs(actual - benchmark) >= 25000` | `materiality_amount_threshold` |
| **Line-Item Percent Materiality** | `10.0%` | `abs(variance_pct) >= 10.0` (when `abs(variance) >= 5000`) | `materiality_pct_threshold` |
| **Hierarchy Reconciliation Tolerance** | `$1.00` | Flag any `abs(parent_total - sum(leaf_rows)) > 1.00` | `hierarchy_tolerance_amount` |
| **Minimum Reporting Currency** | `USD` | Convert multi-currency lines using `fx_rates` table | `default_currency` |

## 2. Accounts Payable 3-Way Match & GR/IR Clearing Tolerances

| Control Check | Standard Baseline Default | Action When Breached | Override Key in `config.json` |
| :--- | :--- | :--- | :--- |
| **Unit Price Tolerance (%)** | `2.0%` (`0.02`) | Hold payment; route to Procurement Buyer (`PRICE_VARIANCE`) | `price_tolerance_pct` |
| **Unit Price Hard Dollar Cap** | `$500.00` | Even if `< 2%`, variances `> $500` require AP Manager sign-off | `price_tolerance_abs` |
| **Quantity Over-Receipt / Over-Bill Tolerance** | `0.0%` (strict `Invoice_Qty <= GR_Qty <= PO_Qty`) | Hold excess quantity (`QTY_VARIANCE` / `MISSING_GRN`) | `qty_tolerance_pct` |
| **GR/IR Unmatched Aging Threshold** | `60 days` | Escalate accrued GR/IR imbalance older than 60 days | `gr_ir_aging_threshold_days` |
| **Duplicate Invoice Detection** | Exact `(vendor_id, invoice_number)` or `(vendor_id, amount, date +/- 3d)` | Immediate `DUPLICATE_SUSPECT` payment block | `duplicate_date_window_days` |

## 3. Accounts Receivable Aging & Collections Priority

- **Standard Aging Buckets:** `Current` (`<= 0` days past due), `1-30`, `31-60`, `61-90`, `90+` days past due.
- **Credit Memo Isolation Rule:** Negative invoice rows (`amount < 0` or `doc_type == 'CREDIT_MEMO'`) are NEVER netted into `90+` buckets; isolate into `unapplied_credits` and report separately.
- **Collections Escalation Threshold:** Single customer `90+` overdue balance `>= $10,000` (`ar_escalation_90_plus_threshold`) triggers formal Dunning Hold / Account Executive escalation.
