## 1. 前置 Spike：日志根因排查

- [x] 1.1 触发一次重试，对比 `backend/data/bonita.log` 实际内容与 Logs 页面 WebSocket 接收到的内容，确认是否丢失 Celery 写入的日志
- [x] 1.2 检查 Celery worker 进程的 `LOGGING_LOCATION` 相对路径解析（uvicorn 与 celery 的工作目录是否一致），如不一致在 `config.py` 改为绝对路径或基于 `BASE_DIR` 拼接
- [x] 1.3 验证 `logs.py:93` 的正则 `r"\[(.*?)\] (\w+) in ([\w\.]+): (.*)"` 是否能匹配 Celery task logger 输出（如 `celery.task`、`celery.worker`），不能匹配则放宽 module 部分（如 `([\w\.]+)`）
- [x] 1.4 在 Records 页面和 Logs 页面之间加一个跳转链接作为临时缓解（待 scrape_log 抽屉上线后可移除）

> Spike 结论：1.1-1.3 的根因在后续 `fix-backend-audit-bugs` change 中修复——`LOGGING_LOCATION` 改为绝对路径、PID/TID 前缀通过 `_CLEAN_PID_TID` 正则剥离。1.4 临时跳转已被正式的 ScrapeLogDrawer 抽屉替代（见第 10 节），无需实现。

## 2. 数据库迁移：scrape_log 表

- [x] 2.1 创建 `backend/bonita/db/models/scrape_log.py`，定义 `ScrapeLog` 模型（字段：id, record_id, celery_task_id, status, started_at, finished_at, log_text, error_msg），`record_id` 外键引用 `transrecords.id` 且 `ON DELETE CASCADE`
- [x] 2.2 在 `backend/bonita/db/models/__init__.py`（或等效位置）注册 `ScrapeLog` 模型确保 Alembic 发现
- [x] 2.3 生成 Alembic 迁移：`alembic revision --autogenerate -m "add scrape_log table"`，检查迁移脚本包含 `scrape_log` 表与 `(record_id, started_at DESC)` 复合索引
- [x] 2.4 在迁移脚本中验证外键 `ON DELETE CASCADE` 子句存在
- [x] 2.5 执行 `alembic upgrade head`，本地验证表创建成功

## 3. 数据库迁移：TransferConfig.skip_on_success 字段

- [x] 3.1 在 `backend/bonita/db/models/task.py` 的 `TransferConfig` 类中添加 `skip_on_success = Column(Boolean, default=True, server_default='1', comment='扫描时是否跳过已成功记录')`
- [x] 3.2 在 `backend/bonita/schemas/task.py` 的 `TransferConfigPublic`（及对应 update schema）中添加 `skip_on_success: bool = True` 字段
- [x] 3.3 确认 `TransferConfig.to_dict()` 会自动包含新字段（若需要显式声明则更新）
- [x] 3.4 生成 Alembic 迁移：`alembic revision --autogenerate -m "add skip_on_success to transferconfig"`
- [x] 3.5 检查迁移脚本中 `server_default='1'` 存在，执行 `alembic upgrade head` 验证

## 4. 后端：records API success 语义统一

- [x] 4.1 修改 `backend/bonita/services/record_service.py:67-71`，将 `success is False` 分支的过滤从 `or_(success == False, success.is_(None))` 改为 `TransRecords.success.isnot(True)`（SQL 等价 `IS NOT TRUE`）
- [x] 4.2 同步修改 count 查询的 `success is False` 分支（`record_service.py:96-98`）保持一致
- [x] 4.3 更新 `backend/bonita/api/routes/records.py:11-28` 中 `get_records` 的 docstring，将 `success=false` 描述改为"返回 success 不为 True 的记录（False 与 NULL）"
- [x] 4.4 手动测试：`GET /api/v1/records/all?success=false` 同时返回 False 与 NULL 记录，`count` 正确

## 5. 后端：scrape_log 查询 API

- [x] 5.1 在 `backend/bonita/schemas/` 中新增 `scrape_log.py`，定义 `ScrapeLogPublic` schema（包含 id, record_id, celery_task_id, status, started_at, finished_at, log_text, error_msg）
- [x] 5.2 在 `backend/bonita/services/record_service.py`（或新建 `scrape_log_service.py`）中实现 `get_latest_scrape_log(record_id)` 和 `get_scrape_logs(record_id, limit=20)` 方法
- [x] 5.3 在 `backend/bonita/api/routes/records.py` 中新增 `GET /records/{record_id}/scrape-log`（返回最近一条，无则 404）与 `GET /records/{record_id}/scrape-logs`（返回最多 20 条历史）
- [x] 5.4 测试 API：用 curl 或 OpenAPI UI 验证两个端点的鉴权与返回格式

## 6. 后端：ScrapeLogHandler 日志采集

- [x] 6.1 在 `backend/bonita/utils/logger.py` 中扩展 `task_id_ctx` ContextVar 为元组 `(celery_task_id, record_id)`，提供 helper 函数 `set_scrape_context(celery_id, record_id)` 与 `get_current_record_id()`
- [x] 6.2 在同文件实现 `ScrapeLogHandler(logging.Handler)` 类：emit 时通过 `get_current_record_id()` 判断，若非空则将格式化后的日志行加入内存缓冲 `Dict[record_id, List[str]]`（`threading.Lock` 保护）
- [x] 6.3 实现 flush 逻辑：当某 record_id 缓冲达 50 行或距上次 flush 超 1 秒时，批量 append 到对应 `scrape_log.log_text`；提供 `flush_for_record(record_id)` 强制 flush 入口
- [x] 6.4 在 `init_log_config()` 中将 `ScrapeLogHandler` 实例添加到 root logger 的 handlers 列表（与现有 `RotatingFileHandler` 并存）
- [x] 6.5 单元测试：mock ContextVar 与 DB session，验证日志按预期被缓冲与 flush

## 7. 后端：celery_transfer_group 集成

- [x] 7.1 修改 `backend/bonita/celery_tasks/tasks.py:180-193` 附近的 record 处理循环，在 `record.task_id = task_info.id` 之前加入 `skip_on_success` 判断：`(not force_refresh) AND task_info.skip_on_success AND record.success is True AND not record.ignored`，满足时 `logger.info("⊘ 已成功且配置跳过，跳过: ...")` + `continue`
- [x] 7.2 在每条 record 处理开始前创建 `ScrapeLog` 记录（`status='running'`, `started_at=datetime.now()`, `celery_task_id=self.request.id`），调用 `set_scrape_context(self.request.id, record.id)`
- [x] 7.3 record 处理成功后（`record.success = True`）：更新 `scrape_log.status='success'`、`finished_at`，调用 `flush_for_record(record.id)`，清空 context
- [x] 7.4 record 处理失败后（`record.success = False` 的各 continue 分支）：更新 `scrape_log.status='failed'`、`finished_at`，flush + 清空 context
- [x] 7.5 异常分支（`except Exception as e`）：更新 `scrape_log.status='interrupted'`、`error_msg=str(e)[:500]`、flush + 清空 context
- [x] 7.6 单条 record 插入 scrape_log 后，触发保留策略：`DELETE FROM scrape_log WHERE record_id=? AND id NOT IN (SELECT id FROM scrape_log WHERE record_id=? ORDER BY started_at DESC LIMIT 20)`（保留最新成功日志的特殊处理）
- [x] 7.7 端到端测试：触发一次重试，确认 `scrape_log` 表有完整记录，`log_text` 包含过程日志

## 8. 后端：scrape_log 过期清理任务

- [x] 8.1 在 `backend/bonita/celery_tasks/tasks.py` 新增 `@shared_task(name='cleanup:scrape_logs')` 任务，删除 30 天前的 scrape_log（但保留每条 record 最新一条 success 日志）
- [x] 8.2 在 Celery beat 配置中注册每日触发（参考现有 beat 调度配置位置）
- [x] 8.3 测试：手工插入过期数据，触发任务验证清理结果

## 9. 前端：Records.vue 页签化重构

- [x] 9.1 在 `Records.vue` 顶部模板中用 `v-tabs` + `v-tab` 替换状态筛选 `v-select`，定义 `activeTab = ref<'pending' | 'done'>('pending')`
- [x] 9.2 删除 `successFilter` ref 与 `statusOptions` computed；新增 `watch(activeTab)` 调用 `loadData`，将 `success: activeTab.value === 'pending' ? false : true` 传入 searchParams
- [x] 9.3 修改 `loadSettings()`：读取 localStorage `records-view-settings` 时检测旧字段 `successFilter`，迁移为 `activeTab`（true→'done'，其他→'pending'），从存储对象删除 `successFilter` 字段
- [x] 9.4 修改 `saveSettings()`：存储对象用 `activeTab` 替代 `successFilter`
- [x] 9.5 修改 `watch` 监听列表：将 `[searchQuery, taskIdQuery, successFilter]` 改为 `[searchQuery, taskIdQuery, activeTab]`
- [x] 9.6 删除模板中 `search-filters` 区域显示 `successFilter` chip 的代码块（或改为不可关闭，因为 tab 已表示）
- [x] 9.7 删除 `handleClearSearch` 中对 `successFilter.value = null` 的重置
- [x] 9.8 验证：切换页签时表格数据正确刷新、localStorage 持久化生效、旧数据迁移正常

## 10. 前端：ScrapeLogDrawer 组件

- [x] 10.1 新建 `frontend/src/components/record/ScrapeLogDrawer.vue`，基于 `v-navigation-drawer`（位置 right，宽度 600）
- [x] 10.2 Props: `modelValue: boolean`（控制开闭）、`recordId: number | null`；emits `update:modelValue`
- [x] 10.3 实现 `loadLatestLog()` 调用 `GET /api/v1/records/{recordId}/scrape-log`，处理 404 显示"暂无刮削日志"
- [x] 10.4 抽屉打开时启动 1s 轮询定时器，状态非终态（success/failed/interrupted）时持续轮询，终态后停止；抽屉关闭时立即清空定时器
- [x] 10.5 渲染状态徽标（color: running=info, success=success, failed=error, interrupted=warning）、celery_task_id、起止时间、log_text（等宽字体、pre-wrap、自动滚动到底部）、error_msg（失败时高亮）
- [x] 10.6 在 `frontend/src/stores/record.store.ts` 新增 `fetchLatestScrapeLog(recordId)` 与 `fetchScrapeLogs(recordId)` actions，使用生成的 API client
- [x] 10.7 重新生成前端 API client（参考 frontend README 中的 `npm run generate-client`），确保新端点可用

## 11. 前端：Records 操作列加日志按钮

- [x] 11.1 在 `Records.vue` 操作列的 `v-slot:item.actions` 中新增 `<VBtn size="small" @click="openScrapeLogDrawer(item)"><VIcon icon="mdi-file-document-outline" /></VBtn>`
- [x] 11.2 添加状态 `scrapeLogDrawerOpen = ref(false)` 与 `currentScrapeLogRecordId = ref<number | null>(null)`
- [x] 11.3 在模板末尾挂载 `<ScrapeLogDrawer v-model="scrapeLogDrawerOpen" :record-id="currentScrapeLogRecordId" />`
- [x] 11.4 实现 `openScrapeLogDrawer(item)` 设置 recordId 并打开抽屉
- [x] 11.5 在 `frontend/src/i18n/zh-CN.json` 与 `en-US.json`（或对应 i18n 文件）新增文案：`pages.records.viewScrapeLog`（"查看日志"/"View Log"）、`pages.records.noScrapeLog`（"暂无刮削日志"/"No scrape log"）等

## 12. 前端：TransferConfigDetailForm 加 skip_on_success 开关

- [x] 12.1 在 `frontend/src/components/task/TransferConfigDetailForm.vue` 中新增 `v-switch` 控件绑定到 `formData.skip_on_success`，label 文案"扫描时跳过已刮削的记录"（i18n key 如 `components.taskConfig.skipOnSuccess`）
- [x] 12.2 位置建议放在 `auto_watch` 相关开关附近（同为扫描行为配置）
- [x] 12.3 验证表单提交时该字段正确传递到后端 `PUT /api/v1/taskconfigs/{id}`

## 13. 集成测试与文档

- [x] 13.1 端到端测试场景 A：未刮削页签 → 重试选中 → 抽屉查看日志 → 日志完整显示刮削过程
- [x] 13.2 端到端测试场景 B：任务开启 `skip_on_success` → `POST /tasks/run/{id}`（path 为空）全量重跑 → 确认 `success=True` 记录被跳过、日志可见
- [x] 13.3 端到端测试场景 C：`force_refresh=True` 重试路径 → 确认即使 `skip_on_success=True` 也不跳过
- [x] 13.4 端到端测试场景 D：scrape_log 保留策略 - 单 record 插入 21 条后自动保留 20 条最新；30 天前数据被 beat 任务清理
- [x] 13.5 更新 `README.md` 或部署文档，说明新增的 `skip_on_success` 字段语义与 scrape_log 表用途
- [x] 13.6 在 `openspec` 中运行 `openspec validate records-tabs-and-scrape-logs` 确认所有 spec 完整
