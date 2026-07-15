## Why

Records 页面目前只能逐条重试失败记录（每条点击操作列的重试按钮）。当一批记录因刮削配置错误、网络中断或 worker 崩溃而集体失败时，用户需要逐条点击重试，体验很差。需要支持勾选多条记录后一键批量重试，类似已有的"删除选中"批量操作模式。

## What Changes

### 后端批量重试 API

- 新增 `POST /api/v1/records/retry` 端点，接收 `record_ids: List[int]` 请求体
- `RecordService` 新增 `retry_records(record_ids)` 方法：逐条查询记录，取 `task_id` + `srcpath`，查对应的 `TransferConfig`，提交 `celery_transfer_group.delay()` 异步任务
- 返回汇总结果：成功提交数、失败列表及原因（如 task_id 不存在、srcpath 已删除等）

### 前端批量重试 UI

- Records 页面工具栏新增"重试选中"按钮（图标 `mdi-refresh`），紧邻现有"删除选中"按钮
- 按钮在 `selected.length === 0` 时禁用，选中记录后显示选中数量
- 点击后弹出确认对话框（可选，与删除确认一致的模式），确认后调用批量重试 API
- 结果通过 toast 提示（成功 N 条，失败 M 条）

## Capabilities

### New Capabilities

- `records-batch-retry`: Records 页面批量重试能力——勾选多条记录后一键重新提交转移任务

### Modified Capabilities

（无）

## Impact

- **后端路由**: `backend/bonita/api/routes/records.py` — 新增 `POST /retry` 端点
- **后端服务层**: `backend/bonita/services/record_service.py` — 新增 `retry_records` 方法
- **后端 schemas**: `backend/bonita/schemas/record.py` — 新增批量重试请求/响应 schema（或在路由内联）
- **前端页面**: `frontend/src/pages/Records.vue` — 新增重试按钮、确认对话框、toast 结果
- **前端 store**: `frontend/src/stores/record.store.ts` — 新增 `retryRecords` action
- **前端 client**: 需重新生成 `services.gen.ts` 以包含新的 retry 端点
- **前端 i18n**: `frontend/src/plugins/i18n/locales/zh.ts` 和 `en.ts` — 新增重试相关文案
