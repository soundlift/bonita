## 1. celery_scrapping 任务支持 force_refresh

- [x] 1.1 在 `backend/bonita/celery_tasks/tasks.py` 的 `celery_scrapping` 任务签名新增 `force_refresh: bool = False` 参数
- [x] 1.2 在 ExtraInfo 已存在的分支中,当 `force_refresh=True` 时用 `FileNumInfo(file_path)` 重新解析,刷新 `number`/`tag`/`partNumber`,保留 `specifiedsource`/`specifiedurl` 不变;`crop` 仅当为 None 时根据新 number 推断
- [x] 1.3 当 `force_refresh=True` 时,跳过 `session.query(Metadata).filter(number==...)` 缓存查询分支,直接走 `scraping()` 网络抓取
- [x] 1.4 验证 `force_refresh=False`(默认)时行为与现有逻辑完全一致

## 2. celery_transfer_group 任务支持 force_refresh

- [x] 2.1 在 `backend/bonita/celery_tasks/tasks.py` 的 `celery_transfer_group` 任务签名新增 `force_refresh: bool = False` 参数
- [x] 2.2 在处理每个文件的开头(for循环内、刮削/直接转移分支之前),当 `force_refresh=True` 且 `record.destpath` 存在且文件存在时,无条件删除旧目标文件
- [x] 2.3 在刮削分支中调用 `celery_scrapping` 时,透传 `force_refresh` 参数(修改 `celery_scrapping.apply` 的 args)
- [x] 2.4 验证 `force_refresh=False`(默认)时行为与现有逻辑完全一致(monitor 自动入库不受影响)

## 3. 后端入口对接 force_refresh

- [x] 3.1 在 `backend/bonita/services/record_service.py` 的 `retry_records` 方法中,`celery_transfer_group.delay(...)` 调用增加 `force_refresh=True` 参数
- [x] 3.2 在 `backend/bonita/api/routes/tasks.py` 的 `run_transfer_task` 端点中,当 `path_param.path` 非空时,`celery_transfer_group.delay(...)` 调用增加 `force_refresh=True`;path 为空时(整任务重跑)不传,走默认 False

## 4. 前端文案更新

- [x] 4.1 在 `frontend/src/pages/Records.vue` 的重试确认对话框中,文案明确告知"将重新解析编号、重新刮削元数据、删除旧的目标文件"
- [x] 4.2 在 `frontend/src/plugins/i18n/locales/zh.ts` 和 `en.ts` 中同步更新重试对话框文案

## 5. 验证

- [x] 5.1 验证批量重试(`POST /records/retry`)触发 force_refresh:ExtraInfo.number 被重新解析、旧 destpath 被删除、Metadata 走网络抓取
- [x] 5.2 验证单条重试(操作列图标 → `POST /tasks/run/{id}` 带 path)触发 force_refresh,行为与批量重试一致
- [x] 5.3 验证重试后 `TransRecords.createtime` 保持原值不变,仅 `updatetime` 刷新
- [x] 5.4 验证 monitor 自动入库(走 `celery_transfer_entry` → `celery_transfer_group` 默认参数)行为不受影响
- [x] 5.5 验证整任务重跑(`POST /tasks/run/{id}` path 为空)不触发 force_refresh
