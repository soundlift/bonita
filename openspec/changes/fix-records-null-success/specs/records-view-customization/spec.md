## ADDED Requirements

### Requirement: Celery 转移任务异常时 SHALL 将记录标记为失败

`celery_transfer_group` 任务（`celery_tasks/tasks.py`）在处理文件过程中发生未捕获异常时，SHALL 在 `except` 块中将当前 `record.success` 设为 `False`，然后由 `finally` 块的 `session.commit()` 持久化。如果 `record` 变量在异常发生时尚未定义（异常发生在 record 赋值之前），SHALL 跳过赋值而不抛出 `NameError`。

#### Scenario: 刮削过程中抛出异常

- **WHEN** `celery_transfer_group` 处理某文件时，在 `record.success = None`（第 193 行）之后、`record.success = True`（第 343 行）之前抛出异常
- **THEN** `except` 块 SHALL 将 `record.success` 设为 `False`，`finally` 块 SHALL commit 该值到数据库，记录不会停留在 `None` 状态

#### Scenario: 异常发生在 record 赋值之前

- **WHEN** 异常发生在 `record` 变量赋值之前（如 `session = SessionFactory()` 失败）
- **THEN** `except` 块 SHALL 检测到 `record` 未定义并跳过赋值，不 SHALL 抛出 `NameError`

### Requirement: 后端失败筛选 SHALL 包含 success 为 NULL 的记录

`record_service.get_records()` 方法中，当 `success` 参数为 `False` 时，过滤条件 SHALL 匹配所有 `success IS NOT True` 的记录（即 `False` 和 `NULL` 都被包含）。主查询和 count 查询 SHALL 同步应用此过滤条件。当 `success` 参数为 `True` 时，过滤条件 SHALL 保持精确匹配 `success == True`。当 `success` 为 `None` 时，不应用过滤。

实现 SHALL 使用 `or_(TransRecords.success == False, TransRecords.success.is_(None))` 而非 `TransRecords.success != True`，以确保在 SQLite 三值逻辑下正确包含 `NULL` 值。

#### Scenario: 筛选失败时返回 success=False 和 success=NULL 的记录

- **WHEN** 客户端调用 `GET /api/v1/records/all?success=false`
- **THEN** 返回的记录 SHALL 包含 `success == False` 和 `success IS NULL` 的所有记录，`count` 字段 SHALL 反映两者的总数

#### Scenario: 筛选成功时仅返回 success=True

- **WHEN** 客户端调用 `GET /api/v1/records/all?success=true`
- **THEN** 返回的记录 SHALL 只包含 `success == True` 的记录，行为与当前版本一致

#### Scenario: 不传 success 参数时返回所有记录

- **WHEN** 客户端调用 `GET /api/v1/records/all` 且未提供 `success` 查询参数
- **THEN** 返回的记录 SHALL 包含所有状态（True、False、NULL），行为与当前版本一致（向后兼容）

### Requirement: 前端状态列 SHALL 区分三种 success 状态

Records 页面表格的状态列 SHALL 根据 `transfer_record.success` 的值显示三种不同的视觉状态：
- `true`：绿色 chip + `bx-check` 图标（成功）
- `false`：红色 chip + `bx-x` 图标（失败）
- `null`：灰色 chip + `mdi-alert` 图标（中断）

#### Scenario: success 为 null 时显示中断图标

- **WHEN** 表格渲染一条 `transfer_record.success === null` 的记录
- **THEN** 状态列 SHALL 显示灰色的 chip，内含 `mdi-alert` 警告图标，与成功的绿色和失败的红色区分

#### Scenario: success 为 false 时显示失败图标

- **WHEN** 表格渲染一条 `transfer_record.success === false` 的记录
- **THEN** 状态列 SHALL 显示红色 chip + `bx-x` 图标，与当前行为一致
