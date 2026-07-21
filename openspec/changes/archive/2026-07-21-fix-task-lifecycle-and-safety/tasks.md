## 1. 日志 f-string 修复（P1-9）

- [x] 1.1 修改 `backend/bonita/celery_tasks/tasks.py` 第 569 行：`logger.error("## [Emby扫描] ✗ 失败: {str(e)}")` → `logger.error(f"## [Emby扫描] ✗ 失败: {e}")`
- [x] 1.2 修改 `backend/bonita/celery_tasks/tasks.py` 第 661 行：`logger.error("## [NFO导入] ✗ 失败: {str(e)}")` → `logger.error(f"## [NFO导入] ✗ 失败: {e}")`
- [x] 1.3 验证：语法检查通过

## 2. Celery 装饰器异常传播（P2-19）

- [x] 2.1 修改 `backend/bonita/celery_tasks/decorators.py` 第 56 行后添加 `raise`：在 `fail_task` 调用之后、`except` 块末尾添加 `raise` 语句
- [x] 2.2 验证 `CeleryTaskService.create_task` 对同 `task_id` 的幂等性：`create_task` 已改为先查询再创建，重试时重置状态而非重复插入
- [x] 2.3 验证：语法检查通过；`raise` 让异常传播到 Celery runtime

## 3. lifespan 迁移（P1-6）

- [x] 3.1 修改 `backend/bonita/main.py`：`init_log_config()`、`init_db()`、`init_service()` 已移入 `@asynccontextmanager` 的 `lifespan` 函数
- [x] 3.2 在 lifespan shutdown 阶段调用 `stop_monitor()` 停止 watchdog Observer
- [x] 3.3 `create_app()` 使用 `FastAPI(..., lifespan=lifespan)` 参数
- [x] 3.4 `app.celery_app = celery` 仍在模块顶层赋值
- [x] 3.5 验证：语法检查通过；模块导入不再触发 `init_db()`

## 4. SQLite engine 配置（P1-7）

- [x] 4.1 `backend/bonita/db/__init__.py`：`poolclass=NullPool`，移除 `pool_size=5` 和 `max_overflow=10`
- [x] 4.2 `backend/bonita/core/config.py`：添加 `CELERY_BROKER_DB_LOCATION: str = "./data/celery_broker.sqlite3"`
- [x] 4.3 `backend/bonita/worker.py`：`CELERY_BROKER_URL` 已通过 `settings.CELERY_BROKER_URL` 自动使用新路径
- [x] 4.4 验证：语法检查通过

## 5. file_browser 路径校验（P1-11）

- [x] 5.1 `backend/bonita/core/config.py`：添加 `ALLOWED_FILE_ROOTS: list[str] = []`
- [x] 5.2 `backend/bonita/api/routes/file_browser.py`：添加 `_is_path_allowed()` 校验函数；`list_directory` 在路径操作前调用校验
- [x] 5.3 验证：语法检查通过；路径校验逻辑测试全部通过

## 6. 端到端验证

- [x] 6.1 所有修改文件语法检查通过（7 个文件）
- [x] 6.2 `init_db` 不在模块导入时执行（已移入 lifespan）
- [x] 6.3 `manage_celery_task` 装饰器在异常时正确传播（`raise` 生效）
- [x] 6.4 `file_browser` 路径校验在配置 `ALLOWED_FILE_ROOTS` 后生效
