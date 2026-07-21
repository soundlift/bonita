# Records View Customization Specification

## Purpose

定义 Records 页面的后端过滤能力与前端视图定制项（可见列、排序、分页等）。

## Requirements

### Requirement: 后端 SHALL 支持按 success 字段过滤记录

`GET /api/v1/records/all` 端点 SHALL 接受 `success` 查询参数（`Optional[bool]`，默认 `None`）。当 `success` 为 `None` 时 SHALL 不应用状态过滤。当 `success` 为 `True` 时 SHALL 只返回 `transfer_record.success == True` 的记录。当 `success` 为 `False` 时 SHALL 只返回 `transfer_record.success != True` 的记录（即 `False` 与 `NULL`/中断记录）。`record_service.get_records()` 的 count 查询 SHALL 同步应用此过滤条件，确保分页总数正确。

实现 SHALL 使用 `or_(TransRecords.success == False, TransRecords.success.is_(None))` 而非 `TransRecords.success != True`，以确保在 SQLite 三值逻辑下正确包含 `NULL` 值。

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all` 且未提供 `success` 查询参数
- **THEN** 返回的记录 SHALL 包含所有状态（成功、失败、中断），行为与当前版本完全一致（向后兼容）

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all?success=true`
- **THEN** 返回的记录 SHALL 只包含 `transfer_record.success == True` 的记录，`count` 字段 SHALL 反映过滤后的总数

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all?success=false`
- **THEN** 返回的记录 SHALL 同时包含 `transfer_record.success == False` 与 `transfer_record.success IS NULL` 的记录（即所有 `success IS NOT TRUE` 的记录），`count` 字段 SHALL 反映这两类的总数

### Requirement: Celery 转移任务异常时 SHALL 将记录标记为失败

`celery_transfer_group` 任务（`celery_tasks/tasks.py`）在处理文件过程中发生未捕获异常时，SHALL 在 `except` 块中将当前 `record.success` 设为 `False`，然后由 `finally` 块的 `session.commit()` 持久化。如果 `record` 变量在异常发生时尚未定义（异常发生在 record 赋值之前），SHALL 跳过赋值而不抛出 `NameError`。

#### Scenario: 刮削过程中抛出异常

- **WHEN** `celery_transfer_group` 处理某文件时，在 `record.success = None`（第 193 行）之后、`record.success = True`（第 343 行）之前抛出异常
- **THEN** `except` 块 SHALL 将 `record.success` 设为 `False`，`finally` 块 SHALL commit 该值到数据库，记录不会停留在 `None` 状态

#### Scenario: 异常发生在 record 赋值之前

- **WHEN** 异常发生在 `record` 变量赋值之前（如 `session = SessionFactory()` 失败）
- **THEN** `except` 块 SHALL 检测到 `record` 未定义并跳过赋值，不 SHALL 抛出 `NameError`

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
