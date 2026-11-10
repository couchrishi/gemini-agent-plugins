# Starter Baseline: Deal Desk Approval & Pipeline Hygiene Rubric (`deal-desk-approval-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, every deliverable MUST carry this exact top banner verbatim:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. SaaS Discount, Margin & Approval Escalation Matrix (`deal-desk-rfp-engine`)

| Approval Tier | Net Effective Discount | Commercial Term & Payment Tolerance | Blended Gross Margin | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 0: Auto-Approved (Rep)** | `0.0% – 15.0%` | `12–36 months`, `Net 30`, Standard SLA, no TFC | `>= 75.0%` | `auto_approve_max_discount_pct` |
| **Tier 1: Regional Sales VP** | `> 15.0% – 25.0%` | Up to `Net 45`, Annual upfront billing, standard indemnity | `>= 68.0%` | `vp_approve_max_discount_pct` |
| **Tier 2: Deal Desk & Finance** | `> 25.0% – 35.0%` | Up to `Net 60`, Quarterly billing, Year-1 ramp allowed | `>= 60.0%` | `deal_desk_max_discount_pct` |
| **Tier 3: CFO / Executive Desk** | `> 35.0%` | `> Net 60`, **Termination for Convenience (`TFC`)**, custom SLA credits `> 10%` | `< 60.0%` margin floor breach | `min_gross_margin_floor_pct` |

- **Default Target Currency:** Normalize all multi-currency quotes (`USD`, `EUR`, `GBP`, `JPY`) to `target_currency = "USD"` using dated FX rates before margin or discount banding.
- **RFP Answer Grounding Threshold:** Match security/technical questionnaire rows against curated library answers only when similarity hits `rfp_min_similarity_threshold >= 0.22`; otherwise abstain (`NEEDS_SME_AUTHORING`).

## 2. Pipeline Hygiene, Coverage & Slippage Triggers

| Hygiene Control | Trigger Rule (`org_configured=false`) | Severity | `config.json` Override Key |
| :--- | :--- | :--- | :--- |
| **Target Pipeline Coverage** | `open_weighted_pipeline < 3.0 * remaining_quota_usd` | `COVERAGE_DEFICIT` | `target_pipeline_coverage_x` |
| **Stage Stale Ratio Alert** | `days_in_stage > 1.5 * historical_stage_median_days` | `STALE_STAGE` | `stage_stale_multiplier` |
| **Chronic Close-Date Slippage** | `push_count >= 2` quarter/month pushbacks | `CHRONIC_SLIPPAGE` | `max_push_count_before_flag` |
| **Single-Threaded Commit Gate** | `ForecastCategory == "Commit"` and `contact_count < 2` | `SINGLE_THREADED_COMMIT` | `min_commit_contacts` |
| **Next-Step Inactivity Guard** | Active `Commit` deal missing buyer or `> 14d` since activity update | `UNVERIFIED_COMMIT` | Modeled via `LastActivityDate` + `OpportunityHistory` |

## 3. Executive Briefing & Consulting Delivery Baselines

This baseline also backs two adjacent commercial-cadence plugins whenever `org_configured` is `false`:

| Plugin ID | Governed Workflow & Thresholds | Default Baseline Values | `config.json` Override Keys |
| :--- | :--- | :--- | :--- |
| **`executive-briefing-ops`** | Calendar pre-read SLA, overdue follow-up escalation, renewal radar | `min_prep_buffer_minutes = 15`, `overdue_action_escalation_days = 3`, `renewal_critical_window_days = 90`, `touchpoint_stale_days = 30` | `min_prep_buffer_minutes`, `overdue_action_escalation_days`, `renewal_critical_window_days`, `touchpoint_stale_days` |
| **`gsi-proposal-ip-factory`** | Services SOW pricing, offshore delivery mix, acceptance timeline | `min_sow_gross_margin_pct = 30.0%`, `critical_margin_floor_pct = 20.0%`, `target_offshore_leverage_pct = 55.0%`, `max_acceptance_business_days = 10`, `min_skill_overlap_pct = 60.0%`, `max_start_delay_days = 14` | `min_sow_gross_margin_pct`, `critical_margin_floor_pct`, `target_offshore_leverage_pct`, `max_acceptance_business_days`, `min_skill_overlap_pct`, `max_start_delay_days` |

## 4. Deal & Services Escalation Severity Rules

1. **Year-1 Ramp Distortion Check:** Never approve a multi-year SaaS quote solely on Year-3 run-rate margin if `Year 1 Margin < min_gross_margin_floor_pct` AND `termination_for_convenience == True`.
2. **Unlimited Revisions Blocker (`SOW`):** Clauses promising unlimited revisions without formal change orders (`CO`) trigger mandatory commercial escalation alongside margin `< 20.0%` (`critical_margin_floor_pct`).
3. **Commit vs Pipeline Separation:** Exclude `Closed Lost` and unapproved custom stages (`IsClosed == true`) cleanly per [salesforce-crm-soql-traps.md](../traps/salesforce-crm-soql-traps.md).
4. **Executive Calendar Stale Touchpoint Rule:** Highlight VIP accounts within `90` days of renewal lacking executive outreach for `> 30` days (`touchpoint_stale_days`).

## 5. Customizing via `config.json` & `--org-config`

Provide corporate Deal Desk limits and regional FX conventions cleanly via `tools/package.py --org-config org.json`:

```json
{
  "organization_name": "Cymbal Financial",
  "plugins": {
    "deal-desk-rfp-engine": {
      "auto_approve_max_discount_pct": 12.0,
      "min_gross_margin_floor_pct": 65.0,
      "target_pipeline_coverage_x": 3.5
    },
    "gsi-proposal-ip-factory": {
      "min_sow_gross_margin_pct": 32.0,
      "target_offshore_leverage_pct": 60.0
    }
  }
}
```

Once `org_configured` evaluates `true`, all generated quote scorecards, pipeline hygiene tables, and SOW audits apply tenant thresholds cleanly without emitting the starter baseline banner.

## 6. Commercial Exception Walkthrough (`Q-CYM-22` Reference Case)

| Metric Evaluated | Observed Quote Value | Standard Baseline Threshold | Triggered Escalation Rule |
| :--- | :--- | :--- | :--- |
| **Net Effective Discount** | `37.5%` (`$750` vs `$1,200` list) | `> deal_desk_max_discount_pct (35%)` | Routes past Rep (`15%`) / VP (`25%`) / Deal Desk (`35%`) to **Tier 3 CFO** |
| **Blended Gross Margin** | `57.33%` (`$320` COGS) | `< min_gross_margin_floor_pct (60%)` | Margin floor exception required before quote issuance |
| **Payment Terms** | `Net 90` (`90 days`) | `> Net 60` Deal Desk limit | Working-capital carrying-cost adjustment flagged |
| **Termination for Convenience** | `true` (36-month contract) | Prohibited below `Tier 3` | Locks Year-1 customer churn exposure without cost recovery |

## 7. Pre-Submission Deal Desk Verification Checklist

1. Convert every international quote and opportunity line via dated `fx_rates` into `target_currency` before computing discount % or quota coverage.
2. Separate clean `Commit` pipeline (`>= 2` contacts, `push_count < 2`, `days_in_stage <= 1.5x` median) from at-risk `Commit` deals.
3. Flag every RFP questionnaire row scoring below `rfp_min_similarity_threshold (0.22)` as `NEEDS_SME_AUTHORING` rather than guessing compliance answers.
4. Keep CRM stage updates, SFDC quote approvals, and customer emails strictly behind `task_sticky` or `explicit_per_call` HITL confirmation.
