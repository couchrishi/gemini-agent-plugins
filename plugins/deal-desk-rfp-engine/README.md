# Deal Desk, RFP & Pipeline Hygiene Engine (`deal-desk-rfp-engine`)

Equips Revenue Operations and Deal Desk teams with TF-IDF RFP answer matching, deterministic multi-year SaaS margin/discount tiering, and multi-currency Salesforce pipeline hygiene auditing.

## Included Workflow Skills

1. **`rfp-questionnaire-responder`** ([SKILL.md](skills/rfp-questionnaire-responder/SKILL.md)) — Matches incoming RFP rows against verified answer libraries via TF-IDF cosine similarity (`rfp_matrix_builder.py`), quarantining injected instructions and flagging mandatory compliance gaps.
2. **`deal-desk-quote-guard`** ([SKILL.md](skills/deal-desk-quote-guard/SKILL.md)) — Calculates Year-1 ACV, blended ACV, TCV, net effective discount, and blended gross margin (`deal_margin_validator.py`), routing non-standard terms to the exact Deal Desk approval tier.
3. **`pipeline-hygiene-slippage`** ([SKILL.md](skills/pipeline-hygiene-slippage/SKILL.md)) — Audits CRM opportunity snapshots (`pipeline_slippage_auditor.py`) for stage staleness, close-date push counts, single-threading, MEDDPICC commit gaps, and FX normalization.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/deal-desk-rfp-engine.zip`
- **Granular 1-Hop Upload:** `dist/skills/rfp-questionnaire-responder.zip`, `dist/skills/deal-desk-quote-guard.zip`, `dist/skills/pipeline-hygiene-slippage.zip`
