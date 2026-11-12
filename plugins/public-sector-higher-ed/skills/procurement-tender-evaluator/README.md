# Public Procurement Tender Weighted Evaluator (`procurement-tender-evaluator`)

Screens sealed public procurement bids for debarment, conflict-of-interest, tax clearance, and minimum technical score BEFORE normalizing commercial price scores and ranking finalists. Deterministic computation executes via [`scripts/tender_weighted_scorer.py`](scripts/tender_weighted_scorer.py). Domain guards enforced: Excludes disqualified bids from lowest_compliant_price_usd denominator; Ranks compliant bids cleanly across weighted Tech + Sust + Comm scores. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Public Procurement / Contracting Officer**: Triggered when scoring multi-vendor government RFP responses across weighted technical, sustainability, and price criteria; disqualifies debarred/sanctioned lowest bidders before normalizing `50/15/35` weighted commercial award scores.
- **Higher-Ed / Agency Sourcing Board Lead**: Triggered when documenting auditable FAR/public-tender scoring trails ahead of award notice; prevents illegal award recommendations to disqualified low-price vendors.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`procurement-tender-evaluator.zip`](../../../../dist/skills/procurement-tender-evaluator.zip) (or the full department bundle [`public-sector-higher-ed.zip`](../../../../dist/bundles/public-sector-higher-ed.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` + Customer BYO-MCP (`Grants Management & Procurement Portal MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/procurement-tender-evaluator` or `@procurement-tender-evaluator`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.tender_weighted_scorer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"bids": [{"bid_id": r.get("Custom bid_id"), "total_bid_price_usd": r.get("Custom total_bid_price_usd"), "technical_score_100": r.get("Custom technical_score_100")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/public-sector-higher-ed/skills/procurement-tender-evaluator/scripts/tender_weighted_scorer.py \
  --input examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx \
  --config plugins/public-sector-higher-ed/skills/procurement-tender-evaluator/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `tender_weighted_scorer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` + Customer BYO-MCP (`Grants Management & Procurement Portal MCP server`) via `remote_cli mcp`):** "Evaluate CivicFirst Agency RFP bids where a $120k vendor is debarred/sanctioned and compliant bids are $200k and $250k."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Procurement Bid Sheet in Drive where one bidder lacks signed COI attestation."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx) and ask: "Score the public-sector RFP vendor proposals in `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`, disqualifying any debarred or sanctioned lowest-price bidder before normalizing weighted `50/15/35` Technical, Sustainability, and Price scores."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `3` vendor bids for **`RFP-CIVIC-2026-09`** in `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` **disqualified lowest bidder `OmniGov Disqualified Corp` (`BID-01`, `$180,000.00`, `VENDOR_DEBARRED_OR_SANCTIONED`) before commercial normalization**, ranking **`CivicTech Partners` (`BID-02`, `$245,000.00`) `#1` with `94.20` weighted points** ahead of `Metro Cloud Systems` (`BID-03`, `$290,000.00`, `81.82`).

- **Debarred Denominator Guard:** Normalizing commercial scores strictly against the lowest *compliant* price (`$245,000.00`, `BID-02`) instead of disqualified `$180,000.00` prevented mathematical distortion across compliant bids.
- **Compliant Ranking:** `CivicTech Partners` scored `92.0` Tech / `88.0` Sust / `100.0` Comm (`94.20` total) vs. `Metro Cloud Systems` at `82.0` / `75.0` / `84.5` (`81.82`).
- **Approval Confirmation Prompt:** Confirm Evaluation Board sign-off before issuing the `$245,000.00` contract award recommendation to `CivicTech Partners` (`BID-02`) via your connected procurement / ERP MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx`](../../../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx) (`135.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Public Procurement Tender Evaluation Scorecard (`RFP-CIVIC-2026-09`)

- **Bids Received:** 3 | **Compliant:** 2 | **Disqualified:** 1 | **Top Ranked:** CivicTech Partners (94.20)

| Rank | Vendor | Bid Price | Tech | Sust | Comm | Weighted Score | Status | Notes |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| 1 | CivicTech Partners (`BID-02`) | $245,000.00 | 92.0 | 88.0 | 100.0 | **94.20** | `COMPLIANT_RANKED` | All gates passed |
| 2 | Metro Cloud Systems (`BID-03`) | $290,000.00 | 82.0 | 75.0 | 84.5 | **81.82** | `COMPLIANT_RANKED` | All gates passed |
| - | OmniGov Disqualified Corp (`BID-01`) | $180,000.00 | 90.0 | 80.0 | 0.0 | **0.00** | `DISQUALIFIED_NON_COMPLIANT` | VENDOR_DEBARRED_OR_SANCTIONED |

Award recommendation requires formal Procurement Evaluation Board HITL sign-off.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Grant & Accreditation Evidence Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Grant & Accreditation Evidence Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly sponsored grant allowability and accreditation artifact freshness check via scripts/grant_accreditation_validator.py across active institutional packets."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `tender_id`, `bids`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `bids` requires [`bid_id` or `vendor_name`; `total_bid_price_usd`; `technical_score_100`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `technical_weight_pct` | `number` | `50.0` | RFP technical evaluation weighting %. |
| `sustainability_weight_pct` | `number` | `15.0` | RFP sustainability / local content weighting %. |
| `commercial_weight_pct` | `number` | `35.0` | RFP normalized commercial price weighting %. |

See [`../../README.md`](../../README.md) for the `public-sector-higher-ed` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
