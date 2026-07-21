## Context

批次 1 已消除 P0 安全缺陷。本批次聚焦 5 项 P1/P2 问题，分布在日志完整性、任务重试机制、应用生命周期、数据库引擎配置、路径安全校验 5 个领域。

当前代码状态：
- `main.py:51-52`：`init_db()` 和 `init_service()` 在模块顶层执行。
- `decorators.py:50-56`：`except` 块捕获异常后标记失败但不 `raise`，Celery `autoretry_for` 失效。
- `tasks.py:569,661`：`logger.error` 字符串缺少 `f` 前缀。
- `db/__init__.py:9-15`：SQLite engine 使用 `pool_size=5`（无效）+ 共享 broker 文件。
- `file_browser.py`：`directory_path` 无任何校验。

约束：SQLite 单文件数据库（无 Redis）、需平滑升级、前端不受影响。

## Goals / Non-Goals

**Goals:**
- Celery 任务失败时异常信息完整记录到日志。
- Celery `autoretry_for` 机制正常生效（最多 3 次重试）。
- `init_db`/`init_service` 仅在 uvicorn 主进程的 lifespan startup 中执行，不再在模块导入时触发。
- FastAPI 关闭时 watchdog Observer 线程被正确停止。
- SQLite engine 使用正确的 `NullPool` 配置；Celery broker 与业务数据库分离。
- `file_browser` 端点支持可配置的路径白名单校验。

**Non-Goals:**
- 不重构 Celery 任务架构（`group().apply_async().get()` 嵌套问题）。
- 不引入 WebSocket 日志推送替代文件轮询。
- 不修改 `clean_others` 的误删逻辑。
- 不处理 `get_media_items` 排序注入（P1-13）。
- 不引入 Redis broker。

## Decisions

### D1 · f-string 修复

**选择**：直接为两处 `logger.error` 添加 `f` 前缀：
- `tasks.py:569`：`logger.error(f"## [Emby扫描] ✗ 失败: {e}")`
- `tasks.py:661`：`logger.error(f"## [NFO导入] ✗ 失败: {e}")`

**备选**：`logger.error("... 失败: %s", e)` —— 风格不一致，现有代码全部使用 f-string。

### D2 · 装饰器异常传播

**选择**：在 `manage_celery_task` 的 `except` 块末尾添加 `raise`：

```python
except Exception as e:
    error_message = str(e)
    logger.error(f"Task {task_id} failed: {error_message}")
    with CeleryTaskService() as task_service:
        task_service.fail_task(task_id, error_message)
    raise  # ← 让 Celery autoretry 生效
```

**影响**：`fail_task` 仍会标记任务为失败状态；`raise` 后 Celery runtime 捕获异常并根据 `autoretry_for` 决定是否重试。重试时 `manage_celery_task` 会创建新任务记录（因为 `task_id = self.request.id` 在重试时不变，`create_task` 需要幂等处理——检查是否已存在）。

**幂等性保障**：当前 `CeleryTaskService.create_task` 若检测到同 `task_id` 已存在，应更新状态而非创建新记录。需验证此行为。

### D3 · lifespan 迁移

**选择**：使用 FastAPI 的 `@asynccontextmanager` lifespan：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_log_config()
    logger.info(f"Bonita version: {__version__}")
    init_db()
    init_service()
    yield
    # Shutdown
    stop_monitor()

app = FastAPI(..., lifespan=lifespan)
```

**关键变更**：
- `init_log_config()` 也移入 lifespan（它配置 logging，应在所有其他初始化之前）。
- `logger = logging.getLogger(__name__)` 改为 lifespan 内局部变量或模块级但延迟获取。
- `app.celery_app = celery` 保留（Celery worker 需要访问）。

**Celery worker 安全性**：Celery worker 导入 `bonita.main` 时，`create_app()` 仅创建 FastAPI 实例（不含 lifespan 执行），`init_db()` 不再触发。worker 自身通过 `bonita.worker` 模块启动，不依赖 lifespan。

**多 worker 场景**：uvicorn 主进程执行 lifespan startup 完成迁移；子进程（reload）或 Celery worker 启动时数据库已就绪。

### D4 · SQLite engine 与 broker 分离

**选择**：
1. `db/__init__.py` 中为 SQLite 显式指定 `poolclass=NullPool`：
   ```python
   from sqlalchemy.pool import NullPool

   engine = create_engine(
       settings.SQLALCHEMY_DATABASE_URI,
       connect_args={"check_same_thread": False},
       pool_pre_ping=True,
       poolclass=NullPool,
   )
   ```
2. `config.py` 添加 `CELERY_BROKER_DB_LOCATION: str = "./data/celery_broker.sqlite3"`。
3. `worker.py` 中 `CELERY_BROKER_URL` 改为：
   ```python
   CELERY_BROKER_URL = f"sqla+sqlite:///{settings.CELERY_BROKER_DB_LOCATION}"
   ```

**理由**：
- `NullPool` 是 SQLite 的正确池策略——每次请求创建新连接、用完关闭，避免跨线程连接复用问题。
- 分离 broker 后，Celery 队列表的频繁写入不影响业务数据库的读写性能。
- `pool_pre_ping=True` 保留以兼容 `NullPool` 的连接存活检测。

**升级影响**：旧 broker 队列中的待处理任务将丢失。升级前应确保队列为空。

### D5 · file_browser 路径校验

**选择**：
1. `config.py` 添加 `ALLOWED_FILE_ROOTS: list[str] = []`。
2. `file_browser.py` 添加校验函数：
   ```python
   def _is_path_allowed(path: str, allowed_roots: list[str]) -> bool:
       if not allowed_roots:  # 空列表 = 不限制（向后兼容）
           return True
       real_path = os.path.realpath(path)
       return any(
           os.path.commonpath([real_path, root]) == os.path.realpath(root)
           for root in allowed_roots
       )
   ```
3. `list_directory` 端点在路径操作前调用校验，失败返回空结果。

**备选**：仅允许超管访问 `file_browser`——过于严格，普通用户需要浏览自己配置的 source/output 目录。

**路径遍历防御**：`os.path.realpath` 解析符号链接和 `..`，`os.path.commonpath` 确保规范化路径位于允许的根目录下。

## Risks / Trade-offs

- **broker 队列丢失**：升级后旧 broker 任务丢失。通过升级文档提示，可接受（通常升级时队列应为空）。
- **NullPool 性能**：每次请求新建连接有开销，但 SQLite 文件级锁定下连接池本身收益有限。WAL 模式 + `busy_timeout` 已足够。
- **ALLOWED_FILE_ROOTS 配置负担**：用户需额外配置路径白名单。默认 `[]`（不限制）保持向后兼容，仅安全敏感场景需配置。
- **lifespan 中 init_db 失败**：若迁移失败，FastAPI lifespan 启动失败，uvicorn 进程退出。这是正确行为（不应在数据库未就绪时提供服务）。
- **autoretry 幂等性**：`create_task` 需处理重试时同 `task_id` 已存在的情况。若不幂等，重试会在数据库中创建重复记录。
