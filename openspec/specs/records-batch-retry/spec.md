# Spec: Records Batch Retry

## Purpose

Allow users to batch-retry failed transfer records from the Records page, with a backend API that processes each record independently and a frontend UI with confirmation dialog.

## ADDED Requirements

### Requirement: 后端 SHALL 提供批量重试 API

`POST /api/v1/records/retry` 端点 SHALL 接收 `record_ids: List[int]` 请求体（JSON body），对每条记录执行重试逻辑：查询记录的 `task_id` 和 `srcpath`，查询对应的 `TransferConfig`，提交 `celery_transfer_group` 异步任务。端点 SHALL 返回 `schemas.Response`（`success: bool, message: str`），`message` 中包含成功提交数和失败详情。

对于每条记录，以下情况 SHALL 记录为失败并跳过，不影响其他记录的处理：
- 记录不存在（ID 无效）
- `task_id` 为 0 或对应的 `TransferConfig` 不存在
- `srcpath` 为空或文件不存在

#### Scenario: 批量重试成功

- **WHEN** 客户端调用 `POST /api/v1/records/retry`，body 为 `{ "record_ids": [1, 2, 3] }`，且三条记录的 task_id 和 srcpath 都有效
- **THEN** 后端 SHALL 为每条记录提交 `celery_transfer_group` 异步任务，返回 `{ "success": true, "message": "成功重试 3 条" }`

#### Scenario: 部分记录重试失败

- **WHEN** 客户端调用 `POST /api/v1/records/retry`，body 为 `{ "record_ids": [1, 2, 3] }`，其中 record #2 的 task_id 不存在
- **THEN** 后端 SHALL 成功重试 record #1 和 #3，跳过 record #2 并记录原因，返回 `{ "success": true, "message": "成功重试 2 条，失败 1 条：record #2 task_id 不存在" }`

#### Scenario: 空列表请求

- **WHEN** 客户端调用 `POST /api/v1/records/retry`，body 为 `{ "record_ids": [] }`
- **THEN** 后端 SHALL 返回 `{ "success": false, "message": "未提供记录ID" }`

#### Scenario: srcpath 文件已删除

- **WHEN** 记录的 `srcpath` 指向的文件在文件系统中不存在
- **THEN** 后端 SHALL 跳过该记录的重试，记为失败并说明"源文件不存在"，不影响其他记录

### Requirement: 前端 SHALL 提供批量重试按钮和确认对话框

Records 页面工具栏 SHALL 在"删除选中"按钮旁新增"重试选中"按钮（图标 `mdi-refresh`，`color="warning"`）。按钮在 `selected.length === 0` 时禁用。按钮文字 SHALL 显示选中数量（如"重试选中 (3)"）。

点击"重试选中"SHALL 弹出确认对话框（`VDialog`），内容为"确认重试选中的 N 条记录？"。确认后 SHALL 调用 `recordStore.retryRecords(selected)`，完成后显示 toast 提示结果，并清空选中项、刷新当前页数据。

#### Scenario: 选中记录后点击重试

- **WHEN** 用户勾选 3 条记录后点击"重试选中"按钮
- **THEN** 弹出确认对话框显示"确认重试选中的 3 条记录？"

#### Scenario: 确认重试

- **WHEN** 用户在确认对话框中点击"确认"
- **THEN** 前端 SHALL 调用 `POST /api/v1/records/retry`，完成后显示 toast（成功/失败汇总），清空选中项，刷新当前页数据

#### Scenario: 取消重试

- **WHEN** 用户在确认对话框中点击"取消"
- **THEN** 对话框关闭，不发起请求，选中项保持不变

#### Scenario: 未选中记录时按钮禁用

- **WHEN** `selected.length === 0`
- **THEN** "重试选中"按钮 SHALL 处于禁用状态，无法点击
