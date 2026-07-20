# Scrape Log Observability Specification

## Purpose

为每次刮削执行提供完整的可观测性：通过 `scrape_log` 表持久化日志、自定义 logging Handler 采集日志、Celery 任务管理生命周期、查询 API 与前端抽屉组件展示，以及保留策略。

## Requirements

### Requirement: scrape_log 数据表与模型
系统 SHALL 新增数据表 `scrape_log` 存储每次刮削执行的日志记录。表结构 SHALL 包含以下字段：
- `id`: Integer, 主键，自增
- `record_id`: Integer, 外键引用 `transrecords.id`，SHALL 建立索引
- `celery_task_id`: String, 默认空字符串，存储 Celery 任务 ID
- `status`: String, 默认 `'running'`，取值集合 `{running, success, failed, interrupted}`
- `started_at`: DateTime, 默认当前时间
- `finished_at`: DateTime, 可空
- `log_text`: Text, 默认空字符串，存储完整日志文本（追加写）
- `error_msg`: Text, 默认空字符串，存储失败原因摘要

模型 SHALL 通过 Alembic 迁移创建。迁移 SHALL 同时为 `(record_id, started_at DESC)` 创建复合索引以加速按 record 查询最新日志。

#### Scenario: 数据表创建
- **WHEN** 执行 `scrape_log` 表创建迁移
- **THEN** 表 SHALL 包含上述所有字段，`record_id` 字段 SHALL 有索引，`(record_id, started_at)` SHALL 有复合索引

#### Scenario: record 被删除时的级联行为
- **WHEN** 某条 `transrecords` 记录被强制删除（`force=True`）
- **THEN** 关联的 `scrape_log` 记录 SHALL 通过外键 `ON DELETE CASCADE` 自动删除，避免孤儿日志

### Requirement: ScrapeLogHandler 日志采集
系统 SHALL 新增自定义 logging Handler `ScrapeLogHandler`（继承 `logging.Handler`）。该 Handler SHALL 通过 `task_id_ctx` ContextVar 读取当前线程的 `record_id` 上下文。当 `record_id` 非空时，Handler SHALL 将格式化后的日志行追加到内存缓冲。

Handler SHALL 实现批量 flush 策略：缓冲满足以下任一条件时 SHALL flush 到数据库：
- 缓冲行数达到 50 行
- 距上次 flush 超过 1 秒
- 收到 flush 信号（如 record 处理结束）

Handler SHALL 使用 `threading.Lock` 保护内存缓冲，确保 Celery `--pool threads` 下的线程安全。

`init_log_config()` SHALL 在保留现有 `RotatingFileHandler` 的基础上，额外注册 `ScrapeLogHandler` 到 root logger。

#### Scenario: 刮削过程中的日志采集
- **WHEN** `celery_transfer_group` 处理某 record 时通过 `task_id_ctx` 设置了 `record_id`，且 logger.info 输出日志
- **THEN** `ScrapeLogHandler` SHALL 将该日志行缓冲，并在 flush 时追加到对应 `scrape_log.log_text`

#### Scenario: 无 record_id 上下文的日志不采集
- **WHEN** 系统其他模块（非刮削流程）输出日志，`task_id_ctx` 中 `record_id` 为空
- **THEN** `ScrapeLogHandler` SHALL 忽略该日志，不写入 `scrape_log` 表

#### Scenario: 批量 flush 性能保证
- **WHEN** 刮削流程中短时间内产生 200 行日志
- **THEN** Handler SHALL 在累计 50 行时 flush 一次，避免每行一次 DB 写入；4 次 flush 完成全部日志写入

### Requirement: celery_transfer_group 集成 scrape_log 生命周期
`celery_transfer_group` 任务在处理每条 record 时 SHALL 管理 `scrape_log` 记录的生命周期：

1. 在开始处理 record 前（设置 `record.success = None` 之前），SHALL 创建一条 `scrape_log` 记录，`status='running'`，`started_at=datetime.now()`，并通过 `task_id_ctx.set((celery_task_id, record.id))` 设置上下文。
2. 处理过程中所有的 `logger.*` 调用 SHALL 经 `ScrapeLogHandler` 自动追加到 `scrape_log.log_text`。
3. record 处理结束时（无论成功或失败），SHALL：
   - 设置 `scrape_log.status` 为 `'success'`（若 `record.success=True`）或 `'failed'`（其他情况）
   - 设置 `scrape_log.finished_at = datetime.now()`
   - 调用 Handler 的 flush 确保所有缓冲日志落库
   - 通过 `task_id_ctx.set(("", None))` 清空上下文
4. 若处理过程中抛出异常，异常处理分支 SHALL 将 `scrape_log.status` 设为 `'interrupted'`，并将异常摘要写入 `error_msg` 字段。

#### Scenario: 成功刮削的生命周期
- **WHEN** `celery_transfer_group` 成功处理一条 record（最终 `record.success=True`）
- **THEN** 对应的 `scrape_log` 记录 SHALL 有 `status='success'`、`finished_at` 非空、`log_text` 包含完整过程日志

#### Scenario: 刮削失败的生命周期
- **WHEN** 处理过程中刮削返回 None（如未找到元数据），最终 `record.success=False`
- **THEN** 对应的 `scrape_log` 记录 SHALL 有 `status='failed'`、`log_text` 包含失败过程日志、`error_msg` 含失败原因

#### Scenario: 异常中断的生命周期
- **WHEN** 处理过程中抛出未捕获异常（进入 `except Exception` 分支）
- **THEN** 对应的 `scrape_log` 记录 SHALL 有 `status='interrupted'`、`error_msg` 含异常摘要（`str(e)` 前 500 字符）

### Requirement: scrape_log 查询 API
系统 SHALL 新增两个 API 端点：

1. `GET /api/v1/records/{record_id}/scrape-log` — 返回该 record 最近一条 `scrape_log` 记录（按 `started_at` 倒序）。若无记录 SHALL 返回 404。
2. `GET /api/v1/records/{record_id}/scrape-logs` — 返回该 record 的所有 `scrape_log` 记录列表（按 `started_at` 倒序），最多 20 条。

两个端点 SHALL 复用现有 JWT 鉴权机制。返回的 schema SHALL 包含 `id, record_id, celery_task_id, status, started_at, finished_at, log_text, error_msg` 字段。

#### Scenario: 查询最近日志
- **WHEN** 客户端调用 `GET /api/v1/records/123/scrape-log`，且 record #123 存在 scrape_log 记录
- **THEN** 端点 SHALL 返回最近一条记录的完整信息，HTTP 200

#### Scenario: 查询不存在日志
- **WHEN** 客户端调用 `GET /api/v1/records/123/scrape-log`，且 record #123 无任何 scrape_log 记录
- **THEN** 端点 SHALL 返回 HTTP 404，错误信息提示该 record 无刮削日志

#### Scenario: 查询历史列表
- **WHEN** 客户端调用 `GET /api/v1/records/123/scrape-logs`，且 record #123 有 25 条 scrape_log 记录
- **THEN** 端点 SHALL 返回最近 20 条记录（按 `started_at` 倒序），HTTP 200

### Requirement: 前端 ScrapeLogDrawer 组件
前端 SHALL 新增组件 `ScrapeLogDrawer.vue`（基于 `v-navigation-drawer`）。Records 页面的操作列 SHALL 新增一个 [查看日志] 按钮（图标 `mdi-file-document-outline`），点击后 SHALL 打开抽屉展示该 record 的刮削日志。

抽屉打开时 SHALL 调用 `GET /api/v1/records/{id}/scrape-log` 加载最近一次日志，并以 1s 间隔轮询直到 `status` 为终态（`success/failed/interrupted`）。抽屉关闭时 SHALL 立即停止轮询。

抽屉 SHALL 展示以下信息：
- 顶部状态栏：状态徽标（颜色区分 running/success/failed/interrupted）、celery_task_id、起止时间
- 日志文本区域：`log_text` 内容按行渲染，等宽字体，自动滚动到底部
- 失败时高亮显示 `error_msg`

#### Scenario: 打开抽屉查看日志
- **WHEN** 用户点击某 record 的 [查看日志] 按钮
- **THEN** 抽屉 SHALL 从右侧滑入，1 秒内展示该 record 最近一次 scrape_log 的内容

#### Scenario: 日志实时刷新
- **WHEN** 用户打开抽屉时该 record 正在刮削（`status='running'`）
- **THEN** 抽屉 SHALL 每秒轮询一次，更新 `log_text` 内容，直到 `status` 变为终态后停止轮询

#### Scenario: 无日志时的提示
- **WHEN** 用户点击 [查看日志] 按钮，但该 record 无任何 scrape_log 记录（API 返回 404）
- **THEN** 抽屉 SHALL 展示"暂无刮削日志"的空状态提示

#### Scenario: 关闭抽屉停止轮询
- **WHEN** 用户关闭抽屉
- **THEN** 所有进行中的轮询 SHALL 立即取消，不再发送 API 请求

### Requirement: scrape_log 保留策略
系统 SHALL 对 `scrape_log` 表实施双重清理策略：

1. **单 record 上限**: 每条 record SHALL 最多保留 20 条 scrape_log 记录。当插入新记录后该 record 的日志数超过 20 时，SHALL 自动按 `started_at` 升序删除最旧的记录。
2. **全局过期清理**: 30 天前的 scrape_log 记录 SHALL 被定期清理。清理逻辑 SHALL 通过 Celery beat 定时任务执行（每天一次）。

清理 SHALL NOT 影响 `success=True` 的最新一条记录（确保每条 record 至少保留最近一次成功日志）。

#### Scenario: 单 record 超过上限
- **WHEN** 某 record 插入第 21 条 scrape_log
- **THEN** 系统 SHALL 自动删除该 record 最旧的一条 scrape_log，保持总数为 20

#### Scenario: 全局过期清理
- **WHEN** Celery beat 触发每日清理任务，存在 35 天前的 scrape_log 记录
- **THEN** 这些过期记录 SHALL 被删除，但若某 record 仅有这 1 条记录则 SHALL 保留（避免清空）

#### Scenario: 清理不影响最新成功日志
- **WHEN** 某 record 的最新一条 scrape_log 为 `status='success'` 且已超过 30 天
- **THEN** 该条记录 SHALL 被保留，不被过期清理删除
