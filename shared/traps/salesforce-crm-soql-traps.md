# Trap Guide: Salesforce CRM & SOQL Traps (`salesforce-crm-soql-traps`)

## Critical Pitfalls in Pipeline, Deal Desk & Forecasting

1. **`StageName` Probability vs. `ForecastCategoryName` Mismatch**
   - Salesforce `Opportunity.Probability` often defaults to stage probabilities (`Negotiation = 80%`), while managers override `ForecastCategoryName` (`Omitted`, `Pipeline`, `BestCase`, `Commit`, `Closed`). Conversely, `"Closed Lost"` or `"Disqualified"` custom stages occasionally retain non-zero probabilities in sandboxed or legacy picklists.
   - **Rule:** Filter active open pipeline using `IsClosed = false` AND compute weighted pipeline from `ForecastCategory` weights or verified stage probability, flagging rows where `StageName` contradicts `IsClosed`/`IsWon`.

2. **Multi-Currency `Amount` vs. `DatedConversionRate` (`CurrencyIsoCode`)**
   - Querying raw `Amount` across USD, EUR, JPY, and GBP opportunities without `convertCurrency(Amount)` or joining `DatedConversionRate` (for Advanced Currency Management orgs) adds raw nominal numbers across currencies (e.g., summing `10,000,000 JPY` with `50,000 USD` as `10,050,000`!).
   - **Rule:** Enforce explicit `currency` -> `target_currency` normalization via `fx_rates` before summing `ACV` or `TCV`. Flag mixed-currency inputs missing an FX rate table rather than summing raw amounts.

3. **Polymorphic `WhoId` / `WhatId` & `nextRecordsUrl` Pagination**
   - `Task` and `Event` objects use polymorphic `WhoId` (Contact or Lead) and `WhatId` (Account, Opportunity, or Case); SOQL joins must use `TYPEOF` or inspect key prefixes (`003` Contact, `00Q` Lead, `006` Opportunity).
   - SOQL REST `/query` returns max `2000` records per batch (or `200` with child subqueries) and sets `done: false` with `nextRecordsUrl`. Always check `done` and `totalSize`.

4. **`ACV` vs. `TCV` vs. Multi-Year Ramp Distortion**
   - Multi-year ramped SaaS deals store total contract value in `Amount` while Year-1 ramp ARR is lower (e.g., `$100k Y1 / $250k Y2 / $350k Y3 = $700k TCV` vs `$233.3k Avg ACV`). Discounting Year 1 heavily can push blended multi-year gross margin below floor if evaluated only on Year-3 list price.
   - **Rule:** Evaluate both Year-1 `ACV`, blended `ACV`, total `TCV`, and year-by-year ramp margin in `deal_margin_validator.py`.

5. **Compound Address & `SystemModstamp` vs. `LastActivityDate`**
   - `LastActivityDate` updates only on **completed** Tasks or past Events (`ActivityDate`), NOT on inbound emails logged via third-party sync or Chatter posts unless synced as Tasks. Check both `LastActivityDate` and `LastStageChangeDate` (or `OpportunityHistory`) before declaring an opportunity inactive.
