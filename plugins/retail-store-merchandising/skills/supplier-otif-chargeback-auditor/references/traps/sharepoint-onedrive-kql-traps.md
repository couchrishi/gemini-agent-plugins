# Trap Guide: SharePoint & OneDrive KQL Traps (`sharepoint-onedrive-kql-traps`)

## Common Microsoft 365 Search & Content Pitfalls

1. **KQL `path:` Trailing Slash & Subsite Scoping**
   - In SharePoint / Microsoft Search KQL, `path:"https://tenant.sharepoint.com/sites/Finance"` also matches `/sites/FinanceSandbox` or `/sites/FinanceArchive` unless closed with a trailing `/` or exact `SiteId` filter.
   - **Mitigation:** Always scope by explicit `SiteId` / `ListId` or append trailing slash (`path:"https://.../sites/Finance/"`) and exclude sandbox/archive site URLs explicitly.

2. **KQL Managed Property Restrictions & Exact String Matching**
   - Free-text search inside body vs managed properties (`Title:`, `Author:`, `FileType:`, `LastModifiedTime>=`) behaves differently: unmapped custom SharePoint columns are NOT KQL-searchable unless crawled into `RefinableStringXX` managed properties.
   - Unquoted multi-word property filters (`Title:Board Deck`) bind `Title:` only to `"Board"` and search `"Deck"` across full text. Always quote multi-word KQL values (`Title:"Board Deck"`).

3. **Sensitivity Labels, IRM Encryption & Partial Indexing**
   - Files tagged with Microsoft Purview `Confidential` / `Highly Confidential` encryption or Information Rights Management (`IRM`) may return metadata (`Title`, `LastModifiedTime`) in Microsoft Graph search while body extraction returns empty — making an encrypted policy look "blank" or unmatched.
   - **Mitigation:** Check `sensitivityLabel` / `irmProtected` metadata; never declare a document irrelevant solely because body snippet is empty when `size > 0` and restricted label is present.

4. **List Item vs. Document Library Pagination & Major/Minor Versions**
   - SharePoint document libraries with `Minor Versions (Draft)` enabled separate `OData__UIVersionString` (`1.0` published vs `1.2` unapproved draft). Agents indexing `1.2` treat unapproved SOP edits as official policy.
   - **Mitigation:** Filter for major published versions (`_ModerationStatus == 0` / integer version `.0`) when answering authoritative policy queries, or flag `UNPUBLISHED_DRAFT_VERSION` explicitly.
   - Check `@odata.nextLink` for every Graph `/items` and `/search/query` call (default page size varies from 25 to 200).
