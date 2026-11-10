# Trap Guide: SharePoint & OneDrive KQL Traps (`sharepoint-onedrive-kql-traps`)

> **Applies to:** Authoritative policy Q&A, RFP answer-library grounding, contract clause search, brand copy compliance, and M365 SharePoint / OneDrive search fallback (`enterprise-knowledge-hub`, `deal-desk-rfp-engine`, `legal-contract-desk`, `brand-campaign-studio`, `retail-store-merchandising`).

## 1. Executive Summary Matrix

| Trap ID | Microsoft 365 Trap | Silent Failure Pattern | Exact KQL / Graph API Fix |
| :--- | :--- | :--- | :--- |
| `TRAP-SP-01` | Prefix `path:` match leakage | `path:"https://.../sites/Finance"` matches `.../sites/FinanceSandbox` and `.../sites/FinanceArchive` | Close URL with trailing `/` (`path:"https://.../sites/Finance/"`) or filter `SiteId` |
| `TRAP-SP-02` | Unquoted multi-word KQL filters | `Title:Travel Policy` binds `Title:` only to `"Travel"` and full-text searches `"Policy"` | Wrap multi-word managed properties in quotes: `Title:"Travel Policy"` |
| `TRAP-SP-03` | Uncrawled custom columns | Custom SharePoint library columns fail silently unless mapped in Search Schema | Query mapped `RefinableStringXX` / `RefinableDateXX` managed properties |
| `TRAP-SP-04` | Purview IRM / sensitivity-label blind body | Encrypted `Confidential` files return `size > 0`, `Title`, and **empty snippet** | Inspect `sensitivityLabel` / `irmProtected`; report `UNVERIFIED_INSUFFICIENT_SCOPE`, never `"blank"` |
| `TRAP-SP-05` | Minor draft version (`1.2`) pollution | Search surfaces unapproved draft edits (`_ModerationStatus != 0`) over published `2.0` | Enforce major published filter (`is_draft == False`, integer version `.0`) |
| `TRAP-SP-06` | Silent Graph `@odata.nextLink` cap | Microsoft Graph `/search/query` & `/items` truncate at `25–200` hits silently | Follow `@odata.nextLink` / check `moreResultsAvailable`; emit `TRUNCATION_WARNING` otherwise |

## 2. Detailed KQL & Microsoft Graph Walkthroughs

### Case A — Site URL Prefix Leakage & Sandbox Contamination

- **Scenario:** An enterprise hosts production policies under `/sites/Legal/` (`MSA Playbook v4`) alongside a testing sandbox `/sites/LegalSandbox/` (`2023 Test Playbook — Unlimited Indemnity Permitted`).
- **Unsafe KQL:**
  ```kql
  path:"https://cymbal.sharepoint.com/sites/Legal" "Limitation of Liability"
  ```
- **Why It Breaks:** SharePoint KQL evaluates `path:` as a raw string prefix! Documents inside `LegalSandbox` and `LegalArchive` match identically to production `Legal`, poisoning contract redline guidance with sandbox rules.
- **Safe KQL Pattern:**
  ```kql
  path:"https://cymbal.sharepoint.com/sites/Legal/" NOT path:"/sites/Legal/Archive/" "Limitation of Liability"
  ```

### Case B — Minor Draft Version (`2.1`) vs Published Policy (`2.0`)

- **Scenario (`policy_sop_answering.py`):** HR saves an unapproved travel cap proposal (`version = "2.1"`, `is_draft = True`, `status = "draft"`, `$400/night`) in SharePoint (`LastModifiedTime = 2026-11-08`), while the officially ratified policy remains `version = "2.0"` (`$275/night`, `status = "published"`).
- **Naive Failure:** Ranking documents solely by recency (`LastModifiedTime DESC`) cites `$400/night` from an unapproved minor draft (`OData__UIVersionString = 2.1`) as current corporate policy.
- **Guarded Outcome:** `enterprise-knowledge-hub` enforces `allow_draft_versions_in_answers = False` in `config.json`. Minor/draft files are excluded from authoritative answers (or quarantined separately as unapproved WIP) while `CL-US-1` (`$275/night`) governs.

### Case C — Purview IRM / Sensitivity Label Extraction Trap

- **Symptom:** Files encrypted under Microsoft Purview `Confidential` or `Highly Confidential` Information Rights Management (`IRM`) return valid directory metadata (`Name`, `Author`, `LastModifiedDateTime`, `size: 428190`) in Graph responses, yet search extraction returns `snippet = ""` (empty text) when the service account lacks decryption rights!
- **Mandatory Safeguard:** Check `sensitivityLabel` / `irmProtected` metadata whenever `size > 0` and text body is empty. Surface `UNVERIFIED_INSUFFICIENT_SCOPE` with a direct SharePoint file URL for authorized human opening — never claim *"The file is empty or contains no exclusions."*

### Case D — Pagination & Batch Ceiling Protection

- Microsoft Graph `/v1.0/search/query` defaults to `from=0`, `size=25` (max `500` per request) and returns `moreResultsAvailable: true` alongside `total`.
- Document library listings (`/drives/{driveId}/items/{itemId}/children`) cap at `200` items per page and rely on `@odata.nextLink`. Failure to follow `@odata.nextLink` silently omits files beyond row `200`.

## 3. Programmatic Ingestion & Citation Checklist

1. **Always check `is_draft`, `status`, and `version`:** Only major published policies (`status in {"published", "approved"}` and `not is_draft`) count toward authoritative compliance baselines unless `allow_draft_versions_in_answers == True`.
2. **Apply Authoritative Source Weights (`config.json`):** Score overlapping SharePoint/Confluence/Drive hits deterministically (`official_policy: 1.0`, `approved_sop: 0.9`, `knowledge_article: 0.8`, `slide_deck: 0.5`, `chat_thread: 0.3`).
3. **Require Citation Parity (`min_citation_coverage_pct = 100.0`):** Flag every policy claim in synthesized drafts lacking a mapped `cited_source_id` (`UNCITED_CLAIM`), and propagate any Graph `moreResultsAvailable` gap into `truncation_warnings`.

```python
def is_authoritative_sharepoint_doc(item: dict) -> bool:
    status = str(item.get("status") or "").strip().lower()
    version = str(item.get("version") or "1.0").strip()
    is_draft = bool(item.get("is_draft", False)) or status in {"draft", "superseded", "archived"}
    is_minor_ver = "." in version and not version.endswith(".0")
    return not is_draft and not is_minor_ver
```

## 4. Microsoft Graph & SharePoint KQL Guard Table

| KQL / Graph Vector | Failing Query / Field Usage | Silent Error Mechanism | Hardened Guard Syntax |
| :--- | :--- | :--- | :--- |
| **Site Scope Filter** | `path:"https://tenant.sharepoint.com/sites/HR"` | Matches `/sites/HRSandbox` & `/sites/HRArchive` via string prefix | Close with `/` (`.../sites/HR/`) + exclude `/Archive/` |
| **Managed Property** | `Title:Vendor Security Policy` | Binds `Title:` only to `"Vendor"`; searches rest across body | Wrap exact phrase: `Title:"Vendor Security Policy"` |
| **Custom Library Column** | `Region:EMEA` | Uncrawled column name matches `0` results or treats as keyword | Query mapped crawl slot (`RefinableString04:"EMEA"`) |
| **Minor Draft Filtering** | Sort by `LastModifiedTime DESC` without filter | Unapproved minor revision `1.4` overrides published `1.0` | Filter `_ModerationStatus=0` / `.0` integer version |
| **Encrypted Purview IRM** | Assume empty snippet = empty document | Protected PDFs hide body text while keeping `size > 0` | Check `sensitivityLabel` / `irmProtected` -> `UNVERIFIED_INSUFFICIENT_SCOPE` |
| **Pagination** | First Graph `/search/query` call (`size=25`) | Drops hits `26..N` without exception | Inspect `moreResultsAvailable` & `@odata.nextLink` |

## 5. Authoritative Policy Retrieval Checklist

1. Restrict policy retrieval to major published revisions unless the user explicitly asks to inspect pending drafts (`allow_draft_versions_in_answers = true`).
2. Preserve exact `[Site > Library > File Name > Version]` attribution on every numeric limit (`$275/night`, `60d notice`).
3. Quarantine encrypted/IRM-locked items explicitly as unreadable without guessing missing text or reporting `"no conflicts found"`.
4. Emit `TRUNCATION_WARNING` whenever Graph pagination terminates prior to exhausting `total` results.

## 6. Microsoft Graph Search Envelope & IRM Verification

```python
def inspect_graph_search_hit(hit: dict) -> tuple[str, list[str]]:
    """Verify Microsoft Graph Search hits for Purview IRM locks and unpublished drafts."""
    flags: list[str] = []
    resource = hit.get("resource") or {}
    summary = str(hit.get("summary") or "").strip()
    size = int(resource.get("size") or 0)
    if bool(resource.get("irmProtected")) or (resource.get("sensitivityLabel") and size > 0 and not summary):
        flags.append("UNVERIFIED_INSUFFICIENT_SCOPE: IRM/Purview encrypted body unreadable.")
    if not is_authoritative_sharepoint_doc(resource):
        flags.append("UNPUBLISHED_DRAFT_VERSION")
    return summary, flags
```

- Always escape double quotes inside user search keywords before injecting into KQL managed-property filters.
- Cross-check OneDrive personal sharing paths against corporate SharePoint production libraries so personal scratch notes never override SOPs.
