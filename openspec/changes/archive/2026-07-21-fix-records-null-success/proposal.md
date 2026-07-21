## Why

Records 页面中部分记录的状态（`success` 字段）显示为空白。根因是 `celery_tasks/tasks.py` 的 `celery_transfer_group` 在开始处理时将 `record.success` 设为 `None`（第 193 行），但如果处理过程中发生异常（第 344-347 行的 `except` 块），`success` 不会被重置为 `False`，导致 `None` 被持久化到数据库。这些"中断"记录在 UI 上无法辨识，也无法被"失败"筛选器正确捕获——当前筛选逻辑 `success == False` 会漏掉 `None` 值。

## What Changes

### 修复异常处理遗漏（后端 bug fix）

- `celery_tasks/tasks.py` 的 `celery_transfer_group` 函数 `except` 块（约第 344 行）中，在记录日志后遍历当前循环中的 `record`，将其 `success` 设为 `False`，确保异常中断的记录不会停留在 `None` 状态

### 失败筛选语义修正（后端 + 前端）

- **后端** `record_service.get_records()` 的 `success` 过滤逻辑从精确匹配改为语义匹配：当 `success=False` 时，筛选条件改为 `TransRecords.success IS NOT True`（即 `False` 和 `None` 都被包含）；`success=True` 保持精确匹配 `== True`
- **前端** Records 页面状态列渲染优化：`success === null` 时显示"中断"状态图标（灰色警告图标），与成功（绿色✓）和失败（红色✗）区分

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `records-view-customization`: 状态筛选的语义从"`success == False` 精确匹配"改为"`success != True` 包含 null"，状态列渲染新增 null 状态的视觉区分

## Impact

- **后端 Celery 任务**: `backend/bonita/celery_tasks/tasks.py` — `celery_transfer_group` 异常处理补充 `record.success = False`
- **后端服务层**: `backend/bonita/services/record_service.py` — `get_records` 方法的 `success` 过滤条件修改（主查询和 count 查询同步）
- **前端页面**: `frontend/src/pages/Records.vue` — 状态列模板增加 null 分支渲染
