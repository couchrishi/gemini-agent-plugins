# Trap Guide: Salesforce CRM & SOQL Traps (`salesforce-crm-soql-traps`)

> **Applies to:** Deal Desk quote discounting & margin validation, pipeline slippage & forecast hygiene, executive QBR account prep, and VIP customer escalation workflows (`deal-desk-rfp-engine`, `executive-briefing-ops`, `customer-operations-escalation`).

## 1. Executive Summary Matrix

| Trap ID | Salesforce Object / API | Silent Failure Pattern | Deterministic Programmatic Guard |
| :--- | :--- | :--- | :--- |
| `TRAP-SF-01` | `Opportunity.StageName` vs `ForecastCategoryName` | Legacy/custom `"Closed Lost"` stages keep `Probability > 0`; rep overrides `Commit` | Enforce `IsClosed = false`; cross-check `StageName`, `IsWon`, and `ForecastCategoryName` |
| `TRAP-SF-02` | `Amount` vs `CurrencyIsoCode` (`DatedConversionRate`) | Summing nominal `10,000,000 JPY` + `50,000 USD` as `10,050,000` raw | Convert every opportunity/line via `fx_rates` to `target_currency`; block missing FX entries |
| `TRAP-SF-03` | `/query` `nextRecordsUrl` & polymorphic `WhoId`/`WhatId` | SOQL batches truncate at `2,000` (`200` with nested child subqueries) | Loop `done == true`; resolve polymorphic prefixes (`003` Contact, `00Q` Lead, `006` Opp) via `TYPEOF` |
| `TRAP-SF-04` | Multi-year ramped `TCV` vs Year-1 `ACV` | `Amount` holds 3-yr `$700k TCV` while Year-1 ramp ACV is `$100k` at `< 60%` margin | Evaluate Year-1 `ACV`, blended `ACV`, total `TCV`, and year-by-year gross margin |
| `TRAP-SF-05` | `LastActivityDate` staleness blind spot | Ignores unsynced inbound emails, Slack/Meet touchpoints, and stage stagnation | Combine `LastActivityDate`, `LastStageChangeDate`, and `OpportunityHistory` |
| `TRAP-SF-06` | Field-Level Security (FLS) omissions | Restricted fields (`AnnualRevenue`, `COGS`) omitted from JSON -> coerced to `$0` | Distinguish missing FLS field (`None`) from literal `0.0`; warn when margin/ARR data missing |

## 2. Numerical Before-vs-After Failure Walkthroughs

### Case A — Mixed-Currency Pipeline Coverage Distortion (`USD` + `JPY`)

- **Scenario:** Regional Sales Ops evaluates remaining-quarter quota (`$1,000,000 USD`) across two open `Commit` deals:
  1. `OPP-US`: `Cymbal US` = `$250,000 USD`
  2. `OPP-JP`: `Tokyo Financial` = `15,000,000 JPY` (`fx_rate = 0.0067 USD/JPY`)
- **Naive Failure:** Unconverted SOQL `SELECT SUM(Amount) FROM Opportunity` adds nominal numbers (`250,000 + 15,000,000 = $15,250,000`), reporting **`15.25x` quota coverage** and masking a severe Q4 pipeline deficit!
- **Correct Guarded Output (`pipeline_hygiene_analyzer.py`):** Convert `15,000,000 * 0.0067 = $100,500 USD`. True open Commit equals **`$350,500 USD`** (`0.35x` coverage vs `3.0x` target_pipeline_coverage_x), immediately flagging an urgent coverage gap.

### Case B — Multi-Year Ramped SaaS Margin & Term Escape Hatch (`Q-CYM-22`)

- **Scenario (`Cymbal Financial` Quote `Q-CYM-22`):** `36-month` subscription priced at `$750/unit/yr` vs `$1,200` list (`37.5%` net discount), `$320/unit/yr` COGS (`57.33%` gross margin), `payment_terms_days = 90` (`Net 90`), `billing_frequency = "quarterly"`, and `termination_for_convenience = True`.
- **Naive Failure:** Evaluating only nominal discount ceiling or averaging Year-3 expansion revenue misses two stacked blockers: `57.33%` blended margin breaches the **`60.0%` CFO floor** (`min_gross_margin_floor_pct`), AND `termination_for_convenience = True` allows exit prior to recovering Year-1 implementation cost!
- **Correct Guarded Output:** `deal_desk_quote_validator.py` routes `Q-CYM-22` cleanly to **Tier 3 (`CFO / Executive Desk`)** citing discount `> 35%`, gross margin `< 60%`, `Net 90 > Net 60`, and termination-for-convenience carve-out.

### Case C — Commit Integrity & Chronic Slippage Risk (`OPP-1`)

- **Scenario:** `OPP-1 Northstar POS Refresh` sits in `Commit` (`$250,000`), `days_in_stage = 45` (historical median `20d` -> `2.25x > 1.5x` stale limit), `push_count = 3` (`>= max_push_count_before_flag = 2`), and `contact_count = 1` (`< min_commit_contacts = 2`).
- **Naive Failure:** Forecast rollup treats `$250,000` identically to fresh multi-threaded deals, overstating Commit reliability.
- **Correct Guarded Output:** Applies deterministic hygiene penalty flags (`CHRONIC_SLIPPAGE`, `STALE_STAGE`, `SINGLE_THREADED_COMMIT`) and isolates clean vs at-risk Commit dollars for Deal Desk / Sales VP inspection.

## 3. SOQL Querying, Pagination & Relationship Rules

1. **Follow `done` and `nextRecordsUrl` completely:**
   - REST `/services/data/v61.0/query/` caps single pages at `2,000` records, and drops sharply to **`200` records** whenever nested parent-to-child subqueries (`(SELECT Product2Id, UnitPrice FROM OpportunityLineItems)`) appear!
   - If `done == false` on any API payload, pass `truncated = true` and `total_available = totalSize` into Python so `truncation_warnings` flags incomplete pipeline coverage.
2. **Use Explicit `TYPEOF` on Polymorphic Activity Fields:**
   - Standard `Task` and `Event` records use polymorphic `WhoId` (`003...` Contact vs `00Q...` Lead) and `WhatId` (`006...` Opportunity vs `500...` Case). Query via `TYPEOF What WHEN Opportunity THEN Name, Amount WHEN Account THEN Name END` rather than assuming `WhatId` is always an Opportunity.
3. **Avoid Non-Selective SOQL Queries:**
   - Filter on indexed fields (`IsClosed = false`, `LastModifiedDate >= ...`, `AccountId IN (...)`) to prevent `QUERY_TIMEOUT` and `NON_SELECTIVE_QUERY` rejections in multi-million-row orgs.

## 4. Programmatic Currency & Rate Normalization Pattern

```python
def convert_to_target_currency(amount: float, currency: str, fx_rates: dict[str, float], target: str = "USD") -> tuple[float, list[str]]:
    curr = (currency or target).upper().strip()
    tgt = (target or "USD").upper().strip()
    if curr == tgt:
        return amount, []
    rate = fx_rates.get(curr)
    if rate is None or float(rate) <= 0:
        return amount, [f"MISSING_FX_RATE: Cannot convert {curr} to {tgt} safely."]
    return amount * float(rate), []
```

- **HITL Policy Enforcement:** Never execute `sf_update_opportunity_stage`, `sf_approve_quote`, or `gmail_send_quote` autonomously — enforce `task_sticky` or `explicit_per_call` confirmation per `.gemini-plugin/policy.cel`.

## 5. Salesforce Object & Field Pitfall Reference Table

| Salesforce Object | Critical Fields | Common Analytical Trap | Programmatic Remediation |
| :--- | :--- | :--- | :--- |
| **`Opportunity`** | `Amount`, `CurrencyIsoCode`, `IsClosed`, `ForecastCategoryName` | Nominal `JPY` summed with `USD`; closed-lost custom stages non-zero prob | Filter `IsClosed=false`; convert via `DatedConversionRate` / `fx_rates` |
| **`OpportunityLineItem`** | `Quantity`, `UnitPrice`, `TotalPrice`, `Discount` | Year-1 promo discounts hidden in blended 36-mo TCV margin | Model Y1 ACV, blended ACV, and COGS margin separately |
| **`Quote` / `SBQQ__Quote__c`** | `NetTotal`, `PaymentTerm`, `TermMonths`, `Termination` | `Net 90` or `termination_for_convenience` triggers Tier-3 CFO gate | Enforce tier check across discount, margin, term, and TFC clauses |
| **`OpportunityHistory`** | `StageName`, `CreatedDate`, `CloseDate` | Missing slippage history if only snapshot `CloseDate` is checked | Compute `push_count` and `days_in_stage` vs historical stage median |
| **`Task` / `Event`** | `WhoId`, `WhatId`, `LastActivityDate` | `LastActivityDate` excludes unsynced emails and inbound Chatter notes | Join `EmailMessage` + `OpportunityContactRole` (`min_commit_contacts >= 2`) |

## 6. Pre-Commit Pipeline & Quote Audit Checklist

1. Assert `len(truncation_warnings) == 0` when SOQL queries return `<= 2,000` (or `200` with subqueries) and confirm `done == true`.
2. Separate `Commit` opportunities passing hygiene (`contacts >= 2`, `push_count < 2`, `stage_ratio <= 1.5`) from **At-Risk Commit** deals.
3. Require explicit FX rate table entries for every distinct `CurrencyIsoCode` before rolling up regional forecasts.
4. Route every Tier-2/Tier-3 quote (`> 25%` discount, `< 60%` margin, `> Net 60`, or `termination_for_convenience`) through named Deal Desk / CFO HITL approvers.

## 7. Safe SOQL Query Construction Examples

```sql
-- Include CurrencyIsoCode, IsClosed, ForecastCategoryName, and PushCount on every forecast query
SELECT Id, Name, AccountId, Amount, CurrencyIsoCode, StageName,
       ForecastCategoryName, Probability, IsClosed, IsWon,
       CloseDate, LastActivityDate, LastStageChangeDate, PushCount__c
FROM Opportunity
WHERE IsClosed = false
  AND CloseDate >= 2026-10-01
  AND CloseDate <= 2026-12-31
ORDER BY Amount DESC
```

- Always paginate child `OpportunityContactRole` and `OpportunityLineItem` subqueries at `batchSize <= 200` to avoid silent truncation.
- Cross-check every `Lead`/`Account` territory boundary against `references/config.json` before attributing rep attainment.
