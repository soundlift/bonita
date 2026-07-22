## 1. 移除 `transfer:all` 自动重试

- [x] 1.1 在 `backend/bonita/celery_tasks/tasks.py` 的 `celery_transfer_entry` 装饰器中，移除 `autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}` 参数，仅保留 `bind=True` 和 `name='transfer:all'`
- [x] 1.2 验证：语法检查通过，`celery_transfer_entry` 的 `@shared_task` 仅保留 `bind=True, name='transfer:all'`

## 2. 统一同步执行，消除死锁

- [x] 2.1 在 `celery_transfer_entry` 中，将 `MAX_CONCURRENCY` 条件分支（lines 68-71）替换为 `transfer_result = transfer_group.apply()`
- [x] 2.2 移除 `with allow_join_result():` 上下文管理器（line 75），保留 `done_list = transfer_result.get()`
- [x] 2.3 将 `MAX_CONCURRENCY` 条件分支（lines 95-98）替换为 `celery_clean_others.apply(args=[task_info.output_folder, done_list])`
- [x] 2.4 将 `MAX_CONCURRENCY` 条件分支（lines 101-104）替换为 `celery_emby_scan.apply(args=[task_json])`
- [x] 2.5 验证：`celery_transfer_entry` 中不再有 `os.environ.get("MAX_CONCURRENCY")` 和 `apply_async` 调用

## 3. 清理无用导入

- [x] 3.1 检查 `allow_join_result` 是否仍被 `celery_transfer_group` 使用（line 237），若是则保留导入；若否则移除 `from celery.result import allow_join_result`
- [x] 3.2 验证：语法检查通过

## 4. 验证

- [x] 4.1 运行 `python -c "from bonita.celery_tasks.tasks import celery_transfer_entry"` 确认导入无异常
- [x] 4.2 检查 `celery_transfer_entry` 函数体中无 `apply_async`、`allow_join_result`、`MAX_CONCURRENCY` 关键字
- [x] 4.3 检查 `celery_transfer_group` 内部的 `celery_scrapping.apply()` + `get()` 保持不变（内层同步调用无死锁风险）
