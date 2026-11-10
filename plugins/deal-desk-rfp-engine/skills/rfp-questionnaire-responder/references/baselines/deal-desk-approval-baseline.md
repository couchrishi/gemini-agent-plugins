# Starter Baseline: Deal Desk Approval & Pipeline Hygiene Rubric (`deal-desk-approval-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, stamp the deliverable header verbatim with:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Discount, Gross Margin & Approval Tier Matrix

| Approval Tier | Net Effective Discount | Contract Term / Payment Terms | Blended Gross Margin | Override Key in `config.json` |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 0: Auto-Approved (Rep)** | `0% – 15%` | `12–36 months`, `Net 30`, Standard SLA | `>= 75%` | `auto_approve_max_discount_pct` |
| **Tier 1: Regional Sales VP** | `> 15% – 25%` | Up to `Net 45`, Annual upfront billing | `>= 68%` | `vp_approve_max_discount_pct` |
| **Tier 2: Deal Desk & Finance** | `> 25% – 35%` | `Net 60`, Quarterly billing, Year-1 ramp | `>= 60%` | `deal_desk_max_discount_pct` |
| **Tier 3: CFO / Executive Desk** | `> 35%` | `> Net 60`, non-standard termination for convenience, custom SLA credits `> 10%` | `< 60%` (requires explicit margin exception) | `min_gross_margin_floor_pct` |

## 2. Pipeline Hygiene & Slippage Risk Triggers

- **Stage Stale Ratio Alert:** Opportunity `days_in_stage > 1.5 * historical_stage_median_days` (`stage_stale_multiplier = 1.5`).
- **Chronic Slippage Alert:** `push_count >= 2` across fiscal quarters (`max_push_count_before_flag = 2`).
- **Commit Integrity Gates:** Opportunities in `Commit` must have:
  - Non-empty `economic_buyer` / `next_step` updated within `14 days` (`max_commit_inactivity_days = 14`),
  - At least `2` active stakeholder contacts (`min_commit_contacts = 2` — avoiding single-threaded risk),
  - Active `technical_validation` or `mutual_action_plan` status.
- **Target Pipeline Coverage Ratio:** `3.0x` remaining open quota (`target_pipeline_coverage_x = 3.0`).
