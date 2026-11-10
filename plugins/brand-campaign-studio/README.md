# Brand Governance, Campaign Matrix & Localization Studio (`brand-campaign-studio`)

Lints marketing copy against brand voice rules, prohibited claims, and channel limits, validates audience-by-channel multimodal campaign matrices, and audits global localization packs against do-not-translate glossaries.

## Included Workflow Skills

1. **`brand-voice-compliance-gate`** ([SKILL.md](skills/brand-voice-compliance-gate/SKILL.md)) — Lints marketing copy for banned guarantees, missing substantiation disclaimers, readability density, and channel char caps.
2. **`multimodal-campaign-brief`** ([SKILL.md](skills/multimodal-campaign-brief/SKILL.md)) — Audits audience-by-channel and funnel coverage matrices, planned spend vs budget, and critical-path launch buffers.
3. **`market-localization-adapter`** ([SKILL.md](skills/market-localization-adapter/SKILL.md)) — Verifies target locale translations for missing markets, untranslated leaks, DNT term preservation, and regional glossary fidelity.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/brand-campaign-studio.zip`
- **Granular 1-Hop Upload:** `dist/skills/brand-voice-compliance-gate.zip`, `dist/skills/multimodal-campaign-brief.zip`, `dist/skills/market-localization-adapter.zip`
