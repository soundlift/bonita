# Delta Spec: task-lifecycle

> 基线: `openspec/specs/task-lifecycle-and-path-validation/spec.md`

## ADDED Requirements

### R3 · 入口任务不得阻塞等待子任务

`celery_transfer_entry`（`transfer:all`）在调度子任务组时，SHALL 使用同步 `group.apply()` 执行，不得使用 `group.apply_async()` + `.get()` 阻塞等待模式。

**行为要求**：
- 子任务组在当前进程内同步执行，`group.apply()` 返回时所有子任务已完成。
- `allow_join_result()` 上下文管理器 SHALL 移除（同步执行不需要）。
- `MAX_CONCURRENCY` 环境变量不再控制同步/异步切换，仅用于 Celery worker `--concurrency` 参数。

#### Scenario: 多目录转移不死锁
- **GIVEN** 源文件夹包含 10 个子目录，每个子目录有视频文件
- **WHEN** 触发 `transfer:all` 任务
- **THEN** 子任务组同步顺序执行，不阻塞 worker 线程
- **AND** 所有子目录处理完成后，清理/扫描任务正常触发

#### Scenario: Docker 默认配置行为不变
- **GIVEN** Docker 部署，`MAX_CONCURRENCY=1`
- **WHEN** 触发 `transfer:all` 任务
- **THEN** 行为与修复前完全一致（同步执行，无死锁）

### R4 · 入口任务不自动重试

`celery_transfer_entry`（`transfer:all`）SHALL NOT 声明 `autoretry_for` 参数。入口任务失败时 SHALL 标记为失败，由用户通过 API 手动触发重试。

**行为要求**：
- `manage_celery_task` 装饰器的 `raise` 仍然生效（异常传播到 Celery runtime），但 Celery 不会自动重试。
- 子任务（`transfer:group`、`scraping`）保留各自的 `autoretry_for=(Exception,)` 和 `max_retries=3`。
- 用户可通过 `/api/v1/records/retry` 端点手动重试失败的转移任务。

#### Scenario: 子任务失败不触发入口重试
- **GIVEN** `transfer:group` 中某个文件的刮削失败，抛出异常
- **WHEN** 异常传播到 `transfer:all`
- **THEN** `transfer:all` 标记为失败（`manage_celery_task` 的 `fail_task` 生效）
- **AND** Celery 不自动重试 `transfer:all`
- **AND** 已成功的子任务结果保留，不受影响

#### Scenario: 手动重试已失败的入口任务
- **GIVEN** `transfer:all` 已失败
- **WHEN** 用户通过 API 触发重试
- **THEN** 重新执行 `transfer:all`，`skip_on_success=True` 的子任务跳过已成功记录

## MODIFIED Requirements

### R2 · 异常传播（更新）

`manage_celery_task` 装饰器的 `except` 块在标记 `fail_task` 后 MUST `raise`。此行为适用于所有使用该装饰器的任务。

**新增约束**：
- `transfer:all` 虽然 `raise`，但因未声明 `autoretry_for`，Celery 不会自动重试。
- 其他任务（`transfer:group`、`scraping` 等）的 `raise` 触发各自声明的 `autoretry_for`。
