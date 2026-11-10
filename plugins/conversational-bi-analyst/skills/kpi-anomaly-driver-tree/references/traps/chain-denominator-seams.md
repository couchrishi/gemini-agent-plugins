# Trap Guide: Chain Denominator & Calendar Seams (`chain-denominator-seams`)

> **Applies to:** Revenue/margin bridges, sales pipeline coverage, HR turnover & compa-ratio audits, supply-chain OTIF, retail promo ROI, and healthcare/FSI ratio KPIs spanning disparate enterprise systems.

## 1. Executive Summary Matrix

| Trap ID | Seam Category | Broken Formula Example | Correct Normalized Formula |
| :--- | :--- | :--- | :--- |
| `TRAP-DEN-01` | Fiscal calendar mismatch (`52` vs `53` wks / NRF `4-5-4`) | Comparing `14`-week fiscal Q4 raw revenue to prior `13`-week Q4 | Normalize to per-week or per-day run-rate (`value / active_days`) |
| `TRAP-DEN-02` | Mixed FX basis (Spot vs Plan/Budget vs Closing) | Comparing Actual at Spot FX directly to Plan at Budget FX | Split `Constant-Currency Ops Variance` vs `FX Translation Variance` |
| `TRAP-DEN-03` | Denominator population mismatch | `FTE_Exits / (FTE + Contractors)` or unpolled stores in shrink % | Align numerator & denominator populations strictly; guard `n < min_sample_size` |
| `TRAP-DEN-04` | Revenue recognition timing gap | Summing CRM Bookings `Amount` directly with ERP `VBRK` Billings | Reconcile along ID lineage (`opportunity_id -> sales_order_id -> invoice_id`) |
| `TRAP-DEN-05` | Unit-of-Measure (UoM) & scale mixing | Multiplying `$K` unit price by `$1` cost, or `CS` (case=12) by `EA` | Canonicalize UoM (`qty * uom_factor`) & reporting currency before arithmetic |
| `TRAP-DEN-06` | Simpson's Paradox in segment rollups | Explaining total margin shift without Mix + Rate + Volume split | Run additive bridge `(Volume + Mix + Rate == Total Delta)` |

## 2. Numerical Before-vs-After Failure Walkthroughs

### Case A — Constant-Currency FX vs Operational Variance (`Cymbal EMEA OpEx`)

- **Scenario:** EMEA Infrastructure budgets `100,000 EUR` at Annual Plan FX (`1.10 USD/EUR` = `$110,000 USD`). Actual local spend lands at `100,000 EUR` (exact operational compliance!), while Spot FX appreciates to `1.25 USD/EUR` (`$125,000` reported USD).
- **Naive Failure:** Subtracting reported USD actual minus USD budget computes `+$15,000 (+13.6%)` — breaching `$10,000` / `10%` materiality and faulting engineering managers for currency appreciation outside their control.
- **Correct Guarded Output:** Decompose deterministically inside `pnl_variance_bridge.py`:
  - **Operational Variance (Constant Plan FX):** `(100,000 - 100,000) * 1.10 = $0.00` (On Budget).
  - **FX Translation Impact:** `100,000 * (1.25 - 1.10) = +$15,000.00` (Routed to Treasury FX explanation).
  - **Tie-Out Identity:** `$0.00 + $15,000.00 == $15,000.00` total USD delta.

### Case B — Retail Promotional Lift (`7-Day Promo` vs `28-Day Baseline`)

- **Scenario (`PROMO-BEV`):** Baseline period (`28 days`) sold `4,000` units (`$20,000` revenue, `$8,000` gross margin = `$285.71/day`). A `7-day` `50% Off` campaign sells `2,200` units (`$5,500` revenue, `$1,500` gross margin = `$214.29/day`), triggers `$900` sibling SKU margin cannibalization, adds `$200` basket halo, and costs `$1,200` in media execution.
- **Naive Failure:** Looking only at raw `7-day` promo units (`2,200 / 7 = 314.3/day` vs `142.9/day` baseline -> `+120%` unit lift!) declares the promotion a resounding success!
- **Correct Guarded Output (`promo_lift_analyzer.py`):**
  - Expected 7-day baseline margin (`7 * $285.71`) = **`$2,000.00`**.
  - Incremental direct promo margin (`$1,500 - $2,000`) = **`-$500.00`**.
  - Net promo margin after cannibalization (`-$900`), halo (`+$200`), and promo cost (`-$1,200`) = **`-$2,400.00` (`ROI = -200%`) -> `VALUE_DESTRUCTIVE`!**

### Case C — Sample Size Threshold & Zero-Denominator Crashes

- **Scenario:** Segment `APAC` shows `100%` churn intent on `n = 2` survey responses while `North America` shows `8%` on `n = 600`. Simultaneously, a newly launched product line has `prior_volume = 0`, `prior_revenue = 0.0`.
- **Naive Failure:** Ranking `n = 2` at the top of an executive escalation chart misallocates support staffing, while computing `(current - prior) / prior` triggers `ZeroDivisionError` and crashes the batch pipeline!
- **Guarded Outcome:**
  1. Emit `LOW_SAMPLE_SIZE_WARNING` whenever `sample_size < min_sample_size_guard` (`30` default in BI; `5` for HR cell privacy).
  2. Use guarded zero-denominator checks (`denominator == 0 -> None / 0.0`) paired with explicit `UNDEFINED_ZERO_DENOMINATOR` status flags.

### Case D — Mix / Rate / Volume Bridge Identity (Simpson's Paradox)

- When evaluating total revenue or ASP shifts across segments, two segments can both increase price individually while total blended ASP **drops** due to lower-priced tier volume growth (`Mix Effect`).
- Compute additive decomposition in Python RAM:
  - `Volume Effect = (Total_Q1 - Total_Q0) * P0_blended`
  - `Mix Effect = sum_i (Share1_i - Share0_i) * Total_Q1 * (P0_i - P0_blended)`
  - `Rate Effect = sum_i Q1_i * (P1_i - P0_i)`
  - Assert identity `abs((Volume + Mix + Rate) - (Rev1 - Rev0)) < 0.01` to catch reconciliation drift automatically.

## 3. Cross-System Population & Calendar Checklist

1. **Time-Window Alignment:** Require explicit `baseline_days`, `window_days`, or `enrollment_window_months`; never divide a 90-day numerator by a 30-day denominator.
2. **Cohort Parity:** Verify numerator & denominator exclude mismatched entity types:
   - HRIS attrition excludes `Contingent_Worker` and `Pre_Hire` from both exits and active headcount.
   - CRM pipeline coverage compares weighted active `Commit/BestCase` against `remaining_quota_usd`, NOT annual quota.
   - Telco/ITSM MTTR excludes open/canceled tickets (`resolved_at is None`, `state=8`) from closed MTTR averages.
3. **Currency & UoM Normalization:** Require explicit `fx_rates` before combining multi-currency monetary fields (`USD`, `EUR`, `JPY`), and scale BOM/retail units (`CS -> EA`, `Hourly -> Annual * 2080`) prior to summation.

## 4. Programmatic Ratio & Guard Template

```python
def safe_ratio(
    numerator: float | None,
    denominator: float | None,
    *,
    sample_size: int | None = None,
    min_sample_size: int | None = None,
) -> tuple[float | None, list[str]]:
    flags: list[str] = []
    if sample_size is not None and min_sample_size is not None and sample_size < min_sample_size:
        flags.append(f"LOW_SAMPLE_SIZE: n={sample_size} < {min_sample_size}")
    if numerator is None or denominator is None or abs(float(denominator)) < 1e-12:
        flags.append("UNDEFINED_ZERO_DENOMINATOR")
        return None, flags
    return float(numerator) / float(denominator), flags
```

## 5. Multi-System Denominator Reconciliation Matrix

| Metric Domain | System A (Numerator) | System B (Denominator) | Hidden Divergence Seam | Canonical Safeguard |
| :--- | :--- | :--- | :--- | :--- |
| **Sales Coverage** | Salesforce `Commit` ACV | Plan remaining-Q quota | Year-1 ramp vs multi-yr TCV; nominal FX | Normalize to USD, separate Y1 ACV & coverage vs Q-to-go quota |
| **Employee Attrition** | Workday terminations | Active `EMP` headcount | Contractors (`CWK`), pre-hires, future rows | Filter `Effective_Date <= as_of_date`, exclude `CWK`, suppress `n < 5` |
| **Promo Margin ROI** | `7-day` POS promo GM | `28-day` baseline GM | Raw totals compare 7d vs 28d + ignore halo/cannibalization | Normalize to `/day` run-rate; subtract cannibalization & cost |
| **OTIF Compliance** | WMS dock arrivals | ERP PO quantities | `98%` in-full threshold + `30 min` dock grace ignored | Apply contractual grace tolerance + separate dwell detention |
| **Support CSAT / MTTR** | Zendesk / Jira resolved | Total ticket cohort | Still-open/canceled tickets in MTTR; `n < 30` segments | Exclude open (`resolved_at is None`) & `Canceled` (`state=8`) |
| **P&L OpEx Bridge** | Actual GL (`USD` Spot) | Budget GL (`USD` Plan) | FX move blamed on functional budget owners | Split `(Act - Bud) * Bud_FX` from `Act * (Act_FX - Bud_FX)` |

## 6. Executive Output Verification Rules

1. Never publish a percentage change without printing both the raw numerator and exact denominator (`n`).
2. Flag `LOW_SAMPLE_SIZE_WARNING` whenever cohort `n` drops below configured statistical floor (`30` BI default, `5` HR privacy).
3. Assert additive tie-outs (`Volume + Mix + Rate == Revenue Delta`, `Ops Variance + FX Impact == Total Variance`) inside unit/eval checks before returning tables.
