# Starter Baseline: HR Hiring Rubric, Onboarding & Compensation Guardrails (`hr-hiring-comp-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, every deliverable MUST carry this exact top banner verbatim:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Structured Interview Calibration & Anti-Bias Matrix (`structured-hiring-rubric`)

| Calibration Dimension | Standard Baseline Default | Flag / Alert Condition | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- |
| **4-Point Anchor Rubric** | `1 = Strong No Hire`, `2 = No Hire`, `3 = Hire`, `4 = Strong Hire` | Compute unweighted/competency mean against bar floor (`3.0`) | `hire_mean_threshold` |
| **Panel Score Dispersion** | Max allowed interviewer spread `< 2.0` points | Flag `HIGH_PANEL_DISPERSION` whenever `max(scores) - min(scores) >= 2.0` | `max_score_spread` |
| **Evidence Depth Minimum** | `>= 40 characters` specific behavioral/technical citation per note | Flag `INSUFFICIENT_EVIDENCE` when rubber-stamp feedback `< 40 chars` | `min_evidence_chars` |
| **Protected-Class / Bias Scan** | Strictly prohibited (`age`, `marital`, `maternity`, `cultural fit`) | Immediate `BIAS_LANGUAGE_WARNING` + human Talent Calibration hold | Deterministic phrase & regex scan |

- **Audit Principle:** Never extrapolate a hiring recommendation (`HIRE`) solely from numerical average when one or more competencies score `1`, panel spread `>= 2.0`, or bias language triggers (`CALIBRATION_REVIEW_REQUIRED`).

## 2. Employee Onboarding Readiness & SLA Checkpoints (`employee-onboarding-navigator`)

| Milestone Window | Standard Required Tasks (`EMP` New Hire) | Escalation Owner & Action |
| :--- | :--- | :--- |
| **Day `<= 0` (Pre-Start)** | Background clearance, laptop provisioning, SSO identity activation | IT & People Ops blocker hold (`START_DATE_AT_RISK`) |
| **Day `1 – 3` (Compliance Critical)** | Government I-9 / right-to-work verification (`due_day_offset = 3`), NDA & Code of Conduct | Legal / HR Compliance immediate `OVERDUE_BLOCKER` past Day 3 |
| **Day `4 – 7` (Security & Role)** | Security awareness training (`due_day_offset = 7`), IAM least-privilege group binding | Manager + SecOps notification if open past target offset |
| **Day `8 – 30` (Ramp & Goals)** | 30-day manager check-in, benefits enrollment deadline, mandatory role onboarding | People Partner digest rollup |

## 3. Compensation Band, Compa-Ratio & Privacy Rules (`workforce-attrition-comp-audit`)

| Metric | Standard Baseline Default | Interpretation & Escalation Rule | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- |
| **Target Compa-Ratio Band** | `0.85 – 1.15` (`Annualized USD / Band Midpoint`) | `0.85–0.95` Developing; `0.95–1.05` Market Competitive; `1.05–1.15` High Performer | `compa_ratio_min`, `compa_ratio_max` |
| **Underpaid Compression Alert** | `< 0.80` (`compa_ratio_underpaid_alert`) | Flag `COMP_UNDERPAID_COMPRESSION` for immediate off-cycle equity/merit review | `compa_ratio_underpaid_alert` |
| **Above-Band Ceiling Alert** | `> 1.25` (`compa_ratio_overpaid_alert`) | Flag `COMP_OVER_CEILING`; block auto-merit increase pending VP Compensation approval | `compa_ratio_overpaid_alert` |
| **Small-Cell Privacy Floor** | `n >= 5` active FTEs (`min_privacy_cell_size`) | Suppress department/level `avg_compa_ratio` & `attrition_pct` (`None`) when `n < 5` | `min_privacy_cell_size` |
| **Hourly Annualization Basis** | `2080 hours / year` (`annual_working_hours`) | Normalize `Hourly * 2080` and `Monthly * 12` + `fx_rates` before band evaluation | `annual_working_hours` |

## 4. Workday Cohort Hygiene & HITL Enforcement

1. **Snapshot Deduplication (`TRAP-WD-01`):** Collapse multi-row effective-dated exports keeping strictly `max(effective_date <= as_of_date)` per `worker_id` and isolating `future_dated` promos.
2. **Cohort Separation (`TRAP-WD-02`):** Isolate `Contingent_Worker` (`CWK`) and `Pre_Hire` rows completely from `FTE` active headcount, attrition, and compa-ratio calculations.
3. **Zero Autonomous HR Mutations:** Drafting interview debrief packets or private onboarding checklists runs cleanly; sending candidate offers/rejections or updating compensation in a connected Workday HRIS / ATS MCP server requires Agent Gateway (`Auto-Guardian`) approval and explicit HRBP/Lead confirmation.

## 5. Customizing via `config.json` & `--org-config`

```json
{
  "organization_name": "Cymbal Financial",
  "plugins": {
    "people-ops-talent-hub": {
      "compa_ratio_min": 0.90,
      "compa_ratio_max": 1.10,
      "min_privacy_cell_size": 7,
      "annual_working_hours": 1950
    }
  }
}
```

Packaging via `tools/package.py --org-config org.json` activates `org_configured: true`, enforces local statutory working hours (`1950` vs `2080`) and stricter `n >= 7` privacy suppression, and removes the starter baseline stamp.

## 6. Workday Audit & Calibration Walkthrough (`Meridian BioPharma` Fixture)

| Raw Audit Edge Case | Uncorrected Failure | Guarded Baseline Outcome (`hr-hiring-comp-baseline`) |
| :--- | :--- | :--- |
| **`W-101` two effective snapshots** | Counts `W-101` twice (`+$120k` phantom payroll) | Collapses to `2026-04-01` row (`$135,000`); `historical_snapshots_collapsed = 1` |
| **`CWK-901` active `$0` contractor** | Pulls active FTE avg pay down; dilutes attrition % | Isolates contractor (`contingent_worker_isolated_count = 1`) from FTE headcount `5` |
| **Hourly `$45/hr` & `140k EUR` staff** | Raw `$45` looks `-99.9%` underpaid vs `$90k` band | Annualizes `$45 * 2080 = $93,600` & converts FX before band check |
| **`Clinical R&D` (`n=4`) & `Legal` (`n=1`)** | Exposes identifiable teammate salary/exit stats | Sets `suppressed_for_privacy = True`; masks cell averages (`None`) cleanly |
| **Interview spread `[4, 2]` + short note** | Rubber-stamps `3.0` mean as consensus Hire | Triggers `HIGH_PANEL_DISPERSION` (`2.0 >= 2.0`) & `INSUFFICIENT_EVIDENCE` |

## 7. People Ops & Privacy Verification Checklist

1. Verify `historical_snapshots_collapsed`, `future_dated_isolated`, and `contingent_worker_isolated_count` tie out against raw RaaS row counts.
2. Confirm every group cell with `< min_privacy_cell_size` workers omits numeric compa-ratio and attrition rates (`None`).
3. Audit every interview rubric output for `< 40` char rationales (`min_evidence_chars`) and prohibited bias terminology.
4. Keep all offer approvals, merit adjustments, and Workday status writes gated behind explicit HR Partner confirmation.

## 8. Privacy & Talent Write Governance (`Auto-Guardian` & Python Guards)

- **Mandatory `n < 5` Privacy Floor:** Python engines enforce `min_privacy_cell_size >= 5` before serialization, redacting small-cohort salaries and attrition rates structurally.
- **Compensation & Offer Release Gate:** Agent Gateway (`Auto-Guardian`) and explicit HRBP / Hiring Manager confirmation block autonomous Workday pay changes or ATS offer advances.
- **Calibration Dispersion Invariant:** Interview debrief outputs flag any panel spread above `max_score_spread` or short rationales before final consensus.

Scheduled People Ops `schedule_task` sweeps (such as `Weekly Onboarding SLA Nudge`) draft manager reminders safely and never release automated employee termination or compensation changes.
