# Test Scenarios: `kpi-anomaly-driver-tree`

## Scenario 1 — Live Enterprise Connectors: Zero-Residual Volume-Mix-Rate Bridge
- **Prompt:** "Explain Veloce SuperApp's Q3-to-Q4 net revenue change across Ride, Food, and Mart segments from BigQuery."
- **Assertions:**
  - Verifies `volume_effect + mix_effect + rate_effect == total_delta` (`bridge_residual ~ 0`).
  - Highlights the primary variance driver segment.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Sheets KPI Table Anomaly Alert
- **Prompt:** "Check our Revenue KPI Sheet in Shared Drive for statistically anomalous drops (`|z| >= 2.0`) and small-sample alerts."
- **Assertions:**
  - Flags anomalous segments with `is_anomaly: true` and marks `< 30` observations with `low_sample_caution: true`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local CSV Segment Upload with Truncation Warning
- **Prompt:** "Run `mix_rate_volume_bridge.py` on `kpi_segments.json` marked truncated."
- **Assertions:**
  - Emits `TRUNCATION_WARNING` and avoids claiming full-company totals.
