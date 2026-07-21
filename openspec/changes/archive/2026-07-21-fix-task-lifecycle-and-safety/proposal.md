## Why

批次 1（harden-auth-and-secrets）消除了 P0 攻击链，但系统仍有 5 项 P1/P2 问题直接影响正确性和可用性：

1. **日志异常信息丢失**（P1-9）：`celery_emby_scan` 和 `celery_import_nfo` 的 `logger.error` 缺少 `f` 前缀，异常详情被吞掉，线上排查无法定位根因。
2. **Celery 重试机制失效**（P2-19）：`manage_celery_task` 装饰器捕获异常后未 `raise`，Celery 的 `autoretry_for=(Exception,)` 永远不触发，任务失败即终态。
3. **启动期阻塞与无清理**（P1-6）：`init_db()` 和 `init_service()` 在模块顶层执行，任何导入 `bonita.main` 的进程（Celery worker、测试、alembic CLI）都会触发迁移和 watchdog 线程启动；FastAPI 关闭时 watchdog Observer 从未停止。
4. **SQLite 连接池参数无效**（P1-7）：`pool_size=5`、`max_overflow=10` 对 SQLite 默认 `NullPool` 无意义；Celery broker 与业务数据共用同一 SQLite 文件，高并发下触发 `database is locked`。
5. **file_browser 路径无校验**（P1-11）：`directory_path` 参数无任何根目录限制，任何登录用户可遍历宿主机全盘文件系统。

## What Changes

- **P1-9**：修改 `celery_tasks/tasks.py` 第 569 行和第 661 行，为 `logger.error` 字符串添加 `f` 前缀，确保 `{str(e)}` 被正确插值。
- **P2-19**：修改 `celery_tasks/decorators.py` 第 50-56 行 `except` 块，在 `fail_task` 之后添加 `raise`，让异常传播到 Celery runtime 以触发自动重试。
- **P1-6**：
  - 将 `main.py` 中的 `init_db()` 和 `init_service()` 移入 FastAPI `lifespan` 上下文管理器的 startup 阶段。
  - 在 lifespan 的 shutdown 阶段调用 `stop_monitor()` 停止 watchdog Observer 线程。
  - 确保 `app = create_app()` 仍可被 Celery worker 安全导入（不触发迁移）。
- **P1-7**：
  - 为 SQLite engine 显式指定 `poolclass=NullPool`，移除无效的 `pool_size`/`max_overflow` 参数。
  - 在 `config.py` 中添加 `CELERY_BROKER_DB_LOCATION` 配置项，默认值为 `./data/celery_broker.sqlite3`（与业务数据库分离）。
  - 更新 `worker.py` 中 `CELERY_BROKER_URL` 使用新的独立 broker 路径。
- **P1-11**：
  - 在 `config.py` 中添加 `ALLOWED_FILE_ROOTS: list[str]` 配置项（默认 `[]`，表示不限制）。
  - 在 `file_browser.py` 的 `list_directory` 端点中添加路径校验：`os.path.realpath(directory_path)` 必须位于 `ALLOWED_FILE_ROOTS` 之一的子树下；空列表表示不限制（向后兼容）。
  - 路径遍历攻击（`../../etc/passwd`）通过 `realpath` 规范化后校验。

## Capabilities

### New Capabilities

- `task-lifecycle`：Celery 任务的异常传播与自动重试机制完整性。覆盖 `celery_tasks/decorators.py` 的异常处理流程。
- `file-path-validation`：`file_browser` 端点的路径安全校验。覆盖 `api/routes/file_browser.py` 的目录浏览逻辑。

### Modified Capabilities

- `app-lifecycle`：FastAPI 应用的 startup/shutdown 生命周期管理。从模块顶层执行迁移到 `lifespan` 上下文管理器。
- `database-engine`：SQLAlchemy 引擎配置。SQLite 显式 `NullPool` + broker 数据库分离。
- `logging-diagnostics`：Celery 任务异常日志的完整性。

## Impact

- **受影响文件**：`backend/bonita/main.py`、`backend/bonita/celery_tasks/tasks.py`、`backend/bonita/celery_tasks/decorators.py`、`backend/bonita/db/__init__.py`、`backend/bonita/core/config.py`、`backend/bonita/worker.py`、`backend/bonita/api/routes/file_browser.py`。
- **BREAKING**：Celery broker 数据库路径变更。升级后首次启动会在 `./data/` 下创建 `celery_broker.sqlite3`，旧 broker 队列中的待处理任务将丢失。建议升级前确保 Celery 队列为空。
- **BREAKING**：`file_browser` 端点在配置了 `ALLOWED_FILE_ROOTS` 后，超出范围的路径请求将返回空结果（而非全盘遍历）。未配置时行为不变。
- **向后兼容**：`init_db()` 从模块顶层移除后，Celery worker 导入 `bonita.main` 不再触发迁移——由 lifespan 在 uvicorn 主进程中统一执行。多 worker 场景需确保主进程先完成迁移。
- **非目标**：不重构 Celery 任务架构（如将 `group().apply_async().get()` 改为 `chord`）——属于批次 3 范围。
