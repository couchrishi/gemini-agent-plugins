# Commercial Credit Memo & Stress Analyst (`commercial-credit-memo-analyst`)

Computes commercial credit covenant ratios (DSCR, Net Leverage, Interest Coverage, Liquidity) across Base Case and multi-factor revenue and interest rate stress shocks. Deterministic computation executes via [`scripts/credit_covenant_stress.py`](scripts/credit_covenant_stress.py). Domain guards enforced: Applies both operating-leverage EBITDA contraction and floating-rate +200bps shocks; Distinguishes Watch vs Breach covenants deterministically. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Commercial Credit Underwriter**: Triggered when preparing credit committee memos for leveraged mid-market corporate borrowers; evaluates DSCR (`>=1.25x`), Net Leverage (`<=3.50x`), Interest Coverage, and Current Ratio under both base and `-20% EBITDA / +200bps` stress.
- **Portfolio Risk Officer**: Triggered when monitoring covenant Watch Zones vs formal Covenant Breaches across floating-rate portfolios; routes borderline `WATCH_ALERT` vs `COVENANT_BREACH` names (`BORR-CYM-01`) cleanly before committee voting.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`commercial-credit-memo-analyst.zip`](../../../../dist/skills/commercial-credit-memo-analyst.zip) (or the full department bundle [`fsi-credit-kyc-claims.zip`](../../../../dist/bundles/fsi-credit-kyc-claims.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` + Customer BYO-MCP (`KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/commercial-credit-memo-analyst` or `@commercial-credit-memo-analyst`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.credit_covenant_stress import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"borrowers": [{"borrower_id": r.get("Custom borrower_id"), "ebitda_usd": r.get("Custom ebitda_usd"), "total_debt_usd": r.get("Custom total_debt_usd")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/fsi-credit-kyc-claims/skills/commercial-credit-memo-analyst/scripts/credit_covenant_stress.py \
  --input examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx \
  --config plugins/fsi-credit-kyc-claims/skills/commercial-credit-memo-analyst/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `credit_covenant_stress.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` + Customer BYO-MCP (`KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`) via `remote_cli mcp`):** "Stress-test Cymbal Financial's borrower spread with $12M EBITDA, $42M floating debt, under -20% revenue and +200bps."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Borrower Credit Spread Sheet in Drive with 4.5x Net Leverage and 1.05x Base DSCR."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx) and ask: "Using the borrower financial spreads in `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`, underwrite DSCR, Net Leverage, Interest Coverage, and Current Ratio under Base Case, `-10% Rev / +100bps`, and `-20% Rev / +200bps` stress scenarios, separating Watch Zones from formal Covenant Breaches."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `2` corporate borrowers across `3` stress scenarios in `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` flagged **`BORR-CYM-01` (Meridian Maritime Holdings) in Base-Case `WATCH_ALERT` (`3.99x` Net Leverage > `3.50x`, `1.14x` Current Ratio) escalating to `COVENANT_BREACH` under both `-10%/+100bps` and `-20%/+200bps` stress (`0.94x` DSCR, `5.69x` Net Leverage)**, while `BORR-STR-02` passed cleanly.

- **`BORR-CYM-01` (Meridian Maritime Holdings):** Base `1.46x` DSCR holds above `1.25x`, yet leverage (`3.99x`) and liquidity (`1.14x`) sit in Watch Zone before collapsing to `0.94x` DSCR / `5.69x` Net Leverage (`COVENANT_BREACH`) under severe `-20% / +200bps` shock.
- **`BORR-STR-02` (Kestrel Logistics Corp):** Remains `COVENANT_COMPLIANT` across all three scenarios (`3.16x` base DSCR / `1.68x` leverage down to `2.09x` DSCR / `2.40x` leverage under severe stress).
- **Approval Confirmation Prompt:** Confirm Credit Committee determination and covenant waiver requirements before committing the loan decision via your connected credit origination / loan MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx`](../../../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx) (`135.8 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Commercial Credit Covenant & Stress Underwriting Memo

- **Borrowers Evaluated:** 2 | **Base Covenant Breaches:** 0 | **Severe Stress Breaches:** 1

| Borrower | Scenario | DSCR | Net Leverage | Int Cov | Status | Notes |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `BORR-CYM-01` Meridian Maritime Holdings | Base Case | 1.46x | 3.99x | 3.54x | `WATCH_ALERT` | Net Leverage 3.99x > 3.50x covenant; Current Ratio 1.14x < 1.15x |
| `BORR-CYM-01` Meridian Maritime Holdings | -10% Rev / +100bps | 1.19x | 4.69x | 2.71x | `COVENANT_BREACH` | Net Leverage 4.69x > 4.25x breach; DSCR 1.19x < 1.25x covenant; Current Ratio 1.14x < 1.15x |
| `BORR-CYM-01` Meridian Maritime Holdings | -20% Rev / +200bps | 0.94x | 5.69x | 2.04x | `COVENANT_BREACH` | DSCR 0.94x < 1.10x breach; Net Leverage 5.69x > 4.25x breach; Interest Coverage 2.04x < 2.50x; Current Ratio 1.14x < 1.15x |
| `BORR-STR-02` Kestrel Logistics Corp | Base Case | 3.16x | 1.68x | 7.76x | `COVENANT_COMPLIANT` | Meets covenants |
| `BORR-STR-02` Kestrel Logistics Corp | -10% Rev / +100bps | 2.61x | 1.98x | 6.15x | `COVENANT_COMPLIANT` | Meets covenants |
| `BORR-STR-02` Kestrel Logistics Corp | -20% Rev / +200bps | 2.09x | 2.40x | 4.74x | `COVENANT_COMPLIANT` | Meets covenants |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily KYB Velocity & Structuring Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily KYB Velocity & Structuring Watch" on cron `0 5 * * *` (`UTC`) with instruction: "Run the daily AML transaction velocity and structuring sweep via scripts/ubo_velocity_screener.py across active corporate banking accounts and flag EDD alerts for MLRO review."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `borrowers`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `borrowers` requires [`borrower_id` or `borrower_name`; `ebitda_usd`; `total_debt_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_dscr` | `number` | `1.25` | Minimum Debt Service Coverage Ratio covenant floor. |
| `max_net_leverage` | `number` | `3.5` | Maximum Net Debt / EBITDA covenant ceiling. |
| `min_interest_coverage` | `number` | `2.5` | Minimum EBITDA / Interest Coverage floor. |
| `min_current_ratio` | `number` | `1.15` | Minimum liquidity current ratio floor. |
| `stress_rate_shock_bps` | `integer` | `200` | Severe floating-rate interest rate shock in basis points. |

See [`../../README.md`](../../README.md) for the `fsi-credit-kyc-claims` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
