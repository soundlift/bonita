# Design: Fix Frontend Race Conditions and Error Handling

## Records.vue

### Fix 1 & 2: Request Sequencing

**Problem**: Multiple `loadData` calls can overlap. No cancellation or sequencing.

**Solution**: Use a request generation counter (monotonic id). Each `loadData` call increments the counter. When the async response arrives, check if the counter still matches — if not, discard the stale response.

```typescript
const requestGeneration = ref(0)

async loadData() {
  const gen = ++requestGeneration.value
  // ... build params ...
  const result = await recordStore.getRecords(params)
  if (gen !== requestGeneration.value) return // stale, discard
  // ... apply result ...
}
```

This is simpler than AbortController (which requires backend support) and handles all race cases.

**Cleanup**: In `onBeforeUnmount`, clear `searchTimeout` and increment `requestGeneration` to invalidate in-flight requests.

### Fix 3: localStorage sortBy Validation

```typescript
function loadSettings() {
  // ...
  const saved = JSON.parse(raw)
  // Validate sortBy structure
  if (saved.sortBy && Array.isArray(saved.sortBy) && saved.sortBy.length > 0
      && typeof saved.sortBy[0]?.key === 'string') {
    sortBy.value = saved.sortBy
  }
  // ...
}
```

### Fix 4: Empty visibleColumnKeys

```typescript
// Change from:
if (saved.visibleColumnKeys && saved.visibleColumnKeys.length > 0) {
// To:
if (saved.visibleColumnKeys && Array.isArray(saved.visibleColumnKeys)) {
```

An empty array is a valid user choice (only always-visible columns remain).

### Fix 5: Migration Writeback

After migrating `successFilter` → `activeTab`, call `saveSettings()` once to persist the migration.

### Fix 6: Remove Direct loadData in Clear Handlers

`handleClearSearch` should only reset the ref value. The watcher with debounce will trigger `loadData` automatically. Remove the explicit `loadData()` call.

### Fix 7: deleteRecords Preserves Context

```typescript
async function handleDeleteSelected() {
  await recordStore.deleteRecords(selectedIds.value)
  // loadData will use current activeTab/searchQuery/sortBy automatically
  loadData()
}
```

Verify that `loadData` already reads from the reactive refs (activeTab, searchQuery, etc.) — if so, no change needed beyond confirming the current implementation is correct.

---

## ScrapeLogDrawer.vue

### Fix 8 & 10: Request Identity

Use a generation counter per drawer open/record change:

```typescript
const fetchGeneration = ref(0)

async function loadLatestLog() {
  const gen = ++fetchGeneration.value
  const result = await recordStore.fetchLatestScrapeLog(props.recordId)
  if (gen !== fetchGeneration.value) return // stale
  if (!props.modelValue) return // drawer closed
  // ... apply result ...
}
```

Reset generation when `recordId` or `modelValue` changes.

### Fix 9: Polling Guard

```typescript
let pollingInFlight = false

async function poll() {
  if (pollingInFlight) return
  pollingInFlight = true
  try {
    await loadLatestLog()
  } finally {
    pollingInFlight = false
  }
}
```

### Fix 11: User-Visible Error State

```typescript
const error = ref<string | null>(null)

// In loadLatestLog catch:
if (err?.status === 404) {
  // no log yet, show placeholder
} else {
  error.value = '加载日志失败'
}
```

Display error in template with a retry button.

### Fix 12: Retry on 404

Instead of permanently stopping polling on 404, use a backoff strategy:
- First 404: retry in 2s
- Second 404: retry in 5s
- Third+: stop polling, show "暂无日志，将在任务开始后自动刷新" with manual retry button

Or simpler: don't stop polling on 404, just skip the update. The polling already stops when the drawer closes.

---

## Logs.vue

### Fix 14: WebSocket Identity Guard

```typescript
let wsInstanceId = 0

function connectLogs() {
  const myId = ++wsInstanceId
  const ws = new WebSocket(wsUrl)
  wsConnection.value = ws

  ws.onopen = () => {
    if (myId !== wsInstanceId) return // stale socket
    // ... auth ...
  }
  ws.onmessage = (event) => {
    if (myId !== wsInstanceId) return
    // ... handle message ...
  }
  // ... same for onclose, onerror ...
}
```

### Fix 15: Auth Error UI

```typescript
const authError = ref<string | null>(null)

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'auth' && data.status === 'ok') {
    authError.value = null
    // ...
  }
}

ws.onclose = (event) => {
  if (event.code === 1008) {
    authError.value = '认证失败，请重新登录'
  }
}
```

### Fix 17: Token Freshness

Capture token inside `connectLogs()` at call time, not at module level. If the user reconnects, the latest token is used.
