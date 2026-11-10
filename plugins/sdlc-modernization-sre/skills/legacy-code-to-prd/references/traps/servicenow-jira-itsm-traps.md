# Trap Guide: ServiceNow & Jira ITSM API Traps (`servicenow-jira-itsm-traps`)

## Critical Pitfalls in ITSM Triage, CAB & Problem Analytics

1. **ServiceNow Numeric `state` vs. `sysparm_display_value=all`**
   - ServiceNow stores `state`, `priority`, `impact`, and `urgency` as integers (`state=1` New, `2` In Progress, `3` On Hold, `6` Resolved, `7` Closed, `8` Canceled), and custom workflows add tenant-specific numeric codes (e.g., `state=-5` Pending Change).
   - Reference fields (`assignment_group`, `cmdb_ci`, `assigned_to`) return 32-character hex `sys_id`s unless `sysparm_display_value=true` or `all` is requested. Querying `assignment_group=Network` fails silently when `sys_id` is expected (`assignment_group.name=Network`).
   - **Mitigation:** Request `sysparm_display_value=all` (which returns both `value` and `display_value`) and normalize `state_code` -> canonical label via explicit config mapping rather than assuming `state >= 6` means resolved without checking `canceled=8`.

2. **`sys_id` Joins & Missing CMDB CI Hierarchy**
   - Incidents linked to a `cmdb_ci` leaf server may have their upstream `business_service` stored in `cmdb_rel_ci` rather than on the incident row itself. Counting blast radius strictly by `cmdb_ci` string misses downstream service dependencies.
   - Always check `X-Total-Count` response header and `sysparm_offset` pagination; ServiceNow Table API caps unpaginated fetches at `sysparm_limit` (typically `1000` or `10000`).

3. **SLA Business-Elapsed Time vs. Wall-Clock Time**
   - `sys_created_on` to `resolved_at` measures **24x7 wall-clock time**, NOT contractual `task_sla.business_percentage` / `business_duration` (which pauses during `"Awaiting User Info"` / `On Hold` and honors regional business-hours schedules like `8x5` vs `24x7`).
   - Comparing raw wall-clock duration against an `8x5` SLA threshold creates false SLA breach alerts. Always check `sla_paused_minutes` and `schedule_type` (`24x7` vs `8x5`) when calculating breach status.

4. **Jira Multi-Instance Regional Routing & JQL Field Name vs. Custom Field ID**
   - Enterprise tenants often run separate Jira Cloud sites or Jira Data Center shards (`emea`, `apac`, `amer`) with distinct `customfield_XXXXX` IDs for `Severity`, `Change Risk`, or `Customer ARR`.
   - JQL searches without `startAt` + `maxResults` loop silently truncate at `50` or `100` issues (`total > startAt + len(issues)`). Always verify `total` in Jira `/rest/api/3/search/jql` responses.
   - Jira `statusCategory` (`To Do`, `In Progress`, `Done`) is consistent across workflows even when custom `status.name` differs (`QA Verify`, `CAB Pending`).
