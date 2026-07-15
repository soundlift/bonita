## 1. 后端：修复 Celery 异常处理

- [x] 1.1 在 `backend/bonita/celery_tasks/tasks.py` 的 `celery_transfer_group` 函数 `except Exception as e:` 块（约第 344 行）中，在 `logger.error(e)` 之后，安全地将当前 `record.success` 设为 `False`。使用 `'record' in locals() and record` 模式检查变量是否存在，避免 `NameError`
- [x] 1.2 验证修复：模拟异常场景（如临时在 `record.success = None` 后抛出异常），确认数据库中 `success` 被设为 `False` 而非 `NULL`

## 2. 后端：修正失败筛选逻辑

- [x] 2.1 在 `backend/bonita/services/record_service.py` 的 `get_records` 方法中，将 `success` 过滤条件从 `TransRecords.success == success`（当 `success=False` 时）改为 `or_(TransRecords.success == False, TransRecords.success.is_(None))`。当 `success=True` 时保持 `TransRecords.success == True`。需导入 `or_`（已在文件第 7 行导入）
- [x] 2.2 在 `get_records` 方法的 count 查询部分（约第 91-92 行）同步修改 `success` 过滤条件，确保分页总数一致
- [x] 2.3 编写或手动验证测试：数据库中同时存在 `success=True`、`success=False`、`success=NULL` 的记录时，`success=false` 筛选返回 `False` + `NULL` 的记录，`success=true` 只返回 `True` 的记录

## 3. 前端：状态列三态渲染

- [x] 3.1 在 `frontend/src/pages/Records.vue` 的状态列模板（约第 578-590 行）中，将 `v-if="item.transfer_record.success !== null"` 的单一分支改为三分支渲染：`success === true` 显示绿色 chip + `bx-check`；`success === false` 显示红色 chip + `bx-x`；`success === null` 显示灰色 chip + `mdi-alert`
- [x] 3.2 在 `frontend/src/plugins/i18n/locales/zh.ts` 和 `en.ts` 的 `records` 命名空间中新增 `interruptedStatus`（"中断" / "Interrupted"）文案，用于状态筛选 chip 或 tooltip

## 4. 验证

- [x] 4.1 调用 `GET /api/v1/records/all?success=false`，确认返回包含 `success=False` 和 `success=NULL` 的记录，count 总数正确
- [x] 4.2 调用 `GET /api/v1/records/all?success=true`，确认只返回 `success=True` 的记录
- [x] 4.3 调用 `GET /api/v1/records/all`（不传 success），确认返回所有记录（含 NULL）
- [x] 4.4 打开 Records 页面，确认 `success=null` 的记录状态列显示灰色中断图标，`success=false` 显示红色失败图标，`success=true` 显示绿色成功图标
- [x] 4.5 在状态筛选中选择"失败"，确认表格同时显示失败和中断状态的记录
