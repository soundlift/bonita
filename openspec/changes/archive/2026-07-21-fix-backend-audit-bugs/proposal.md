# Proposal: Fix Backend Audit Bugs

## Problem

2026-07-21 代码审计发现 4 个后端 bug，其中 1 个为运行时崩溃风险（TypeError），1 个为功能失效（日志丢失），1 个为协议违规（双重 accept），1 个为路径脆弱性。

## Scope

### Bug 1: `destpath` 为 None 时 TypeError 崩溃（P1）

**位置**: `backend/bonita/celery_tasks/tasks.py:360-363, 390-393`

新记录首次转移时 `record.destpath` 为 `None`，`os.path.exists(None)` 抛出 `TypeError`。该异常被 `manage_celery_task` 装饰器捕获并标记任务失败，导致整个转移流程中断。

**修复**: 在 `os.path.exists(record.destpath)` 前增加 `record.destpath` 非空判断。

### Bug 2: WebSocket 日志正则不匹配 Celery task logger 输出格式（P1）

**位置**: `backend/bonita/api/websockets/logs.py:93`

正则 `r"\[(.*?)\] (\w+) in ([\w\.]+): (.*)"` 中 `[\w\.]` 不匹配 Celery task logger 的 module 名（如 `celery.app.trace` 含有点号，但实际 `[\w\.]` 已包含点号）。更关键的是，`LOGGING_FORMAT` 中包含 `PID:%(process)d TID:%(thread)d [%(task_id)s]` 段，正则的 `(.*)` 会把 PID/TID/task_id 混入 message，而 timestamp 和 level 的提取可能因格式不符而失败。

**修复**: 重写正则以匹配实际 `LOGGING_FORMAT`，或改用结构化解析（按 `] ` 分割 level、按 ` in ` 分割 module）。

### Bug 3: WebSocket 双重 `accept()` 调用（P1）

**位置**: `backend/bonita/api/websockets/logs.py:181 + :46`

`websocket_logs` 在 line 181 调用 `await websocket.accept()`，认证成功后调用 `log_manager.connect(websocket)`，而 `connect()` 在 line 46 又调用 `await websocket.accept()`。第二次 accept 在已 accepted 的 WebSocket 上是未定义行为，可能静默失败或抛异常。

**修复**: 从 `LogConnectionManager.connect()` 移除 `await websocket.accept()`，因为 endpoint 已经 accept 过了。

### Bug 4: `LOGGING_LOCATION` 相对路径在 Celery worker 中解析错误（P2）

**位置**: `backend/bonita/core/config.py:68`

`LOGGING_LOCATION` 默认值为 `"./data/bonita.log"`（相对路径）。uvicorn 和 Celery worker 可能有不同的工作目录，导致日志写入不同文件。WebSocket 监控读取的文件可能不是 Celery 写入的文件。

**修复**: 在 `init_log_config()` 中将 `LOGGING_LOCATION` 解析为基于 `BASE_DIR` 的绝对路径，或在 Settings 初始化时 normalize。

## Out of Scope

- P1-8（Celery 嵌套 get 死锁）：架构级改动，需单独 change
- P1-10（WS 日志全量读取 + 轮询）：体验改进，需单独 change
- 前端 race conditions：单独 change

## Impact

- 修复后转移任务不再因新记录 destpath=None 而崩溃
- WebSocket 日志页面能正确显示 Celery 任务日志
- WebSocket 连接协议正确，不再有双重 accept
- 日志路径在所有进程中一致
