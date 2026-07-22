## Context

`celery_transfer_entry`（`transfer:all`）通过 `group.apply_async()` + `transfer_result.get()` 阻塞 worker 等待子任务组。子任务可能排在同一 worker 队列后面 → 死锁。Docker 默认 `MAX_CONCURRENCY=1` 走 `.apply()` 同步路径绕过了此问题，但非 Docker 部署或调高并发后死锁真实存在。

P2-19 修复让 `manage_celery_task` 装饰器 `raise` 异常,使 Celery autoretry 生效。但 `transfer:all` 的 `autoretry_for=(Exception,)` 在子任务失败时重试整个入口任务,再次触发嵌套 `get()` — 形成"死锁→重试→再死锁"循环。

## Goals / Non-Goals

**Goals:**
- 消除 `transfer:all` 中的阻塞 `get()`,根除死锁风险。
- 移除入口任务的 `autoretry_for`,避免重试爆炸半径。
- 保持 `MAX_CONCURRENCY=1` 行为不变(Docker 默认不受影响)。

**Non-Goals:**
- 不重写 `celery_transfer_group` 内部的 `.apply()` + `.get()` 调用(该层已是同步执行,无死锁风险)。
- 不引入 `chord`/`chain` 等高级 Celery 编排(复杂度过高,留给未来增强)。
- 不修改 P1-10、P2-16。

## Decisions

### D1 · `transfer:all` 统一走同步 `group.apply()`

移除 `MAX_CONCURRENCY` 条件分支,始终使用 `transfer_group.apply()` 同步执行子任务组。

```python
# Before (deadlock-prone when MAX_CONCURRENCY != "1"):
if os.environ.get("MAX_CONCURRENCY") == "1":
    transfer_result = transfer_group.apply()
else:
    transfer_result = transfer_group.apply_async()
with allow_join_result():
    done_list = transfer_result.get()

# After (always synchronous):
transfer_result = transfer_group.apply()
done_list = transfer_result.get()
```

**理由**：
- `MAX_CONCURRENCY=1`（Docker 默认）已证明此路径可靠。
- `transfer:group` 内部的 `celery_scrapping` 已是 `.apply()` 同步调用,外层并行收益有限。
- `semaphore` 信号量控制单进程内并发数,同步执行下无意义但无害。
- 典型场景(1-5 个源目录)顺序处理耗时与并行无显著差异(I/O 瓶颈在磁盘)。

**备选方案(未采用)**：`chord(group)(callback)` — 保持并行但需新增回调任务、改造进度追踪、处理装饰器兼容性。复杂度过高,收益有限。

### D2 · 移除 `transfer:all` 的 `autoretry_for`

入口任务是编排器,不应自动重试整个流程。子任务（`transfer:group`、`scraping`）保留各自的 `autoretry_for`。

```python
# Before:
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}, ...)

# After:
@shared_task(bind=True, ...)
```

**理由**：
- `transfer:all` 失败时,子任务的重试机制已在粒度级别处理异常。
- 入口级重试会重新 scandir + 重建 group,已成功的子任务靠 `skip_on_success` 跳过,但 `force_refresh` 路径无幂等保护(P1-8 point 2)。
- 用户可通过 API 手动触发重试(已有 `retry` 端点)。

### D3 · 移除 `MAX_CONCURRENCY` 同步/异步分支

`os.environ.get("MAX_CONCURRENCY") == "1"` 的 if/else 分支不再需要。`MAX_CONCURRENCY` 保留用于 Celery worker `--concurrency` 参数(控制 worker 线程数),与任务调度模式解耦。

清理位置：
- `celery_transfer_entry`：3 处 if/else（lines 68-71, 95-98, 101-104）
- 保留 `MAX_CONCURRENCY` 在 `docker/s6-rc.d/bonita/run` 中的 `--concurrency` 用法

## Risks / Trade-offs

- **并行度降低**：多源目录场景下顺序处理比并行慢。影响范围：非 Docker 部署 + 多目录 + `MAX_CONCURRENCY > 1` 的用户。缓解：典型场景目录数少,I/O 瓶颈下差异不大。
- **`allow_join_result` 移除**：同步 `group.apply()` 的 `.get()` 不需要 `allow_join_result`,但保留也无害。移除保持代码整洁。
- **进度追踪不变**：同步模式下进度更新与当前 `MAX_CONCURRENCY=1` 路径一致,无需改造。
