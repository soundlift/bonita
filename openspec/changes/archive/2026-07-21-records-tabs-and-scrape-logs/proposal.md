## Why

Records 页面当前以单一列表混合显示刮削成功 / 失败 / 中断三种状态的记录，用户在大量数据中无法快速聚焦"需要处理"的失败记录；自动任务扫描对 `success=True` 的记录也会重新刮削，浪费时间和网络请求；最关键的是，用户点重试后无法在 UI 上看到任何执行反馈——日志基础设施虽存在（FastAPI + Celery + WebSocket + Logs 页面），但 Celery worker 写入的日志无法可靠地回流到用户操作 Records 页面的上下文里，导致"看不出有没有成功"。

## What Changes

### 1. Records 页面页签化（严格二分）
- **BREAKING**: 移除工具栏中的状态筛选 `v-select` 下拉框，替换为页面顶部的 `v-tabs`，包含两个固定页签：**未刮削** / **已刮削**。
- 后端 `GET /api/v1/records/all` 的 `success` 查询参数语义扩展：当 `success=False` 时，SHALL 返回所有 `success IS NOT TRUE` 的记录（即 `False` + `NULL`），不再区分失败与中断。当 `success=True` 时行为不变。
- localStorage 持久化字段从 `successFilter` 重命名为 `activeTab`，取值为 `"pending"` 或 `"done"`。
- 默认进入页面时聚焦"未刮削"页签（用户最常需要处理的场景）。

### 2. 任务级 `skip_on_success` 开关
- `TransferConfig` 新增字段 `skip_on_success: Boolean = True`（数据库迁移 + 模型 + schema）。
- `celery_transfer_group` 任务在遍历 `waiting_list` 时，当满足 `(not force_refresh) AND task_info.skip_on_success AND record.success IS TRUE AND NOT record.ignored` 时，SHALL 跳过该记录并记录 INFO 日志。
- 任务编辑表单 `TransferConfigDetailForm.vue` 新增 `v-switch` 控件，让用户可按任务配置此开关。
- 不影响 `force_refresh=True` 的重试路径（用户显式要求重做时永远不跳过）。

### 3. Record 行内刮削日志抽屉
- 新增数据表 `scrape_log`，存储每次刮削执行的完整日志文本、celery task_id、起止时间、状态。
- 自定义 logging Handler（`ScrapeLogHandler`），通过 `task_id_ctx` ContextVar 关联当前 celery 任务与 record_id，将相关日志追加写入 `scrape_log.log_text`。
- `celery_transfer_group` 在处理每条 record 前后创建/关闭 `scrape_log` 记录。
- 新增 API：`GET /api/v1/records/{id}/scrape-log`（返回最近一次）和 `GET /api/v1/records/{id}/scrape-logs`（返回历史列表）。
- Records 页面操作列新增 [查看日志] 按钮，点击打开 `ScrapeLogDrawer.vue` 侧边抽屉，展示该 record 的刮削日志，支持自动刷新（打开时 1s 轮询直到状态为终态）。
- 新增保留策略：每条 record 自动保留最近 20 条 scrape_log，超出的自动清理；30 天前的历史日志自动清理。

### 4. 日志根因排查 Spike
- 作为首个实施任务，验证 Logs 页面 WebSocket 在重试触发后能否实际收到 Celery 写入的日志；若不能，修复 `LOGGING_LOCATION` 路径或 WebSocket 日志文件 tail 的实现。

## Capabilities

### New Capabilities
- `records-tabs`: Records 页面页签化（未刮削/已刮削），替代原状态下拉筛选；包含 active tab 持久化与默认聚焦行为
- `scrape-skip-on-success`: TransferConfig 任务级开关，控制自动扫描时是否跳过已成功记录；包含 `celery_transfer_group` 跳过逻辑与 UI 配置
- `scrape-log-observability`: scrape_log 数据表、日志采集 Handler、查询 API、前端抽屉组件与保留策略，提供 record 维度的刮削执行可观测性

### Modified Capabilities
- `records-view-customization`: 移除 `successFilter` 持久化字段与状态下拉控件需求；这些能力被 `records-tabs` 取代。同时将原 `success=False` 仅匹配 `False OR NULL` 的语义收敛为"匹配 `success IS NOT TRUE`"（语义上等价但表述统一）

## Impact

### 受影响代码
- **后端**
  - `backend/bonita/api/routes/records.py` — 扩展或新增 scrape-log 端点
  - `backend/bonita/services/record_service.py` — `success=False` 过滤语义收敛；新增 scrape_log 查询方法
  - `backend/bonita/celery_tasks/tasks.py` — `celery_transfer_group` 加入 skip 逻辑与 scrape_log 生命周期管理
  - `backend/bonita/db/models/task.py` — `TransferConfig.skip_on_success` 字段
  - `backend/bonita/db/models/` — 新增 `scrape_log.py` 模型
  - `backend/bonita/schemas/` — 新增 `ScrapeLogPublic`，扩展 `TransferConfigPublic`
  - `backend/bonita/utils/logger.py` — 新增 `ScrapeLogHandler` 与 ContextVar 联动
  - `backend/bonita/alembic/versions/` — 两个迁移：TransferConfig 新字段、scrape_log 新表
- **前端**
  - `frontend/src/pages/Records.vue` — 核心重构：v-select → v-tabs，操作列加日志按钮
  - `frontend/src/components/record/ScrapeLogDrawer.vue` — 新组件
  - `frontend/src/components/task/TransferConfigDetailForm.vue` — 加 v-switch
  - `frontend/src/stores/record.store.ts` — 新增 fetchScrapeLog action
  - `frontend/src/i18n/` — 中英文案

### 受影响 API
- `GET /api/v1/records/all` — `success` 参数语义微调（向后兼容）
- `POST /api/v1/tasks/*` — 间接通过 `skip_on_success` 影响行为
- `GET /api/v1/records/{id}/scrape-log(s)` — 新增

### 依赖与风险
- 数据库迁移需要在升级文档中提示
- `ScrapeLogHandler` 写入 DB 的频率需要控制（按 record 批量追加，避免每行日志一次 commit）
- 历史 Records 页面的 localStorage 数据迁移（旧 key `records-view-settings` 中 `successFilter` 字段作废）
