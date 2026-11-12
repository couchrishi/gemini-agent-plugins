# Trap Guide: Workday & HRIS API Traps (`workday-hris-traps`)

> **Applies to:** Workforce attrition & compensation band audits, structured hiring rubric calibration, and employee onboarding orchestration (`people-ops-talent-hub`, `workforce-attrition-comp-audit`, `structured-hiring-rubric`, `employee-onboarding-navigator`).

## 1. Executive Summary Matrix

| Trap ID | Workday / HRIS Seam | Silent Failure Pattern | Deterministic Programmatic Guard |
| :--- | :--- | :--- | :--- |
| `TRAP-WD-01` | Effective-dated stack (`Effective_Moment`) | Single `Worker_ID` outputs historical, current, and scheduled future promotion rows | Group by `Worker_ID`, take `max(effective_date <= as_of_date)`; isolate `future_dated` rows |
| `TRAP-WD-02` | `Employee` vs `Contingent_Worker` (`CWK`) & `Pre_Hire` | Contractors with `$0` base pay or pre-hires contaminate FTE headcount & attrition | Partition `EMP`, `CWK`, and `PRE_HIRE` cohorts explicitly before any ratio math |
| `TRAP-WD-03` | Mixed pay periods & currencies (`Hourly`/`Monthly`/`JPY`) | Comparing `$45/hr` directly against `$90,000` annual midpoint (`0.0005` compa!) | Scale `Hourly * annual_working_hours (2080)`, `Monthly * 12`, then apply `fx_rates` to USD |
| `TRAP-WD-04` | Small-cell privacy leak (`n < 5`) | Publishing compa-ratio or attrition for `1–4` FTE slices leaks personal compensation | Suppress cell averages (`avg_compa_ratio = None`, `attrition_pct = None`) when `active_n < 5` |
| `TRAP-WD-05` | Rescinded offers & zero-headcount divisions | `Pre_Hire` no-shows inflate `Voluntary_Attrition` or empty cohorts throw `ZeroDivisionError` | Exclude pre-start cancellations from turnover numerator; guard `0` denominators cleanly |
| `TRAP-WD-06` | Unsubstantiated/biased interview scorecards | Short boilerplate notes or age/protected-class phrasing distort hiring bar decisions | Check `len(evidence_text) >= min_evidence_chars (40)` & dispersion `max - min >= 2.0` |

## 2. Numerical Before-vs-After Failure Walkthroughs

### Case A — Effective-Dated Promotion Stack Double-Counting (`W-101`)

- **Scenario (`workday_people_ops_meridian.json`):** `Worker_ID = W-101` appears in two RaaS rows inside the same export file (`as_of_date = 2026-11-10`):
  1. Prior comp row: `effective_date = 2026-01-01`, `base_pay = 120,000 USD`
  2. Current promotion row: `effective_date = 2026-04-01`, `base_pay = 135,000 USD`
- **Naive Failure:** Summing raw report rows counts `W-101` twice (`7` FTE rows instead of `6` unique FTEs), overstates annual payroll by `+$120,000`, and miscalculates `compa_ratio` from stale Q1 salary!
- **Correct Guarded Output (`workday_comp_attrition_audit.py`):** Collapses `W-101` deterministically to its single latest effective row `<= as_of_date` (`2026-04-01`, `$135,000`) -> `historical_snapshots_collapsed = 1`.

### Case B — Contingent Worker (`CWK-901`) & Hourly / FX Pay Normalization

- **Scenario:** Same RaaS extract contains contractor `CWK-901` (`worker_type = "Contingent_Worker"`, `base_pay = 0`, `status = "Active"`), an hourly lab technician (`$45/hr`, `pay_period = "Hourly"`), and a German scientist (`140,000 EUR`, `fx_rate = 1.10 USD/EUR`).
- **Naive Failure:**
  - Including `CWK-901` adds a `$0` contractor row into active FTE payroll (`6` active instead of `5`), drags department average salary down, and dilutes turnover %.
  - Comparing `$45` unscaled hourly rate against a `$90,000` annual midpoint yields `compa_ratio = 0.0005` (`-99.95%` critical compression false alarm!).
- **Correct Guarded Output:** Isolates `CWK-901` (`contingent_worker_isolated_count = 1`), multiplies `$45 * 2080 = $93,600` (`annual_working_hours = 2080`), converts `140,000 EUR * 1.10 = $154,000 USD`, and evaluates target `[0.85, 1.15]` bands accurately (`< 0.80` underpaid alert, `> 1.25` overpaid ceiling).

### Case C — Small-Cell Privacy Suppression (`n < 5` Rule)

- **Scenario:** `Clinical R&D` has `4` active FTEs (`< min_privacy_cell_size = 5`) and `Legal` has `1` active FTE alongside `1` departure.
- **Naive Failure:** Emitting `Legal Attrition = 100%` and `Clinical R&D Avg Compa-Ratio = 0.78` allows coworkers in a shared spreadsheet to infer an individual employee's exact salary and termination!
- **Correct Guarded Output:** Sets `suppressed_for_privacy = True`, `avg_compa_ratio = None`, and `attrition_pct = None` for every department slice where `active_n < 5`, preserving individual confidentiality while still surfacing `comp_outlier_count` cleanly to HR Ops leadership.

## 3. Workday Pagination, RaaS & Interview Calibration Safeguards

1. **RaaS & WQL Pagination Completeness:** Workday REST/WQL APIs paginate via `offset` & `limit` (often `100` rows per page). Always compare returned count vs `total` and preserve `truncated=True` warnings inside `truncation_warnings`.
2. **Structured Interview Calibration (`candidate_rubric_scorer.py`):** Flag interviewer panel spread whenever `max(scores) - min(scores) >= 2.0` (`max_score_spread`), require behavioral evidence `>= 40` characters (`min_evidence_chars`), and scan notes for protected-class bias terms (`age`, `family plans`, `maternity`, `culture fit` clichés).
3. **Strict HITL Compensation & HRIS Mutation Hold:** Updating compensation bands, advancing candidate offers, or syncing HRIS status updates via a connected Workday/ATS MCP server requires Agent Gateway (`Auto-Guardian`) approval and explicit HRBP/Lead confirmation; only read-only analysis and private summaries run automatically.

```python
def annualize_worker_pay(raw_pay: float, pay_period: str, fx_rate: float, annual_hours: int = 2080) -> float:
    period = (pay_period or "annual").strip().lower()
    if period in {"hourly", "hour", "hr"}:
        local_annual = raw_pay * annual_hours
    elif period in {"monthly", "month", "mo"}:
        local_annual = raw_pay * 12.0
    elif period in {"biweekly", "bi-weekly"}:
        local_annual = raw_pay * 26.0
    else:
        local_annual = raw_pay
    return local_annual * fx_rate
```

## 4. Workday Field & Export Normalization Table

| Workday Field / Concept | Common Export / API Pitfall | Normalization Formula / Filter | Verification Metric |
| :--- | :--- | :--- | :--- |
| **`Effective_Moment` / `Effective_Date`** | Multiple stacked historical + future-dated promo rows per `Worker_ID` | Deduplicate keeping `max(effective_date <= as_of_date)`; segregate future rows | `historical_snapshots_collapsed`, `future_dated_isolated` |
| **`Worker_Type`** | Mixes `Employee`, `Contingent_Worker`, and `Pre_Hire` (`$0` salary) | Evaluate attrition & compa-ratios strictly across `Employee` cohort | `contingent_worker_isolated_count`, `active_fte_count` |
| **`Pay_Rate_Type` & `Currency`** | Hourly (`$45/hr`), Monthly, Annual mixed across `USD`/`EUR`/`JPY`/`INR` | `Hourly * 2080`, `Monthly * 12`, multiply by `fx_rates[curr]` | `normalized_annual_usd`, `compa_ratio` |
| **Small-Cell Demographics** | Department + Level buckets with `1–4` employees expose exact pay | Suppress aggregate means when `cohort_count < min_privacy_cell_size (5)` | `suppressed_for_privacy == True` |
| **`Terminated_Before_Start`** | Rescinded offer counted as active voluntary turnover | Partition `Pre_Hire` cancellations separately from active `EMP` exits | `pre_hire_excluded_count` |
| **Interviewer Evidence Notes** | `< 40` char rubber-stamp reviews or demographic bias language | Flag `short_evidence`, score spread `>= 2.0`, and bias phrases | `dispersion_alert_count`, `bias_flags` |

## 5. People Analytics Verification Checklist

1. Reconcile `raw_row_count - historical_snapshots_collapsed - future_dated_isolated - contingent_worker_isolated == unique_fte_count` before computing any department metric.
2. Assert every hourly and monthly worker converts to annual USD prior to dividing by `band_midpoint_usd`.
3. Verify `avg_compa_ratio` and `attrition_pct` return `None` in JSON and `"Suppressed (n < 5)"` in Markdown whenever a slice contains fewer than `5` employees.
4. Route every compensation band adjustment, offer extension, or Workday mass-change behind Agent Gateway (`Auto-Guardian`) and explicit HITL confirmation.

## 6. Effective-Date Deduplication Reference Logic

```python
def deduplicate_effective_rows(rows: list[dict], as_of_date: str) -> tuple[list[dict], int, int]:
    """Select the latest effective snapshot <= as_of_date per worker_id without counting future promos."""
    latest: dict[str, dict] = {}
    collapsed, future = 0, 0
    for row in rows:
        wid = str(row.get("worker_id") or "").strip()
        eff = str(row.get("effective_date") or "").strip()[:10]
        if eff and as_of_date and eff > as_of_date:
            future += 1
            continue
        prev = latest.get(wid)
        if prev is None:
            latest[wid] = row
        else:
            collapsed += 1
            if eff >= str(prev.get("effective_date") or "")[:10]:
                latest[wid] = row
    return list(latest.values()), collapsed, future
```

- Propagate `historical_snapshots_collapsed` and `future_dated_isolated` counts in `summary` so HR Leadership verifies exact cohort reconciliation.
