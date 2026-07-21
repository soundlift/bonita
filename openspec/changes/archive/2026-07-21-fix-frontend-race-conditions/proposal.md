# Proposal: Fix Frontend Race Conditions and Error Handling

## Problem

2026-07-21 前端审计发现 17 个问题，集中在三个领域：
1. **Records.vue** — 请求竞态、生命周期泄漏、localStorage 校验缺失
2. **ScrapeLogDrawer.vue** — 请求竞态、轮询重叠、错误静默
3. **Logs.vue** — WebSocket 事件过期、认证错误无 UI 反馈

## Scope

### Records.vue（7 项）

| # | 问题 | 严重性 |
|---|------|--------|
| 1 | `searchTimeout` 在 `onBeforeUnmount` 未清除，卸载后 `loadData` 仍可执行 | P1 |
| 2 | `loadData` 可重叠执行（防抖、手动排序、自动刷新），无请求顺序控制，旧响应覆盖新数据 | P1 |
| 3 | localStorage 存储的 `sortBy` 无校验，畸形数据可导致 `sortBy[0].key.startsWith` 抛异常 | P2 |
| 4 | `visibleColumnKeys` 恢复时 `length > 0` 判断导致空数组（用户有意取消所有可选列）被忽略 | P2 |
| 5 | 旧 `successFilter` 迁移后未回写 localStorage，每次加载都重新迁移 | P2 |
| 6 | `handleClearSearch` 直接调用 `loadData`，与 watcher 防抖产生重复请求 | P2 |
| 7 | `deleteRecords` 重新加载时未携带当前 tab/filter/sort 状态，导致列表重置 | P1 |

### ScrapeLogDrawer.vue（6 项）

| # | 问题 | 严重性 |
|---|------|--------|
| 8 | `loadLatestLog` 无请求身份标识，切换 record 时旧响应可覆盖新数据 | P1 |
| 9 | 轮询间隔 1s，请求未完成时下一次轮询已启动，可重叠 | P2 |
| 10 | `loadLatestLog` await 后未检查 drawer 是否仍打开/recordId 是否未变 | P1 |
| 11 | 非 404 错误仅 `console.error`，用户看不到错误提示 | P2 |
| 12 | 初始 404 永久停止轮询，任务创建日志期间打开 drawer 后不会恢复 | P2 |
| 13 | `store.latestScrapeLog` 是共享全局状态但 drawer 用自己的 ref，`fetchScrapeLogs` 未使用 | P2 |

### Logs.vue（4 项）

| # | 问题 | 严重性 |
|---|------|--------|
| 14 | `onopen` 使用 `wsConnection.value`，重连后旧 socket 事件可发送到新 socket | P1 |
| 15 | 认证失败仅通过 close code，UI 无明确错误提示 | P2 |
| 16 | 无自动重连机制（可能是设计决策） | P3 |
| 17 | token 在连接创建时捕获，重连前 token 可能已过期 | P2 |

## Out of Scope

- 后端 bug（单独 change: `fix-backend-audit-bugs`）
- P1-8 / P1-10 架构级改动
- 新功能开发

## Impact

- 消除 Records 页面数据闪烁/覆盖问题
- ScrapeLogDrawer 切换记录时不再显示错误数据
- WebSocket 日志页面重连后行为正确
