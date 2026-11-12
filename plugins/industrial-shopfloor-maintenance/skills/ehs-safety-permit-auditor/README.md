# EHS Permit-to-Work & LOTO Safety Auditor (`ehs-safety-permit-auditor`)

Audits high-hazard Permit-to-Work packages against Lockout/Tagout isolation, atmospheric O2/LEL safety tolerances, gas-test recency, fire watch, and worker certifications. Deterministic computation executes via [`scripts/hse_permit_checker.py`](scripts/hse_permit_checker.py). Domain guards enforced: Blocks missing gas test or expired worker certs unconditionally; Enforces 19.5%-23.5% O2, 0.0% LEL, and <=60 min test freshness. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **EHS Safety Officer / Shift Supervisor**: Triggered when clearing Confined-Space, Hot-Work, and Lockout-Tagout (LOTO) maintenance permits; enforces hard physical safety interlocks (`19.5%–23.5% O2`, `0% LEL`, `<=60m` gas test age, active LOTO verification) with zero override tolerance.
- **Plant Turnaround Coordinator**: Triggered when pre-auditing permit packets before contractor crews mobilize at shift handover; hard-blocks incomplete or out-of-spec atmospheric readings before issuing SAP EHS clearance.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`ehs-safety-permit-auditor.zip`](../../../../dist/skills/ehs-safety-permit-auditor.zip) (or the full department bundle [`industrial-shopfloor-maintenance.zip`](../../../../dist/bundles/industrial-shopfloor-maintenance.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP PM / Shopfloor Historian & EHS Permit MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/ehs-safety-permit-auditor` or `@ehs-safety-permit-auditor`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.hse_permit_checker import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"permits": [{"permit_id": r.get("Custom permit_id"), "gas_test_lel_pct": r.get("Custom gas_test_lel_pct")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/industrial-shopfloor-maintenance/skills/ehs-safety-permit-auditor/scripts/hse_permit_checker.py \
  --input examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx \
  --config plugins/industrial-shopfloor-maintenance/skills/ehs-safety-permit-auditor/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `hse_permit_checker.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP PM / Shopfloor Historian & EHS Permit MCP server`) via `remote_cli mcp`):** "Audit Apex Manufacturing confined-space vessel permit PTW-101 with 90-min-old gas reading and loto_isolated=false."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Daily EHS Sheet where PTW-102 hot-work has no fire watch assigned and expired cert."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx) and ask: "Audit the industrial Permit-to-Work (PTW) packets in `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` as of `2026-11-10` against physical O2 (`19.5%–23.5%`), `0%` LEL gas limits, gas-reading freshness, LOTO isolation, and safety certifications."

## Sample Response

### What You See in Gemini Enterprise Chat

Safety auditing `3` active work permits in `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` as of `2026-11-10` enforced **`STOP_WORK_BLOCKED` on `2` permits (`PTW-MFG-4012` expired cert & missing fire watch; `PTW-MFG-4038` hazardous `19.1%` O2 & `2.0%` LEL gas)** and cleared **`1` electrical HV permit (`PTW-MFG-4055`)**.

- **Life-Safety Hard Stops (`2` Permits):** `PTW-MFG-4038` (`Plant-Houston-01` confined space) recorded oxygen-deficient `19.1% O2` plus explosive `2.0% LEL`, while `PTW-MFG-4012` (`Plant-Singapore-02` hot work) lacked an active fire watch and held a cert expired `2026-10-01`.
- **Zero-Override Enforcement:** Deterministic safety code guards permit zero clearance while `stop_work_blocked_count > 0` or on unsafe atmospheric readings.
- **Approval Confirmation Prompt:** Confirm if you would like to issue EHS clearance solely for compliant permit `PTW-MFG-4055` (`Plant-Munich-03`) via your connected EHS permit / ERP MCP server (`Auto-Guardian` hard-gated); `PTW-MFG-4012` and `PTW-MFG-4038` remain hard-locked.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx) (`132.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# EHS Permit-to-Work (PTW) & LOTO Safety Audit (As Of 2026-11-10)

- **Permits Audited:** 3 | **STOP WORK Blocked:** 2 | **Eligible for EHS Sign-Off:** 1

| Permit | Facility | Work Type | Status | Safety Defects |
| :--- | :--- | :--- | :--- | :--- |
| `PTW-MFG-4012` | Plant-Singapore-02 | `hot_work` | `STOP_WORK_BLOCKED` | Worker safety certification missing or expired (2026-10-01).; Dedicated Fire Watch not assigned for hot work. |
| `PTW-MFG-4038` | Plant-Houston-01 | `confined_space` | `STOP_WORK_BLOCKED` | Unsafe O2 level 19.1% (must be 19.5%-23.5%).; Flammable LEL 2.0% exceeds 0.0% limit. |
| `PTW-MFG-4055` | Plant-Munich-03 | `electrical_hv` | `ELIGIBLE_FOR_EHS_ISSUE` | All mandatory checks verified |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Critical Spares ROP Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Critical Spares ROP Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the daily critical spare parts ROP check via scripts/mtbf_spares_optimizer.py across plant rotating equipment and flag zero-stock critical assets."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `permits`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `permits` requires [`permit_id`; `gas_test_lel_pct` or `gas_test_o2_pct` or `loto_isolated`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `o2_min_pct` | `number` | `19.5` | Minimum safe confined-space O2 percentage. |
| `o2_max_pct` | `number` | `23.5` | Maximum safe confined-space O2 percentage. |
| `max_lel_pct` | `number` | `0.0` | Maximum permitted Lower Explosive Limit % for confined-space entry. |
| `max_gas_test_age_mins` | `integer` | `60` | Maximum elapsed minutes since atmospheric gas test. |

See [`../../README.md`](../../README.md) for the `industrial-shopfloor-maintenance` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
