# Starter Baseline: FSI Credit Underwriting, KYB/UBO & Claims Rubric (`fsi-credit-kyc-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, every deliverable MUST carry this exact top banner verbatim:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Commercial Credit Underwriting Covenant & Stress Matrix (`commercial-credit-memo-analyst`)

| Financial Covenant Ratio | Base Covenant Pass | Watchlist Zone | Hard Covenant Breach | Stress Scenarios & Override Key(s) |
| :--- | :--- | :--- | :--- | :--- |
| **Debt Service Coverage (`DSCR`)** | `>= 1.25x` (`EBITDA / (Interest + Principal)`) | `1.10x <= DSCR < 1.25x` | `< 1.10x` (`BREACH`) or Watch `< 1.25x` (`config.min_dscr`) | `-10%` & `-20%` Revenue shock; `+200 bps` floating-rate shock (`min_dscr`, `stress_rate_shock_bps`) |
| **Net Leverage (`Net Debt / EBITDA`)** | `<= 3.50x` (`(Debt - Cash) / EBITDA`) | `3.50x < Lev <= 4.25x` | `> 4.25x` or Watch `> 3.50x` (`config.max_net_leverage`) | Floating debt service shock + EBITDA compression (`max_net_leverage`) |
| **Interest Coverage (`ICR`)** | `>= 2.50x` (`EBITDA / Interest`) | `2.00x <= ICR < 2.50x` | `< 2.00x` or Watch `< 2.50x` | Pro-forma rate shock adds `floating_debt * (bps / 10000)` (`min_interest_coverage`) |
| **Current Liquidity Ratio** | `>= 1.15x` (`Current Assets / Current Liab`) | `1.00x <= CR < 1.15x` | `< 1.00x` or Watch `< 1.15x` | Working-capital stress check (`min_current_ratio`) |

- **Negative / Zero EBITDA Guard:** Whenever `ebitda_usd <= 0`, `Net Leverage` returns `INF` / `None` (`BREACH_NEGATIVE_EBITDA`) rather than misleadingly looking like negative leverage (`-3.0x`)!
- **Python Covenant Gate (`credit_covenant_stress.py`):** Credit committee release flags any `base_breach_count > 0` or stress breach for explicit Credit Committee override confirmation.

## 2. KYB Beneficial Ownership (UBO) & AML Transaction Monitoring Matrix (`kyc-aml-screening-dossier`)

| Risk Control | Standard Baseline Default | Escalation / EDD Trigger Condition | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- |
| **Standard Beneficial Ownership Floor** | `>= 25.0%` cumulative effective ownership | Direct + multi-hop indirect ownership product paths (`sum(chain_products)`) | `ubo_standard_pct` |
| **Enhanced Due Diligence (EDD) Floor** | Drops automatically to `>= 10.0%` | Triggered when ANY entity/UBO touches a high-risk jurisdiction (e.g., `KY`), PEP, or sanctioned region | `ubo_edd_pct` |
| **Velocity Spike Alert** | Rolling 30-day volume `>= 3.0x` trailing 90d monthly avg | Flags sudden rapid money-movement acceleration (`VELOCITY_SPIKE`) | `velocity_spike_multiplier` |
| **Structuring / Smurfing Count** | `>= 5` structured near-reporting-threshold deposits | Flags split deposits just below `$10,000` (`$9,000–$9,999`) | `structuring_count_threshold` |
| **Multi-Hop Cycle & Self-Ownership** | Graph traversal with cycle prevention | Never hang on circular holding structures; deduplicate multi-path UBO sums | Automated DAG walk per UBO |

## 3. Property, Casualty & Cyber Claims Triage Matrix (`insurance-claims-triage-pack`)

| Validation Step | Deterministic Decision Rule | Claim Outcome Status | `config.json` Override Key(s) |
| :--- | :--- | :--- | :--- |
| **1. Policy Period Coverage** | Verify `policy.effective_date <= loss_date <= policy.expiration_date` | Outside window -> `DENIED_OUTSIDE_POLICY_PERIOD` | Policy payload dates |
| **2. Peril Exclusion Check** | Match claim `peril` against normalized `policy.excluded_perils` | Match -> `DENIED_EXCLUDED_PERIL` (`$0.00` payout) | Policy exclusion list |
| **3. Documentation & Evidence** | Verify `documentation_complete == true` before calculating payable | Incomplete -> `PENDING_DOCUMENTATION_HOLD` | Intake completeness check |
| **4. Financial Waterfall** | Apply `min(claimed - deductible, peril_sublimit, remaining_aggregate) * (coinsurance_pct / 100)` | Compute exact net payable & reserve obligation | Waterfall math |
| **5. High-Value Escalation** | Check whether computed net payable `>= $100,000.00` | Net payable `>= threshold` -> `RESERVE_ESCALATION_HITL` | `high_value_claim_threshold` |

## 4. FSI Compliance & HITL Governance Guardrails

1. **Zero Autonomous SAR / Adverse-Action / Payout Submissions:** Filing SAR/STR reports, issuing formal credit decisions, or releasing claim settlements through connected Core Banking, AML, or Claims MCP servers requires Agent Gateway (`Auto-Guardian`) approval and explicit human confirmation.
2. **Evidence & Provenance Attribution:** Keep full corporate UBO traversal paths (`HoldCo 60% -> MidCo 30% = 18%` + `ParentCo 40% -> SiblingCo 25% = 10%` -> `28%`) visible in deliverables so AML investigators verify every summation.

## 5. Customizing via `config.json` & `--org-config`

```json
{
  "organization_name": "Cymbal Financial",
  "plugins": {
    "fsi-credit-kyc-claims": {
      "min_dscr": 1.35,
      "max_net_leverage": 3.25,
      "stress_rate_shock_bps": 250,
      "high_value_claim_threshold": 75000.0
    }
  }
}
```

Stamping tenant rules via `python3 tools/package.py --org-config org.json` flips `org_configured: true` across all 3 FSI engines and suppresses the baseline banner cleanly.

## 6. FSI Underwriting & KYB Threshold Calibration Example

| Scenario / Entity Input | Standard Baseline (`org_configured=false`) | Cymbal Strict Config (`min_dscr=1.35`, `max_net_leverage=3.25`) | Resulting Governance Verdict |
| :--- | :--- | :--- | :--- |
| **DSCR = `1.28x`, Lev = `3.40x`** | Base **PASS** (`>= 1.25x`, `<= 3.50x`) | **WATCH / BREACH** (`< 1.35x`, `> 3.25x`) | Demonstrates `--org-config` custom policy enforcement |
| **Cayman HoldCo Indirect Stack** | EDD `ubo_edd_pct = 10.0%` (`< 25%` std) | Tenant EDD override if stricter | Flags `28%` (`18% + 10%`) effective owner cleanly |
| **Rolling 30d Volume = `3.2x` Base** | Triggers `VELOCITY_SPIKE` (`>= 3.0x`) | Tenant velocity alert | Routes analyst packet toward SAR prep review (HITL) |
| **Cyber Ransomware Net `$120,000`** | Exceeds `$100,000` reserve floor | Triggers reserve escalation at configured cap | Emits `RESERVE_ESCALATION_HITL` despite covered peril |

## 7. FSI Model Risk & Compliance Verification Checklist

1. Run simultaneous `-10%` / `-20%` revenue and `+200 bps` floating-rate stress tests on every commercial credit underwriting file (`commercial_credit_memo_analyst`).
2. Flatten multi-hop corporate ownership trees cleanly while normalizing joint/trust structures and preventing circular graph loops (`kyc_aml_screening_dossier`).
3. Verify `loss_date` falls strictly inside policy bounds and deductibles/sublimits/coinsurance apply in exact contractual sequence (`insurance_claims_triage_pack`).
4. Require Agent Gateway (`Auto-Guardian`) and explicit human confirmation before filing any SAR/STR report, submitting adverse credit actions, or releasing claim reserves.

## 8. FSI Write Governance (`Auto-Guardian` & Python Guards)

- **Covenant Breach Escalation:** Whenever `credit.base_breach_count > 0`, hold credit approval summaries for Risk Committee review before posting externally.
- **AML / SAR Filing & Claim Release Gate:** Agent Gateway (`Auto-Guardian`) and explicit compliance/adjuster confirmation block autonomous SAR submissions or high-value settlement releases.
- **Python code invariants (`scripts/*.py`):** Enforce transitive UBO graph cycle protection, structuring anomaly flags, and contractual deductible/sublimit ordering deterministically.

Recurring FSI `schedule_task` routines (such as `Daily AML & KYB Velocity Watch`) execute `analyze()` against live transactions when scheduled, emit alerts via `emit_a2ui`, and hold outbound SAR/settlement filings behind human sign-off.
