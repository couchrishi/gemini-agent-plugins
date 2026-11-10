# Starter Baseline: HR Hiring Rubric, Onboarding & Compensation Guardrails (`hr-hiring-comp-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, stamp the deliverable header verbatim with:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Structured Interview Calibration & Bias Rules

- **4-Point Anchor Scale:** `1 = Strong No Hire (Insufficient Evidence / Gaps)`, `2 = No Hire (Below Bar)`, `3 = Hire (Meets Bar)`, `4 = Strong Hire (Exceeds Bar)`.
- **Dispersion Alert:** Flag panel disagreement whenever `max(scores) - min(scores) >= 2.0` (`max_score_spread = 2.0`).
- **Evidence Completeness:** Every rating requires concrete behavioral/technical evidence (`min_evidence_chars = 40`); flag generic unsubstantiated summaries or protected-class / age / marital-status bias language immediately.

## 2. Compensation Band & Compa-Ratio Thresholds

| Metric | Standard Baseline Default | Interpretation / Action | Override Key in `config.json` |
| :--- | :--- | :--- | :--- |
| **Target Compa-Ratio Range** | `0.85 – 1.15` | `0.85–0.95` Developing; `0.95–1.05` Market Midpoint; `1.05–1.15` High Performer | `compa_ratio_min`, `compa_ratio_max` |
| **Below-Band Compression Alert** | `< 0.80` | Flag for equity/merit market adjustment review | `compa_ratio_underpaid_alert` |
| **Above-Band Ceiling Alert** | `> 1.25` | Requires VP Compensation approval for further base increases | `compa_ratio_overpaid_alert` |
| **Small-Cell Privacy Floor** | `n >= 5` | Suppress group average comp/attrition metrics for cells with `< 5` FTEs | `min_privacy_cell_size` |
| **Annual Hours (Hourly Normalization)** | `2080 hours` | Convert hourly pay to annual equivalent (`rate * 2080`) before band lookup | `annual_working_hours` |
