## 1. 后端：Schema 定义

- [x] 1.1 ~~`BatchRetryRequest` schema~~ — 实际实现使用 query param `record_ids: List[int]`（与现有 `DELETE /records` 模式一致），无需额外 schema

## 2. 后端：Service 层

- [x] 2.1 在 `backend/bonita/services/record_service.py` 中新增 `retry_records(self, record_ids: List[int]) -> Tuple[bool, str, int]` 方法。方法逻辑：
  - 遍历 `record_ids`，对每条：查 `TransRecords` by id
  - 记录不存在 → 加入失败列表
  - `task_id == 0` → 加入失败列表（"task_id 无效"）
  - 查 `TransferConfig` by `task_id`，不存在 → 加入失败列表
  - `srcpath` 为空或 `os.path.exists(srcpath)` 为 False → 加入失败列表（"源文件不存在"）
  - 否则：`celery_transfer_group.delay(task_conf.to_dict(), record.srcpath, True)`，成功数 +1
  - 返回 `(success_count > 0, message, success_count)`
- [x] 2.2 需导入 `from bonita.celery_tasks.tasks import celery_transfer_group` 和 `from bonita.db.models.task import TransferConfig` 及 `import os`

## 3. 后端：API 路由

- [x] 3.1 在 `backend/bonita/api/routes/records.py` 中新增 `POST /retry` 端点，接收 `record_ids: List[int]`（作为 JSON body 或 query param，与现有 `DELETE /records` 的 `record_ids` 模式一致）。调用 `record_service.retry_records(record_ids)`，返回 `schemas.Response(success=..., message=...)`

## 4. 前端：Store 层

- [x] 4.1 在 `frontend/src/stores/record.store.ts` 中新增 `retryRecords(ids: number[])` action：调用 `RecordService` 的 retry 端点（需先重新生成 client 或手动添加），完成后刷新当前页数据
- [x] 4.2 在 `frontend/src/client/services.gen.ts` 中手动添加 `retryRecords` 方法（如果后端未运行无法自动生成），或运行 `npm run generate-client` 重新生成

## 5. 前端：UI 组件

- [x] 5.1 在 `frontend/src/pages/Records.vue` 的工具栏区域（"删除选中"按钮旁）新增"重试选中"按钮：`v-btn` + `color="warning"` + `prepend-icon="mdi-refresh"` + `:disabled="selected.length === 0"`，文字显示 `t('pages.records.retrySelected', { count: selected.length })`
- [x] 5.2 新增重试确认对话框 ref（`retryDialog = ref(false)`），模板中新增 `VDialog`，内容为确认文案 + 确认/取消按钮，与现有删除确认对话框结构一致
- [x] 5.3 新增 `handleRetry()` 方法（设置 `retryDialog = true`）和 `confirmRetry()` 方法（调用 `recordStore.retryRecords(selected)`，成功后 toast 提示、清空 selected、关闭对话框、刷新数据）

## 6. 前端：i18n

- [x] 6.1 在 `frontend/src/plugins/i18n/locales/zh.ts` 的 `records` 命名空间中新增：`retrySelected: "重试选中 ({count})"`、`retryDialog: { title: "确认重试", message: "确认重试选中的 {count} 条记录？", confirm: "重试", cancel: "取消" }`、`retrySuccess: "重试完成"`、`retryFailed: "重试失败"`
- [x] 6.2 在 `frontend/src/plugins/i18n/locales/en.ts` 中新增对应英文翻译

## 7. 验证

- [x] 7.1 选中 2-3 条失败记录，点击"重试选中"，确认弹出对话框
- [x] 7.2 确认重试后，观察 Dashboard 任务页确认有新的转移任务被提交
- [x] 7.3 测试部分失败场景（选中一条 task_id=0 或 srcpath 不存在的记录），确认 toast 正确显示成功/失败汇总
- [x] 7.4 确认重试完成后选中项被清空，当前页数据被刷新
- [x] 7.5 确认未选中记录时"重试选中"按钮禁用
