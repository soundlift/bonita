## Why

系统存在 5 项 P0 级安全缺陷：JWT 签名密钥硬编码为源码常量、默认管理员弱口令公开于 Docker 镜像、CORS 配置允许任意来源携带凭证、变更类 API 端点缺失超级管理员校验、刮削配置的 `location_rule`/`naming_rule` 字段经 `eval()` 执行导致任意代码执行。这些问题构成完整攻击链——攻击者可凭默认口令登录或伪造 JWT，越权修改刮削配置，注入恶意表达式在 Celery worker 内执行任意命令。必须一次性修复以消除中间不安全状态。

## What Changes

- **BREAKING** 移除 `SECRET_KEY` 的硬编码默认值 `"secret key"`。首次启动时生成随机密钥并持久化到 `./data/config.yaml`；已部署实例升级时若检测到默认值则强制生成新密钥并记录告警（已签发 token 失效，用户需重新登录）。
- **BREAKING** 收紧 CORS 默认配置：`BACKEND_CORS_ORIGINS` 默认值由 `["*"]` 改为 `[]`（不允许任何跨域）；`allow_credentials` 由 `True` 改为 `False`（当前使用 Bearer Token，无 cookie 需求）。部署方需通过环境变量或 YAML 显式配置可信来源。
- **BREAKING** 治理默认管理员弱口令：`FIRST_SUPERUSER_PASSWORD` 不再保留 `"changepwd"` 默认值。首次启动时若未通过环境变量/YAML 提供则生成随机密码并打印到启动日志（一次性）；`dev.sh` / `dev.ps1` 开发脚本保留 `changepwd` 但仅在 `BONITA_DEV_MODE` 环境变量为真时生效。
- 为以下路由的变更类端点（POST/PUT/DELETE）追加 `Depends(get_current_active_superuser)` 依赖：
  - `scraping_config`：PUT `/{id}`、DELETE `/{id}`（POST 已有 `CurrentUser` 但未要求超管，一并修正）
  - `task_config`：POST `/`、PUT `/{id}`、DELETE `/{id}`
  - `settings`：所有 POST 端点（proxy/emby/jellyfin/transmission/parse-blacklist 的写入与测试连接）
- **BREAKING** 用受限模板引擎替换 `celery_tasks/tasks.py` 中 `celery_scrapping` 的两处 `eval()` 调用：`location_rule`/`naming_rule` 改用 `str.format_map` + 基于 `MetadataMixed` 字段名的白名单字典；禁止访问以 `_` 开头的属性；不允许任意函数调用。现有默认规则字符串 `actor+'/'+number+' '+title` 需迁移为 `"{actor}/{number} {title}"` 格式。
- 在 `core/security.py` 修正 `get_password_hash` 返回 `str`（当前返回 `bytes`，存入 `String` 列在 SQLite 上侥幸工作，迁移到其他数据库会失败）。

## Capabilities

### New Capabilities

- `secret-management`：运行时敏感密钥（JWT `SECRET_KEY`、首次管理员密码）的生成、持久化与启动期校验。覆盖 `core/config.py`、`core/db.py` 的初始化流程，确保默认值不安全时自动收敛。

### Modified Capabilities

当前 `openspec/specs/` 为空（既有 changes 均未沉淀 spec），本次不创建 delta spec 文件，相关行为要求在 `design.md` 中详述。后续若需沉淀，可将以下能力纳入正式 spec：
- `api-authorization`：API 端点的认证与授权层级要求
- `scraping-rule-rendering`：刮削规则模板的渲染与安全约束
- `cors-policy`：跨域来源与凭证策略

## Impact

- **受影响文件**：`backend/bonita/core/config.py`、`backend/bonita/core/security.py`、`backend/bonita/core/db.py`、`backend/bonita/main.py`、`backend/bonita/api/main.py`、`backend/bonita/api/routes/scraping_config.py`、`backend/bonita/api/routes/task_config.py`、`backend/bonita/api/routes/settings.py`、`backend/bonita/celery_tasks/tasks.py`、`backend/bonita/db/models/scraping.py`（默认规则字符串迁移）、`dev.sh`、`dev.ps1`、`docker/Dockerfile`（环境变量声明）。
- **受影响用户**：所有已部署实例在升级后需重新登录（JWT 密钥变更）；跨域前端部署需显式配置 CORS 来源；开发环境需设置 `BONITA_DEV_MODE=true` 才能沿用 `changepwd`。
- **回滚策略**：若 `SECRET_KEY` 自动生成导致严重问题，可通过预先在 `./data/config.yaml` 写入固定 `SECRET_KEY` 值规避；CORS 与管理员密码可通过环境变量回退。
- **非目标**：不重构认证体系（如改用 Redis 存 session、引入 refresh token）；不修改用户表结构；不处理 P1 及以下问题（见后续批次）。
