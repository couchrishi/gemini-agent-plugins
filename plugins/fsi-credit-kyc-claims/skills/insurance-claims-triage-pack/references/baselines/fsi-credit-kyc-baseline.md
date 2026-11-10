# Starter Baseline: FSI Credit Underwriting, KYB/UBO & Claims Rubric (`fsi-credit-kyc-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, stamp the deliverable header verbatim with:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Commercial Credit Underwriting Ratios & Covenant Thresholds

| Financial Ratio | Standard Covenant Floor / Ceiling | Stress Test Shock Scenarios | Override Key in `config.json` |
| :--- | :--- | :--- | :--- |
| **Debt Service Coverage Ratio (DSCR)** | `>= 1.25x` (`Watch < 1.25x`, `Breach < 1.10x`) | `-10%` & `-20%` Revenue shock; `+200 bps` interest rate shock | `min_dscr`, `stress_rate_shock_bps` |
| **Net Leverage (`Net Debt / EBITDA`)** | `<= 3.50x` (`Watch > 3.50x`, `Breach > 4.25x`) | Pro-forma debt drawdown + EBITDA margin compression | `max_net_leverage` |
| **Interest Coverage (`EBITDA / Interest`)** | `>= 2.50x` | Combined revenue drop and floating-rate reset | `min_interest_coverage` |
| **Current Ratio (`Current Assets / Current Liab`)** | `>= 1.15x` | Working capital liquidity covenant | `min_current_ratio` |

## 2. KYB / AML Ownership & Transaction Velocity Thresholds

- **Standard UBO Threshold:** `>= 25.0%` cumulative effective ownership across direct and multi-hop indirect corporate layers (`ubo_standard_pct = 25.0`).
- **Enhanced Due Diligence (EDD) UBO Threshold:** `>= 10.0%` when any entity touches a high-risk jurisdiction, PEP, or cash-intensive vertical (`ubo_edd_pct = 10.0`).
- **Transaction Velocity Spike Alert:** Rolling 30-day transaction volume `>= 3.0x` trailing 90-day monthly baseline (`velocity_spike_multiplier = 3.0`) or `>= 5` structured near-threshold deposits (`structuring_count_threshold = 5`).

## 3. Insurance Claims Triage Rules

- Verify `loss_date` falls strictly within `[policy_effective_date, policy_expiration_date]`.
- Apply **per-occurrence deductible**, **coverage sub-limits**, and **coinsurance percentage** deterministically; flag `RESERVE_ESCALATION` whenever net payable exceeds `$100,000` (`high_value_claim_threshold = 100000`).
