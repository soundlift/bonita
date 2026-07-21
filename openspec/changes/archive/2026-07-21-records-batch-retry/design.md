## Context

Records 页面已有批量删除功能（`DELETE /api/v1/records/records?record_ids=[...]`，前端工具栏"删除选中"按钮），这是批量操作的既有模式。单条重试功能也已存在（操作列的重试按钮 → `taskStore.runTaskByIdWithPath(task_id, srcpath)` → `POST /api/v1/tasks/run/{id}` with `TaskPathParam { path }` → `celery_transfer_group.delay(task_dict, path, True)`）。

后端单条重试的完整链路是：路由 `run_transfer_task`（`tasks.py:17`）查 `TransferConfig` by id → 转为 dict → `celery_transfer_group.delay(task_dict, path, True)`。批量重试需要为每条记录重复这个链路。

## Goals / Non-Goals

**Goals:**

- 用户可勾选多条记录，一键提交批量重试
- 批量重试对每条记录独立处理——某条失败不影响其他记录的重试
- 返回汇总结果，用户知道哪些成功、哪些失败及原因

**Non-Goals:**

- 不做重试频率限制（concurrency control）——Celery worker 自身有 `semaphore` 控制并发
- 不做重试历史的持久化记录——重试提交后通过现有的任务状态页（Dashboard）跟踪
- 不修改单条重试的现有逻辑和 API

## Decisions

### 决策 1：后端新增 `POST /api/v1/records/retry`，而非复用 `/tasks/run/{id}`

**选择**: 在 `records.py` 路由新增 `POST /retry` 端点，接收 `record_ids: List[int]`，在 `RecordService` 中实现批量逻辑。

**理由**: 现有 `/tasks/run/{id}` 是"按任务 ID 执行"，需要知道 `task_id`。批量重试的输入是 `record_ids`，需要先查记录拿到各自的 `task_id` 和 `srcpath`，再逐条调用 Celery。如果前端循环调用 `/tasks/run/{id}`，N 条记录 = N 次 HTTP 请求，慢且难以汇总反馈。后端批量 API 一次请求处理所有记录，可以返回汇总结果。

**备选方案**: 前端循环调用现有 `/tasks/run/{id}`——实现简单但用户体验差（请求多、无汇总、部分失败难以反馈），放弃。

### 决策 2：`RecordService.retry_records` 逐条提交 Celery 任务

**选择**: 方法内遍历 `record_ids`，对每条记录：
1. 查 `TransRecords` by id，获取 `task_id` 和 `srcpath`
2. 查 `TransferConfig` by `task_id`
3. 如果 `TransferConfig` 不存在或 `srcpath` 为空，记录为失败
4. 否则调用 `celery_transfer_group.delay(task_conf.to_dict(), srcpath, True)` 提交异步任务
5. 汇总成功和失败结果

**理由**: 每条记录可能属于不同的 task（不同刮削配置），必须逐条查询和提交。Celery `delay()` 是非阻塞的，提交后立即返回 `task_id`，不会卡住请求。

**备选方案**: 使用 Celery group/chord 批量提交——但各记录的 `task_dict` 不同（可能属于不同 task config），不适合用同一个 group。逐条 `delay()` 更灵活。

### 决策 3：返回格式包含成功数和失败详情

**选择**: 返回 `schemas.Response`（`success: bool, message: str`），`message` 中包含汇总信息（如"成功重试 3 条，失败 1 条：record #45 task_id 不存在"）。如果需要更结构化的返回，可新增 `BatchRetryResponse` schema。

**理由**: 与现有的 `delete_records` 返回模式一致（也是 `Response` + message 中含汇总）。前端用 toast 显示 message 即可。

### 决策 4：前端"重试选中"按钮带确认对话框

**选择**: 点击"重试选中"后弹出确认对话框（"确认重试选中的 N 条记录？"），确认后调用 API。

**理由**: 重试会触发文件转移操作（可能覆盖已有文件），与删除一样是不可逆操作，应二次确认。复用现有的 `VDialog` 确认模式。

## Risks / Trade-offs

- **[批量重试的并发压力]** 如果用户一次选中 100 条记录，会瞬间提交 100 个 Celery 任务。但 `celery_transfer_group` 内部有 `semaphore` 控制实际并发数（由 `MAX_CONCURRENCY` 环境变量决定），不会压垮 worker。
- **[srcpath 已删除的记录]** 如果记录的源文件已被删除（`srcdeleted=True` 或文件不存在），重试会失败。后端应在提交前检查 `srcpath` 是否存在，不存在则记录为失败并跳过。
- **[task_id 为 0 的记录]** 有些旧记录可能 `task_id=0`（默认值），查不到对应的 `TransferConfig`。后端应将这类记录记为失败并说明原因。
