# Spec: Task Lifecycle and Path Validation

## Purpose

Ensure Celery task exceptions are properly logged with full details, exceptions propagate to enable autoretry, and file browser path access is restricted to prevent traversal.

## MODIFIED · `task-lifecycle`

### Purpose

确保 Celery 任务的异常信息完整记录到日志，且 `autoretry_for` 机制正常生效。

### Requirements
#### R1 · 异常信息完整性

`celery_tasks/tasks.py` 中所有 `logger.error` 调用必须使用 f-string 或 `%s` 格式化，确保异常对象 `e` 的实际信息被写入日志。

**必须修复的行**：
- `celery_emby_scan`：`logger.error(f"## [Emby扫描] ✗ 失败: {e}")`
- `celery_import_nfo`：`logger.error(f"## [NFO导入] ✗ 失败: {e}")`

#### R2 · 异常传播

`celery_tasks/decorators.py` 的 `manage_celery_task` 装饰器 `except` 块在标记 `fail_task` 后必须 `raise`，让异常传播到 Celery runtime。

**行为要求**：
- `fail_task` 标记仍然执行（记录失败状态和错误信息）。
- `raise` 后 Celery 根据 `autoretry_for=(Exception,)` 决定是否重试。
- 重试时 `create_task` 对同 `task_id` 必须幂等（更新状态而非重复创建）。
- `transfer:all` 虽然 `raise`，但因未声明 `autoretry_for`，Celery 不会自动重试。
- 其他任务（`transfer:group`、`scraping` 等）的 `raise` 触发各自声明的 `autoretry_for`。

#### R3 · 入口任务不得阻塞等待子任务

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

#### R4 · 入口任务不自动重试

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

### Verification

- [ ] 修改后语法检查通过。
- [ ] 在 `celery_emby_scan` 和 `celery_import_nfo` 中注入异常，确认日志中包含完整异常信息（非字面量 `{str(e)}`）。
- [ ] 触发一个声明了 `autoretry_for` 的任务失败，确认 Celery 重试最多 3 次。

---

## MODIFIED · `file-path-validation`

### Purpose

限制 `file_browser` 端点可浏览的目录范围，防止任意路径遍历。

### Requirements
#### R1 · 路径白名单配置

`config.py` 新增 `ALLOWED_FILE_ROOTS: list[str] = []` 配置项，支持环境变量和 YAML 覆盖。

#### R2 · 路径校验逻辑

`file_browser.py` 的 `list_directory` 端点在执行 `os.scandir` 之前，必须校验 `os.path.realpath(directory_path)` 位于 `ALLOWED_FILE_ROOTS` 之一的子树下。

**行为要求**：
- `ALLOWED_FILE_ROOTS` 为空列表时：不限制（向后兼容）。
- 路径不在允许范围内时：返回空结果（与路径不存在的行为一致），不抛异常。
- `os.path.realpath` 必须在 `os.path.exists` 检查之前执行，解析符号链接和 `..`。

### Verification

- [ ] 配置 `ALLOWED_FILE_ROOTS=["C:/Users/test"]`，请求 `?directory_path=C:/Windows` 返回空结果。
- [ ] 请求 `?directory_path=C:/Users/test/../../Windows` 返回空结果（路径遍历防御）。
- [ ] 未配置时（默认 `[]`），任意路径正常返回结果。
