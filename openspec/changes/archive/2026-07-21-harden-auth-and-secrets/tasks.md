## 1. SECRET_KEY 安全化

- [x] 1.1 修改 `backend/bonita/core/config.py`：`SECRET_KEY` 默认值改为 `None`（`Optional[str]`），`FIRST_SUPERUSER_PASSWORD` 默认值改为 `None`
- [x] 1.2 在 `backend/bonita/core/config.py` 底部（`settings = Settings()` 之后）添加启动期密钥校验逻辑：检测 `SECRET_KEY` 是否为 `None` 或 `"secret key"`，若是则生成随机密钥并写回 `./data/config.yaml`，用文件锁保护并发写入，记录 WARNING 日志
- [x] 1.3 修改 `backend/bonita/core/db.py` 的 `init_super_user()`：当 `FIRST_SUPERUSER_PASSWORD` 为 `None` 时生成随机密码，打印醒目日志提示一次性密码；非 `None` 时沿用原逻辑
- [x] 1.4 修改 `dev.sh` / `dev.ps1`：启动后端和 Celery 进程时显式传入 `FIRST_SUPERUSER_PASSWORD=changepwd` 环境变量（仅当 `BONITA_DEV_MODE` 未设置或为 true 时）
- [x] 1.5 验证：启动后检查 `./data/config.yaml` 中 `SECRET_KEY` 已为随机值；重启后不再重新生成；Celery worker 启动时读取同一密钥

## 2. CORS 默认收紧

- [x] 2.1 修改 `backend/bonita/core/config.py`：`BACKEND_CORS_ORIGINS` 默认值改为 `[]`
- [x] 2.2 修改 `backend/bonita/main.py`：`allow_credentials` 参数改为 `False`
- [x] 2.3 验证：默认部署时跨域请求被拒绝；显式配置 `BACKEND_CORS_ORIGINS='["http://localhost:3000"]'` 后跨域请求正常

## 3. 写操作超管校验

- [x] 3.1 修改 `backend/bonita/api/routes/scraping_config.py`：POST `/`、PUT `/{id}`、DELETE `/{id}` 统一追加 `dependencies=[Depends(get_current_active_superuser)]`（路由级），移除参数级 `CurrentUser` 依赖（路由级已覆盖）
- [x] 3.2 修改 `backend/bonita/api/routes/task_config.py`：同上，POST `/`、PUT `/{id}`、DELETE `/{id}` 追加超管依赖
- [x] 3.3 修改 `backend/bonita/api/routes/settings.py`：所有 POST 端点（proxy/emby/jellyfin/transmission 写入与 test、parse-blacklist 写入与 preview）追加超管依赖
- [x] 3.4 验证：普通用户调用上述端点返回 403；超级管理员调用正常

## 4. 刮削规则模板引擎替换

- [x] 4.1 在 `backend/bonita/utils/` 下新建 `rule_renderer.py`：实现 `render_rule(rule, metadata)` 函数、`_SafeDict` 类、`SAFE_METADATA_KEYS` 白名单
- [x] 4.2 修改 `backend/bonita/celery_tasks/tasks.py:483-487`：将两处 `eval()` 替换为 `render_rule()`，同时保留 `len(metadata_mixed.actor) > maxlen` 等字段长度判断为独立 Python 逻辑
- [x] 4.3 修改 `backend/bonita/db/models/scraping.py`：`location_rule` 默认值改为 `"{actor}/{number} {title}"`，`naming_rule` 默认值改为 `"{number} {title}"`
- [x] 4.4 创建 Alembic 迁移脚本：对 `scraping_config` 表的 `location_rule`/`naming_rule` 字段做默认值迁移（匹配 `actor+'/'+number+' '+title` 替换为 `{actor}/{number} {title}`；匹配 `number+' '+title` 替换为 `{number} {title}`；其余保留原值）
- [x] 4.5 验证：新建刮削配置使用新格式默认值；已有配置的默认规则被自动迁移；手动输入 `{actor}/{number} {title}` 渲染正确；输入 `__import__('os').system('ls')` 不执行代码

## 5. get_password_hash 返回类型修正

- [x] 5.1 修改 `backend/bonita/core/security.py`：`get_password_hash` 返回 `hashed_password.decode('utf-8')`，类型注解 `-> str`；`verify_password` 参数 `hashed_password` 注解改为 `str`
- [x] 5.2 验证：登录/修改密码流程正常；新建用户密码哈希为字符串

## 6. 端到端验证

- [x] 6.1 完整登录流程：用新生成的随机密码登录 → 修改密码 → 重新登录
- [x] 6.2 越权测试：普通用户调用 `PUT /api/v1/scraping/config/1` 返回 403
- [x] 6.3 RCE 消除：通过 API 将 `location_rule` 设为恶意 Python 代码，触发刮削任务，确认不执行
- [x] 6.4 CORS 测试：默认部署时前端跨域请求被拒绝；配置后正常
- [x] 6.5 升级兼容：用旧数据库（含默认 SECRET_KEY 和旧规则格式）启动，确认自动收敛
