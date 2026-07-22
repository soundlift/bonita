## Why

`celery_transfer_entry`（`transfer:all`）在自身任务中通过 `group.apply_async()` + `transfer_result.get()` 阻塞等待子任务组完成。当 `MAX_CONCURRENCY > 1` 时，所有 worker 线程可能都在等子任务、而子任务排在队列后面拿不到 worker → 死锁。`MAX_CONCURRENCY=1`（Docker 默认）用 `.apply()` 同步执行绕过了此问题，但非 Docker 部署或调整并发配置后死锁风险真实存在。

P2-19 修复（`manage_celery_task` 装饰器加 `raise`）让 Celery autoretry 真正生效，但 `transfer:all` 的 `autoretry_for=(Exception,)` 会在子任务失败时重试整个入口任务，再次触发嵌套 `get()` 死锁循环。

## What Changes

- **消除嵌套阻塞 `get()`**：`celery_transfer_entry` 中 `group.apply_async()` + `allow_join_result` + `transfer_result.get()` 改为不阻塞 worker 的调度模式（`chord` + 回调任务，或统一走同步 `.apply()`）。
- **移除 `transfer:all` 的 `autoretry_for`**：入口任务是高级编排器，不应自动重试整个转移流程。子任务（`transfer:group`、`scraping`）保留各自的 autoretry。
- **清理 `MAX_CONCURRENCY` 分支**：统一调度模式，移除 `os.environ.get("MAX_CONCURRENCY") == "1"` 的 if/else 分支（或将其语义改为控制并行度而非同步/异步切换）。
- **确保 `manage_celery_task` 装饰器与新调度模式兼容**：`transfer:all` 在 chord 模式下立即返回，装饰器的 `complete_task` 需对应调整（或移至回调任务）。

## Capabilities

### Modified Capabilities

- `task-lifecycle`：任务编排和异常传播行为变更（移除入口任务 autoretry、消除嵌套 get）。

## Impact

- **向后兼容**：`MAX_CONCURRENCY=1` 行为不变（同步执行）。`MAX_CONCURRENCY > 1` 的用户获得正确并行执行而非死锁。
- **进度追踪**：`transfer:all` 的进度模型可能调整（chord 模式下入口任务立即完成，回调任务承载后续进度）。
- **非目标**：不修复 P1-10（WS 日志监控）、P2-16（WatchHistory user_id）。
