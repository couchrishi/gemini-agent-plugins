# Starter Baseline: Commercial Contract & Regulatory Rubric (`commercial-contract-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, stamp the deliverable header verbatim with:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Risk Scoring Scale (`1 / 3 / 9` Severity Matrix)

| Score | Band | Meaning | Required Action |
| :--- | :--- | :--- | :--- |
| **1** | **Low / Acceptable** | Minor wording variation within standard commercial tolerances | Accept or log informational note |
| **3** | **Moderate / Negotiable** | Deviation from preferred fallback requiring redline or business sign-off | Propose fallback language + commercial trade-off |
| **9** | **Critical / Walk-Away Blocker** | Uncapped exposure, IP assignment loss, or statutory/regulatory violation | Escalate to General Counsel / Legal Lead; block signature |

## 2. Default Commercial Clause Rubrics (NDA / SaaS MSA / DPA / SOW)

| Clause Family | Standard Position (`Score 1`) | Negotiable Fallback (`Score 3`) | Blocker Trigger (`Score 9`) | Override Key in `config.json` |
| :--- | :--- | :--- | :--- | :--- |
| **Limitation of Liability (LoL)** | Mutual cap at `12 months` trailing fees | Cap up to `24 months` fees or fixed `$2M` floor | Uncapped general liability or cap `< 6 months` fees for Vendor failure | `lol_cap_months_min`, `lol_cap_months_max` |
| **Super-Cap (Data / IP / Sec)** | `2x` general cap for breach of confidentiality or DPA | `3x` general cap with documented cyber insurance | Uncapped consequential damages for general SLA breaches | `super_cap_multiplier_max` |
| **Auto-Renewal & Notice Window** | Explicit opt-in renewal or `<= 30 days` notice | Auto-renewal with `<= 60 days` notice & CPI cap `<= 5%` | Silent evergreen auto-renewal with `> 90 days` notice or uncapped uplift | `max_renewal_notice_days`, `max_price_escalator_pct` |
| **Governing Law & Venue** | Delaware / New York / England & Wales / Singapore | Mutual neutral arbitration (ICC / SIAC / AAA) | Unfamiliar local court with waiver of jury/statutory appeal or unilateral choice | `approved_jurisdictions` |
| **IP & Customer Data Rights** | Customer owns all Customer Data & Pre-Existing IP; Vendor owns Platform | Jointly configured outputs licensed perpetually for internal use | Vendor claims ownership or unrestricted AI training rights over Customer Data | `forbid_customer_data_training` |
| **DPA / Breach Notification** | `<= 48 hours` notice after confirmed security incident | `<= 72 hours` aligned with GDPR Art. 33 | `> 72 hours` or `"commercially reasonable"` vague timing | `max_breach_notify_hours` |
| **SOW Scope & Margin Guard** | Fixed deliverables, explicit assumptions, `>= 30%` gross margin | Milestone acceptance `<= 10 business days` deemed-accepted | Unbounded `"all work required"` phrasing or margin `< 20%` | `min_sow_gross_margin_pct` |
