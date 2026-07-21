## Context

当前 Records 页面 (`frontend/src/pages/Records.vue`) 通过 `successFilter: ref<boolean | null>(null)` 配合一个 `v-select` 下拉实现状态筛选。后端 `GET /api/v1/records/all` 已支持 `success: Optional[bool]` 参数，`record_service.py:67-71` 中 `success=False` 的实现是 `or_(success == False, success.is_(None))`。

刮削流水线由 Celery 驱动（`celery_transfer_group` → `celery_scrapping`），日志通过 `RotatingFileHandler` 写入 `./data/bonita.log`（相对路径）。Logs 页面经 WebSocket (`/api/v1/ws/logs`) tail 该文件并解析行。已知问题：用户在 Records 页点重试后无法看到刮削过程日志——根因可能是 (a) 部署时 uvicorn 与 celery 进程的相对路径解析不一致，(b) WebSocket 端 log_pattern 正则 `r"\[(.*?)\] (\w+) in ([\w\.]+): (.*)"` 对 Celery task logger 名（如 `celery.task` 或带 `celery.worker` 前缀）可能漏匹配，(c) Logs 页面在重连时 `logStore.logs = []` 清空历史。

监控服务 `monitor.py` 仅响应新文件事件，所以"扫描已成功记录"问题主要发生在 `celery_transfer_entry` 全量重跑场景。`celery_transfer_group` 每次进入循环都会 `record.success = None`，没有任何"已成功则跳过"的判断。

## Goals / Non-Goals

**Goals:**
- Records 页面通过页签将"未刮削"与"已刮削"两类记录物理分离，降低用户认知负担
- 在任务维度提供"是否跳过已刮削"开关，避免无意义重复刮削
- 为每条 record 提供可观测的、与上下文绑定的刮削日志展示，用户无需跳转到 Logs 页面即可看到本次执行的完整过程
- 修复 Logs 页面日志回流问题（作为前置 spike）

**Non-Goals:**
- 不重构 Celery 任务执行模型或并发控制（`Semaphore` 保留不动）
- 不改变 `force_refresh=True` 路径的语义（重试永远不跳过）
- 不替换日志基础设施（仍用 stdlib logging + RotatingFileHandler；新增的 `ScrapeLogHandler` 是叠加，不是替换）
- 不引入新的前端状态管理库（继续用 Pinia 现有 store）
- 不做权限/多租户隔离（沿用现有 JWT 鉴权）

## Decisions

### Decision 1: 页签 vs 保留状态下拉
**选择**: 用 `v-tabs` 物理替换 `v-select`。

**理由**: 用户明确表达"拆分为两个页签"，且未刮削/已刮削是互斥视图，页签的视觉分离优于下拉。下拉适合"过滤"，页签适合"切换主视角"。

**Alternative**: 保留 `v-select` 但固定只允许 `null/true/false` 三态——拒绝，违背用户原话。

### Decision 2: `success=False` 语义统一为 `success IS NOT TRUE`
**选择**: 后端过滤从 `or_(success == False, success.is_(None))` 改写为 `TransRecords.success.isnot(True)`（SQLAlchemy 等价于 `success IS NOT TRUE`，覆盖 False + NULL）。

**理由**: 用户选择"严格二分"，但"未刮削"页签的语义实际就是"非已刮削"——失败和中断都应进入此视图让用户决定处理。`IS NOT TRUE` 是 SQL 标准写法，行为可预测。

**Alternative**: 用枚举 `success: "pending" | "done"` 替代 bool 参数——拒绝，破坏向后兼容且无收益。

### Decision 3: 任务级开关而非全局开关
**选择**: 在 `TransferConfig` 加 `skip_on_success: Boolean = True` 列。

**理由**: 用户选择"任务级开关"。不同任务语义不同：日常监控任务应跳过，迁移/修复任务需要全量重跑。默认 `True` 符合大多数场景。

**Alternative**:
- 全局 setting：太粗，无法应对迁移场景
- 用现有 `locked` 字段：locked 是 record 级而非 task 级，语义错位

### Decision 4: scrape_log 表 vs 文件 vs Celery result_backend
**选择**: 新增 `scrape_log` 表，存储完整日志文本 + 元数据。

**理由**:
- Celery result_backend (`TaskProgressTracker`) 只存进度和最终结果，不存日志文本
- 文件方案难以按 record 检索，且会与全局 log 文件耦合
- DB 方案支持按 record_id 索引、按时间排序、支持保留策略清理、支持前端抽屉实时查询

**Schema**:
```python
class ScrapeLog(Base):
    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey('transrecords.id'), index=True, nullable=False)
    celery_task_id = Column(String, default='', comment='Celery 任务 ID')
    status = Column(String, default='running', comment='running|success|failed|interrupted')
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, default=None)
    log_text = Column(Text, default='')
    error_msg = Column(Text, default='')
```

**Alternative**: 复用 `transrecords` 加 `last_scrape_log` TEXT 字段——拒绝，无法保留历史。

### Decision 5: ScrapeLogHandler 设计（ContextVar 关联）
**选择**: 扩展现有 `task_id_ctx` ContextVar 为复合上下文 `(celery_task_id, record_id)`，新增 `ScrapeLogHandler(logging.Handler)` 在 emit 时读取上下文，若 `record_id` 非空则将格式化后的日志行追加到对应 `scrape_log.log_text`。

**批量写入策略**: Handler 内部维护内存缓冲 `Dict[record_id, list[str]]`，每收到 N 条或 1 秒间隔时 flush 到 DB。避免每行日志一次 commit。

**线程安全**: Celery thread pool 下多线程并发，ContextVar 天然线程隔离；缓冲 dict 用 `threading.Lock` 保护。

**Alternative**:
- 直接 patch logger 全部走 DB：性能差
- 用 Celery signal `task_success`/`task_failure` 收集：拿不到中间日志
- 用 structured logging + 单独的日志聚合服务（ELK）：过度工程

### Decision 6: 前端抽屉轮询而非 WebSocket
**选择**: `ScrapeLogDrawer.vue` 打开时以 1s 间隔轮询 `GET /api/v1/records/{id}/scrape-log`，直到 `status` 为终态。

**理由**:
- 单 record 的日志 SSE/WebSocket 通道对后端复杂度过高
- 1s 轮询对单用户单 record 场景性能足够（QPS = 1）
- 用户关闭抽屉立即停止轮询，无后台开销

**Alternative**: 复用全局 Logs WebSocket 并按 record_id 过滤——拒绝，全局通道不携带 record_id 字段，需要改造协议，影响面太大。

### Decision 7: 保留策略
**选择**: 双策略并行：
- 每条 record 自动保留最近 20 条 scrape_log（超出按 `started_at` 倒序删除）
- 30 天前的 scrape_log 自动清理
- 清理在 `celery_transfer_group` 结束时触发（每次处理 record 后检查该 record 的日志数量），低频后台任务清理全局过期日志

**Alternative**: 不做清理——拒绝，长期会膨胀。

## Risks / Trade-offs

### 风险 1: ScrapeLogHandler 写入 DB 可能影响刮削性能
**风险**: 高频 append 日志到 DB 可能阻塞 Celery worker。
**缓解**: 内存缓冲 + 批量 flush（每 N 行或 1 秒）；刮削关键路径（`scraping()` 网络请求）耗时远大于 DB 写入，可忽略。

### 风险 2: ContextVar 在 Celery thread pool 下行为
**风险**: Celery `--pool threads` 下任务在线程池执行，ContextVar 在线程间不自动继承。`celery_transfer_group` 内调用 `task_id_ctx.set(...)` 只对当前线程生效。
**缓解**: 在每个 record 处理循环开始处显式 `task_id_ctx.set(...)`，且 `ScrapeLogHandler` 在同一线程内读取——同线程内读写 ContextVar 是安全的。

### 风险 3: 旧 localStorage 数据迁移
**风险**: 升级后用户的 `records-view-settings` 中 `successFilter` 字段作废，但代码尝试读取可能报错。
**缓解**: `loadSettings()` 已有 try/catch；显式检测 `successFilter` 字段并迁移为 `activeTab`（true → "done"，false/null → "pending"）。

### 风险 4: WebSocket 日志根因未定位即开工
**风险**: Spike 4 可能发现根因超出预期（如 Celery 进程确实没写日志到共享路径），需要重新设计日志架构。
**缓解**: Spike 作为 tasks.md 第一个任务，先验证后实施；若根因复杂则单独建一个 change 处理 Logs 页面，本次 change 聚焦 scrape_log 行内抽屉（独立于全局 Logs）。

### 风险 5: 数据库迁移在已部署实例上的兼容性
**风险**: `skip_on_success` 默认 `True`，但已存在任务可能本意是"全量重跑"。
**缓解**: 迁移时显式 `server_default='1'`（True），并在 release notes 提示用户如需全量重跑可在任务编辑中关闭。

## Migration Plan

1. **DB 迁移（顺序敏感）**:
   - 先执行 `scrape_log` 表创建迁移
   - 再执行 `TransferConfig.skip_on_success` 字段添加迁移
2. **后端代码部署**: 一次性发布所有后端变更（模型、service、tasks、handlers、API）
3. **前端代码部署**: 一次性发布（Records.vue 重构、ScrapeLogDrawer、TransferConfigDetailForm 改动）
4. **回滚策略**:
   - DB 迁移可 downgrade
   - 后端代码回滚后，scrape_log 表残留可手动清理或保留
   - 前端 localStorage 旧字段 `successFilter` 保留，回滚后仍可读取

## Open Questions

1. **ScrapeLogHandler 缓冲 flush 时机**：是按行数（如 50 行）还是按时间间隔（如 1 秒）触发？两者结合还是取一？建议实施时实测性能决定。
2. **`skip_on_success` 在监控新文件场景的行为**：监控触发的是新文件，本来就没有历史 success=True 记录，理论上开关不影响。但若同一文件被删除后重建（如Transmission重新下载），record 复用且 `success=True`，是否应跳过？默认应跳过（尊重用户配置），但需要文档说明。
3. **scrape_log 表是否需要软删除或归档**：30 天清理是否够？是否应提供导出 API 让用户备份？暂不实现，未来按需添加。
