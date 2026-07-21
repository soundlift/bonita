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
