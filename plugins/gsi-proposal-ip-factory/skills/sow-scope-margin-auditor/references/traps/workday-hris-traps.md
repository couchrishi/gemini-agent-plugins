# Trap Guide: Workday & HRIS API Traps (`workday-hris-traps`)

## Critical Pitfalls in Headcount, Compensation & Attrition Analytics

1. **Effective-Dated Stack (`Effective_Moment`) vs. Current Snapshot**
   - Workday RaaS / SOAP / WQL reports often emit **multiple historical and future-dated effective rows** for the same `Worker_ID` (e.g., a scheduled Q3 promotion already entered with `Effective_Date = 2026-07-01`).
   - Summing rows without filtering `Effective_Date <= as_of_date` and selecting the single latest effective record per `Worker_ID` double-counts promoted or transferred employees and inflates payroll totals.
   - **Mitigation:** Deduplicate strictly by `Worker_ID` selecting `max(effective_date <= as_of_date)` and flag future-dated or duplicate snapshot rows explicitly.

2. **Contingent Workers (`CWK`) vs. FTE (`EMP`) Double-Counting**
   - Workday's `All_Workers` report combines Full-Time Employees (`Worker_Type = Employee`), Contractors/Contingent Workers (`Contingent_Worker`), and Pre-Hires (`Future_Hire`).
   - Including `Contingent_Worker` or `Pre-Hire` rows in `FTE_Attrition` or `Compa_Ratio` denominators distorts voluntary turnover and average base salary (contractors often have `$0` base salary in Workday core comp fields!).
   - **Mitigation:** Partition `Employee` (`FTE`/`PTE`), `Contingent_Worker`, and `Pre_Hire` cohorts explicitly before computing headcount, attrition, or compensation bands.

3. **Compa-Ratio Currency & Pay-Period Normalization**
   - HRIS exports frequently mix `Hourly` pay rates (`$42/hr`), `Monthly` salaries, and `Annual` FTE base pay across `USD`, `EUR`, `GBP`, `INR`, and `JPY`. Comparing raw `Base_Pay` against USD annual midpoints produces catastrophic errors (`$42` looks 99% underpaid; `8,000,000 JPY` looks 80x overpaid).
   - **Mitigation:** Convert `Hourly` -> annual (`rate * annual_hours`, default `2080`), `Monthly` -> annual (`* 12`), and apply `fx_rates` to target currency BEFORE computing `compa_ratio = normalized_annual_pay / band_midpoint`.

4. **Small-Cell Privacy & PII Suppression (`n < 5`)**
   - Reporting exact salary min/max or attrition by `Department + Level + Gender/Ethnicity` when a cell has `1–4` employees leaks individual compensation.
   - **Mitigation:** Mask individual worker identifiers in aggregate outputs and suppress demographic/comp breakout averages for cells with `< 5` (configurable `min_privacy_cell_size`) workers.
