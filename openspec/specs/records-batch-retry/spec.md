# Spec: Records Batch Retry

## Purpose

Allow users to batch-retry failed transfer records from the Records page, with a backend API that processes each record independently and a frontend UI with confirmation dialog. Retry triggers a full refresh (force_refresh=True): re-parse number, delete old destpath, force network scraping.
## Requirements
### Requirement: 后端 SHALL 提供批量重试 API

`POST /api/v1/records/retry` 端点 SHALL 接收 `record_ids: List[int]`(query 参数),对每条记录执行重试逻辑:查询记录的 `task_id` 和 `srcpath`,查询对应的 `TransferConfig`,以 `force_refresh=True` 提交 `celery_transfer_group` 异步任务,实现「完全重新开始」语义(重新解析编号、删除旧目标文件、强制网络刮削)。端点 SHALL 返回 `schemas.Response`(`success: bool, message: str`),`message` 中包含成功提交数和失败详情。

重试流程 SHALL 保留 `TransRecords.createtime` 的原始值,不得刷新。重试流程 SHALL 保留 `ExtraInfo.specifiedsource`/`specifiedurl` 及用户已设置的 `crop`。

对于每条记录,以下情况 SHALL 记录为失败并跳过,不影响其他记录的处理:
- 记录不存在(ID 无效)
- `task_id` 为 0 或对应的 `TransferConfig` 不存在
- `srcpath` 为空或文件不存在

#### Scenario: 批量重试成功且触发完全重新开始

- **WHEN** 客户端调用 `POST /api/v1/records/retry?record_ids=1&record_ids=2&record_ids=3`,且三条记录的 task_id 和 srcpath 都有效
- **THEN** 后端 SHALL 为每条记录以 `force_refresh=True` 提交 `celery_transfer_group` 异步任务(触发重新解析编号、删除旧文件、强制网络刮削),返回 `{ "success": true, "message": "成功重试 3 条" }`

#### Scenario: 部分记录重试失败

- **WHEN** 客户端调用 `POST /api/v1/records/retry?record_ids=1&record_ids=2&record_ids=3`,其中 record #2 的 task_id 不存在
- **THEN** 后端 SHALL 成功重试 record #1 和 #3,跳过 record #2 并记录原因,返回 `{ "success": true, "message": "成功重试 2 条，失败 1 条：record #2 task_id 不存在" }`

#### Scenario: 空列表请求

- **WHEN** 客户端调用 `POST /api/v1/records/retry` 且 `record_ids` 为空列表
- **THEN** 后端 SHALL 返回 `{ "success": false, "message": "未提供记录ID" }`

#### Scenario: srcpath 文件已删除

- **WHEN** 记录的 `srcpath` 指向的文件在文件系统中不存在
- **THEN** 后端 SHALL 跳过该记录的重试,记为失败并说明"源文件不存在",不影响其他记录

#### Scenario: 重试后 createtime 保持不变

- **WHEN** 一条 createtime 为 "2026-07-01 10:00:00" 的记录通过批量重试被重新处理,重试完成
- **THEN** 该记录的 `createtime` SHALL 仍为 "2026-07-01 10:00:00",仅 `updatetime` 被刷新

### Requirement: 前端 SHALL 提供批量重试按钮和确认对话框

Records 页面工具栏 SHALL 在"删除选中"按钮旁提供"重试选中"按钮(图标 `mdi-refresh`,`color="warning"`)。按钮在 `selected.length === 0` 时禁用。按钮文字 SHALL 显示选中数量(如"重试选中 (3)")。

点击"重试选中"SHALL 弹出确认对话框(`VDialog`),对话框文案 SHALL 明确告知用户重试将"重新解析编号、重新刮削元数据、删除旧的目标文件",避免用户误以为是轻量重试。确认后 SHALL 调用 `recordStore.retryRecords(selected)`,完成后显示 toast 提示结果,并清空选中项、刷新当前页数据。

#### Scenario: 选中记录后点击重试

- **WHEN** 用户勾选 3 条记录后点击"重试选中"按钮
- **THEN** 弹出确认对话框,文案明确说明将重新解析编号、重新刮削、删除旧文件

#### Scenario: 确认重试

- **WHEN** 用户在确认对话框中点击"确认"
- **THEN** 前端 SHALL 调用 `POST /api/v1/records/retry`,完成后显示 toast(成功/失败汇总),清空选中项,刷新当前页数据

#### Scenario: 取消重试

- **WHEN** 用户在确认对话框中点击"取消"
- **THEN** 对话框关闭,不发起请求,选中项保持不变

#### Scenario: 未选中记录时按钮禁用

- **WHEN** `selected.length === 0`
- **THEN** "重试选中"按钮 SHALL 处于禁用状态,无法点击

