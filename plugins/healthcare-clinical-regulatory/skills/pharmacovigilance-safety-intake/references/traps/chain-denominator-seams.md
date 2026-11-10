# Trap Guide: Chain Denominator & Calendar Seams (`chain-denominator-seams`)

## Why Cross-System KPIs Diverge

Comparing numerator from System A (e.g., CRM bookings, POS gross units, ERP invoice count) against denominator from System B (e.g., Data Warehouse active accounts, HRIS headcount, General Ledger net revenue) fails silently when definitions, calendars, or FX conventions differ.

## Five High-Risk Seam Categories

1. **Fiscal Calendar vs. Calendar Month/Quarter Misalignment**
   - Retail `4-5-4` NRF calendars, `52/53`-week fiscal years, and shifted fiscal quarters (`FY26 Q1 = Feb–Apr`) cause `"Q1 YoY"` queries to compare 13 weeks against 12 weeks or 91 days against 92 days.
   - **Mitigation:** Always verify whether dates use ISO calendar (`YYYY-MM-DD`) or fiscal period keys (`fiscal_year`, `fiscal_period`). Normalize weekly comparisons to per-week run-rate (`value / active_weeks`) when comparing `53`-week years to `52`-week years.

2. **FX Conversion Basis (Spot vs. Budget vs. Period-Average vs. Closing)**
   - P&L Income Statement lines normally convert at **Period-Average** FX rates, Balance Sheet assets/liabilities at **Period-End Closing** rates, and Budget benchmarks at **Annual Plan Constant-Currency** rates. Mixing Spot and Budget FX creates artificial `"operational"` variance.
   - **Mitigation:** Separate **Constant-Currency Operational Variance** from **FX Translation Impact** before attributing blame to regional managers.

3. **Denominator Population Mismatch (Gross vs. Net, Active vs. Enrolled, FTE vs. Headcount)**
   - Examples:
     - **Sales Pipeline Coverage:** Open pipeline (`ACV` or `TCV`?) divided by remaining-quarter quota vs full-year quota.
     - **Workforce Attrition:** Voluntary exits divided by `period_end_headcount` vs `average_headcount`, or including `Contingent Workers` in denominator while numerator only counts `FTE` exits.
     - **Support CSAT / Defect DPMO:** Denominator excluding unresponded surveys or bypassed inspection lots inflates/deflates rates.
   - **Mitigation:** Explicitly print both numerator definition, denominator definition, and sample size `n` in every ratio output. Flag `LOW_SAMPLE_SIZE` whenever `n < 30` (or configured minimum).

4. **Revenue Recognition Timing (Bookings vs. Billings vs. Recognized Revenue)**
   - Salesforce `CloseDate` tracks **Bookings** (`ACV`/`TCV`); ERP `BSEG`/`VBRK` tracks **Billings**; GL revenue recognition tracks **ASC 606 / IFRS 15** amortized revenue.
   - **Mitigation:** Never sum CRM `Amount` directly with ERP `Invoice_Amount` without explicit reconciliation keys (`opportunity_id` -> `sales_order_id` -> `invoice_id`).

5. **Unit-of-Measure & Scale Mismatches (`EA` vs `CS`, `USD` vs `USD_K`, `Days` vs `Hours`)**
   - Procurement, BOM, and Retail feeds often mix `EA` (each), `CS` (case of 12/24), `KG` vs `LB`, or `$K` vs `$1`.
   - **Mitigation:** Enforce explicit `uom` and `currency` column normalization before arithmetic aggregation.
