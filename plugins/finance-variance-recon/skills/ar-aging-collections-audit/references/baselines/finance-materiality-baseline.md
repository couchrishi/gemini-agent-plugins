# Starter Baseline: Finance Materiality, 3-Way Match & Cross-Domain Monetary Rubric (`finance-materiality-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, every deliverable MUST carry this exact top banner verbatim:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. P&L Budget, GL Hierarchy & BI Materiality Thresholds (`finance-variance-recon`, `conversational-bi-analyst`)

| Control Check | Standard Baseline Default | Escalation Condition | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- |
| **Line-Item Dollar Materiality** | `$25,000.00 USD` | `abs(actual_usd - budget_usd) >= 25000.0` | `materiality_amount_threshold`, `default_currency` |
| **Line-Item Percent Materiality** | `10.0%` | `abs(variance_pct) >= 10.0%` | `materiality_pct_threshold` |
| **GL Hierarchy Reconciliation Tolerance** | `$1.00 USD` | Flag `HIERARCHY_VARIANCE` if `abs(parent - sum(leaf)) > 1.00` | `hierarchy_tolerance_amount` |
| **BI Z-Score / Sample / Cost Guard** | `|z| >= 2.0`, `n >= 30`, `<= 500 GB` scan, `<= 15%` nulls | Alert outlier segments; block full scans `> 500 GB`; warn `n < 30` | `zscore_anomaly_threshold`, `min_sample_size_guard`, `max_query_scan_gb`, `max_null_rate_warn_pct` |

## 2. Accounts Payable 3-Way Match, GR/IR Clearing & AR Aging (`finance-variance-recon`, `erp-procure-to-pay`)

| Control Check | Standard Baseline Default | Deterministic Exception / Hold Action | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- |
| **AP Unit Price Tolerance (%)** | `2.0%` (`0.02`) | Hold payment (`PRICE_VARIANCE`); route to Procurement Buyer | `price_tolerance_pct` |
| **AP Unit Price Hard Dollar Cap** | `$500.00` | Even when `% <= 2%`, deltas `> $500` require AP Manager sign-off | `price_tolerance_abs` |
| **Quantity Over-Receipt Tolerance** | `0.0%` (`Invoice <= GR <= PO`) | Hold excess billing (`QTY_VARIANCE`) or missing receipt (`MISSING_GRN`) | `qty_tolerance_pct` |
| **Duplicate Invoice Window** | Same `(vendor, inv_num)` OR `(vendor, amt, +/- 3 days)` | Immediate `DUPLICATE_BLOCK` payment freeze | `duplicate_date_window_days` |
| **GR/IR Unmatched Aging & Tolerance** | `60 days`, `$5.00` clearing tolerance | Escalate uninvoiced GR or unreceived IR aging `> 60 days` | `gr_ir_aging_threshold_days`, `clearing_tolerance_usd` |
| **AR Collections Escalation Floor** | `>= $10,000` in `90+` days past due | Escalate Dunning Hold; NEVER net negative credit memos silently | `ar_escalation_90_plus_threshold` |
| **Tariff / Single-Source / PPV Guard** | `8%` capital, `$45` defect cost, `70%` vendor cap, `5%` PPV | Flag tariff concentration & purchase price variance anomalies | `annual_cost_of_capital_pct`, `defect_cost_per_unit_usd`, `max_single_source_share_pct`, `ppv_alert_threshold_pct` |

## 3. Operational Economics Across Industrial, Retail, Marketplace & Telco Plugins

Several industry operations plugins share financial thresholds from this rubric when `org_configured` is `false`:

| Plugin ID | Financial / Shrink / Economics Thresholds | Starter Baseline Defaults | `config.json` Override Keys |
| :--- | :--- | :--- | :--- |
| **`industrial-shopfloor-maintenance`** | Spares stocking Z-score & CapEx ROI payback | `service_level_z = 1.65`, `max_capex_payback_years = 2.0`, `lot_spike_multiplier = 2.0` | `service_level_z`, `max_capex_payback_years`, `lot_spike_multiplier` |
| **`retail-store-merchandising`** | Phantom shrink, promo ROI floor & OTIF chargeback | `zero_scan_days_threshold = 5`, `min_book_qty_for_phantom = 4`, `high_shrink_usd_threshold = 250.0`, `min_acceptable_promo_roi = 0.15`, `target_otif_pct = 95.0` | `zero_scan_days_threshold`, `min_book_qty_for_phantom`, `high_shrink_usd_threshold`, `min_acceptable_promo_roi`, `target_otif_pct`, `in_full_tolerance_pct`, `on_time_grace_minutes` |
| **`marketplace-superapp-ops`** | Price sanity bounds, payout HITL & PSP tie-out | `min_images = 2`, `low_price_ratio_threshold = 0.35`, `high_price_multiplier_threshold = 4.0`, `high_value_payout_hitl_usd = 50.0`, `default_commission_rate_pct = 15.0`, `settlement_variance_tolerance_usd = 5.0` | `min_images`, `low_price_ratio_threshold`, `high_price_multiplier_threshold`, `high_value_payout_hitl_usd`, `default_commission_rate_pct`, `settlement_variance_tolerance_usd` |
| **`telco-noc-field-dispatch`** | High-value B2B enterprise circuit MRC priority | `high_value_mrc_usd = 2500.0`, `provisioning_sla_days = 15` | `high_value_mrc_usd`, `provisioning_sla_days` |

## 4. Mandatory Accounting & Reconciliation Rules

1. **SAP `TCURX` & `SHKZG` Enforcement:** Always normalize 0-decimal (`JPY`/`KRW`) and 3-decimal (`KWD`/`BHD`) SAP table values and invert `'H'` credit signs prior to tolerance checks.
2. **FX vs Operational Isolation:** Separate constant-currency operational budget variance from spot-FX translation variance in executive P&L bridges.
3. **BEC Bank-Change & Negative Credit Isolation:** Never net negative AR credit memos against `90+` overdue receivables, and never auto-release an AP invoice carrying `bank_account_changed = True`.

## 5. Customizing via `config.json` & `--org-config`

```json
{
  "organization_name": "Cymbal Financial",
  "global": { "default_currency": "USD" },
  "plugins": {
    "finance-variance-recon": {
      "materiality_amount_threshold": 15000.0,
      "price_tolerance_pct": 0.01,
      "ar_escalation_90_plus_threshold": 5000.0
    }
  }
}
```

Supply tenant overrides via `python3 tools/package.py --org-config org.json` so `org_configured: true` governs materiality and suppresses the starter baseline notice.

## 6. End-of-Close Reconciliation Decision Walkthrough

| Control Scenario | Input Anomaly | Standard Baseline Action | Escalation Routing |
| :--- | :--- | :--- | :--- |
| **Parent + Leaf P&L Mix** | Parent OPEX `$310k` + Cloud `$210k` + Travel `$100k` | Sum leaf rows only (`$310k`); verify tie-out `<= $1.00` | Suppress double-count; post `$60k` OpEx bridge (`>= $25k`) |
| **SAP Zero-Decimal JPY Invoice** | Raw `1500.00` `JPY` (`sap_raw_encoding=True`) | Multiply `1500 * 10^(2-0) = 150,000 JPY` (`$1,000`) | Matches PO price cleanly (`MATCHED_READY_FOR_HITL`) |
| **AP Duplicate / Bank Change** | Same vendor/amount within `3 days` or new IBAN | Force `DUPLICATE_BLOCK` / `FRAUD_HOLD` (`payment_hold=True`) | Treasury out-of-band callback + AP Manager freeze |
| **AR Credit Memo Offset Trap** | `$45k` invoice `132d` past due + `-$38k` credit | Isolate `-$38k` to `unapplied_credits`; evaluate `$45k >= $10k` | Priority `90+` Collections Hold + credit application review |
| **Retail Shrink Unpolled POS** | Store `STR-109` has `pos_poll_status="MISSING"` | Exclude store cleanly (`unpolled_pos_skipped=1`) | Dispatch IT POS poll repair rather than LP shrink audit |

## 7. Close & Treasury Control Checklist

1. Confirm `hierarchy_break_count == 0` (enforced inside `pnl_variance_engine.py`) before generating final monthly P&L variance packets.
2. Verify all negative AP credit memos (`SHKZG='H'`) and negative AR credits stay isolated from breach counts.
3. Require explicit Controller HITL confirmation prior to posting SAP payment batches, issuing retail chargebacks, or sending AR dunning notices.
4. Keep non-empty `truncation_warnings` prominently visible whenever API pulls omit total pages.

## 8. Treasury & Close Automation Write Governance (`Auto-Guardian` & Python Guards)

- **Connected ERP MCP payment releases:** Gated via Agent Gateway (`Auto-Guardian`) and explicit Controller confirmation whenever invoice totals `> $0` or exception holds exist.
- **Vendor remittance / bank master updates:** Never initiated from incoming emails; requires out-of-band treasury verification plus explicit approval.
- **Python code invariants (`scripts/*.py`):** Enforce `FRAUD_HOLD` / `DUPLICATE_BLOCK` on suspect invoices and require `hierarchy_break_count == 0` before executive P&L release.

Whenever `org_configured` in `references/config.json` is `false`, preserve the `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` header above all tables.
