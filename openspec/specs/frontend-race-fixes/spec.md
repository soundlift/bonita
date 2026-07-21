# Spec: Frontend Race Condition and Error Handling Fixes

## Purpose

Fix race conditions, stale data overwrites, and error handling issues in frontend Vue components.

## ADDED Requirements

### Requirement: R1: Request Sequencing

All data loading in Records.vue MUST use a generation counter to prevent stale responses from overwriting current data.

#### Scenario: Fast tab switching
- GIVEN the user is on the "未刮削" tab and clicks "已刮削"
- WHEN the first request is still in flight when the second starts
- THEN only the second request's result MUST be applied to the UI
- AND the first request's result MUST be silently discarded

#### Scenario: Component unmount
- GIVEN a loadData request is in flight
- WHEN the user navigates away from Records.vue
- THEN the pending request result MUST NOT be applied
- AND the searchTimeout MUST be cleared

### Requirement: R2: localStorage Validation

Settings loaded from localStorage MUST be validated for correct structure before use.

#### Scenario: Corrupted sortBy in localStorage
- GIVEN localStorage contains `records-view-settings` with malformed `sortBy` (e.g., not an array)
- WHEN Records.vue loads settings
- THEN the default sortBy MUST be used instead
- AND no exception MUST be thrown

#### Scenario: Empty visibleColumnKeys
- GIVEN the user intentionally unchecked all optional columns
- WHEN the page reloads and loads settings
- THEN `visibleColumnKeys` MUST be restored as an empty array
- AND only always-visible columns (name, actions) MUST be shown

#### Scenario: Old successFilter migration
- GIVEN localStorage contains the old `successFilter` field
- WHEN Records.vue loads settings
- THEN `successFilter` MUST be migrated to `activeTab`
- AND the migration MUST be written back to localStorage immediately

### Requirement: R3: Request Deduplication

Clear-filter and delete operations MUST NOT cause duplicate or out-of-context requests.

#### Scenario: Clear search filter
- GIVEN the user has a search query active
- WHEN they click the clear button
- THEN the search input MUST be cleared
- AND only one loadData request MUST be sent (via watcher debounce)
- AND no direct loadData call MUST be made from the clear handler

#### Scenario: Delete records preserves context
- GIVEN the user is on the "已刮削" tab with a sort order set
- WHEN they delete selected records
- THEN the reload MUST preserve the current tab, filter, and sort state

### Requirement: R4: ScrapeLogDrawer Request Identity

ScrapeLogDrawer MUST use a generation counter to prevent stale responses when switching between records.

#### Scenario: Switch record while loading
- GIVEN the drawer is loading log for record A
- WHEN the user switches to record B
- THEN record A's response MUST NOT overwrite record B's data
- AND a new request for record B MUST be sent

#### Scenario: 404 does not permanently stop polling
- GIVEN the drawer is opened for a record that has no scrape log yet
- WHEN the first poll returns 404
- THEN polling MUST continue (the task may create the log shortly)
- AND when the log appears, it MUST be displayed automatically

#### Scenario: Non-404 error display
- GIVEN the API returns a 500 error
- WHEN loadLatestLog catches the error
- THEN an error message MUST be displayed to the user
- AND a retry option MUST be available

### Requirement: R5: Polling Guard

Polling requests MUST not overlap; if a previous poll is still in flight, the next tick MUST be skipped.

#### Scenario: Slow API response
- GIVEN the poll interval is 1s and the API takes 2s to respond
- WHEN the next poll tick fires
- THEN it MUST skip (not queue another request)
- AND polling MUST resume after the in-flight request completes

### Requirement: R6: WebSocket Identity

WebSocket event handlers in Logs.vue MUST check instance identity to prevent stale events from previous connections.

#### Scenario: Reconnection with stale events
- GIVEN the WebSocket disconnects and a new connection is created
- WHEN events from the old socket fire (onopen, onmessage, onclose)
- THEN those events MUST be discarded (instance id mismatch)
- AND only events from the current socket MUST be processed

#### Scenario: Auth failure display
- GIVEN the backend closes the WebSocket with code 1008 (auth failure)
- WHEN the onclose event fires
- THEN an explicit "认证失败" error message MUST be displayed
- AND the UI MUST not show "connected" status

#### Scenario: Fresh token on reconnect
- GIVEN the user's token may have been refreshed
- WHEN connectLogs() is called for a reconnection
- THEN the token MUST be captured fresh at call time
- AND not from a stale reference captured earlier
