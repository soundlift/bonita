# Spec: Secret Management and Security Hardening

## Purpose

Harden application security by enforcing secret key rotation, preventing weak passwords, restricting CORS, requiring admin privileges for mutation APIs, and preventing arbitrary code execution in scraping rules.

## ADDED Requirements

### Requirement: SECRET_KEY 不允许使用源码硬编码默认值

系统在启动时必须检测 `SECRET_KEY` 是否为不安全的默认值（`"secret key"`）。若是，必须自动生成符合密码学安全要求的随机密钥（`secrets.token_urlsafe(32)`），持久化到配置文件（`./data/config.yaml`），并在启动日志中记录 WARNING 级别提示，说明已签发的 Token 将失效、用户需重新登录。

#### Scenario: 首次启动（无配置文件）
- **WHEN** `./data/config.yaml` 不存在且环境变量 `SECRET_KEY` 未设置
- **THEN** 生成随机密钥，写入 `config.yaml` 的 `SECRET_KEY` 字段，使用该密钥初始化 JWT 签名，记录 INFO 日志确认密钥已生成

#### Scenario: 已部署实例升级（配置文件存在但 SECRET_KEY 为默认值）
- **WHEN** `config.yaml` 中 `SECRET_KEY` 的值为 `"secret key"`
- **THEN** 生成随机密钥，覆盖 `config.yaml` 中该字段，记录 WARNING 日志说明密钥已轮换、已签发 Token 失效

#### Scenario: 配置文件中 SECRET_KEY 已为安全值
- **WHEN** `config.yaml` 中 `SECRET_KEY` 的值不为 `"secret key"` 且不为空
- **THEN** 直接使用该值，不修改配置文件

#### Scenario: 环境变量 SECRET_KEY 显式设置
- **WHEN** 环境变量 `SECRET_KEY` 已设置（非空、非 `"secret key"`）
- **THEN** 使用环境变量值，不读取/修改配置文件（环境变量优先级高于 YAML，符合现有 `settings_customise_sources` 逻辑）

#### Scenario: 并发启动（uvicorn reload + Celery worker）
- **WHEN** 多个进程同时检测到默认值并尝试写入
- **THEN** 通过文件锁保护写入；先获得锁的进程写入后，后续进程检测到新值直接使用，不重复生成

---

### Requirement: 首次管理员密码不允许使用已知弱口令

`FIRST_SUPERUSER_PASSWORD` 默认值必须为 `None`（无默认）。创建超级管理员时若密码为 `None`，必须自动生成随机密码（`secrets.token_urlsafe(12)`），并在启动日志中以醒目格式打印该一次性密码，提示用户首次登录后立即修改。

#### Scenario: 生产环境首次启动（未设置管理员密码）
- **WHEN** `FIRST_SUPERUSER_PASSWORD` 为 `None` 且数据库中不存在超级管理员
- **THEN** 生成随机密码，用该密码创建超级管理员账户，在启动日志中打印：`[BONITA] 临时管理员密码: <password>，请首次登录后立即修改`

#### Scenario: 开发环境（BONITA_DEV_MODE=true）
- **WHEN** 环境变量 `BONITA_DEV_MODE` 为 `true`
- **THEN** 允许使用 `changepwd` 等弱口令（开发脚本显式传入 `FIRST_SUPERUSER_PASSWORD=changepwd`）

#### Scenario: 已部署实例升级（数据库中已存在超级管理员）
- **WHEN** 数据库中已存在超级管理员记录
- **THEN** 不修改密码，不打印密码日志

---

### Requirement: CORS 默认不允许任意来源

`BACKEND_CORS_ORIGINS` 默认值必须为 `[]`（空列表）。`allow_credentials` 默认值必须为 `False`。部署方需通过环境变量或 YAML 配置显式指定可信来源。

#### Scenario: 默认部署（未配置 CORS 来源）
- **WHEN** `BACKEND_CORS_ORIGINS` 未通过环境变量或 YAML 设置
- **THEN** CORS 中间件不允许任何跨域请求；浏览器跨域请求收到无 `Access-Control-Allow-Origin` 头的响应

#### Scenario: 显式配置可信来源
- **WHEN** 部署方通过环境变量设置 `BACKEND_CORS_ORIGINS='["https://app.example.com"]'`
- **THEN** 仅允许 `https://app.example.com` 的跨域请求

#### Scenario: allow_credentials 保持 False
- **WHEN** 未显式设置 `allow_credentials`
- **THEN** 响应中不包含 `Access-Control-Allow-Credentials: true` 头

---

### Requirement: 变更类 API 端点需超级管理员权限

所有修改系统配置的 API 端点（POST/PUT/DELETE）必须要求调用者为超级管理员（`is_superuser=True`）。读取类端点（GET）保持要求已认证用户（`verify_token`）即可。

#### Scenario: 超级管理员调用变更端点
- **WHEN** 超级管理员调用 `PUT /api/v1/scraping/config/1` 并携带合法 JWT
- **THEN** 请求正常处理，返回 200

#### Scenario: 普通用户调用变更端点
- **WHEN** 普通用户（`is_superuser=False`）调用 `PUT /api/v1/scraping/config/1` 并携带合法 JWT
- **THEN** 返回 HTTP 403，`detail="The user doesn't have enough privileges"`

#### Scenario: 普通用户读取配置
- **WHEN** 普通用户调用 `GET /api/v1/scraping/config/all`
- **THEN** 请求正常处理，返回配置列表

#### 受影响端点完整清单
- `scraping_config.py`：POST `/`、PUT `/{id}`、DELETE `/{id}`
- `task_config.py`：POST `/`、PUT `/{id}`、DELETE `/{id}`
- `settings.py`：POST `/proxy`、POST `/emby`、POST `/emby/test`、POST `/jellyfin`、POST `/jellyfin/test`、POST `/transmission`、POST `/transmission/test`、POST `/parse-blacklist`、POST `/parse-blacklist/preview`

---

### Requirement: 刮削规则不允许任意代码执行

`location_rule` 和 `naming_rule` 字段必须使用受限模板引擎渲染，禁止使用 `eval()`。模板引擎仅支持对白名单元数据字段的字符串插值，不允许属性链访问、函数调用或逻辑表达式。

#### Scenario: 使用标准格式模板
- **WHEN** `location_rule` 值为 `{actor}/{number} {title}` 且元数据 `actor="ABC"`、`number="123"`、`title="Test"`
- **THEN** 渲染结果为 `ABC/123 Test`

#### Scenario: 模板引用不存在的字段
- **WHEN** `location_rule` 值为 `{actor}/{nonexistent}` 且字段 `nonexistent` 不在白名单中
- **THEN** 渲染结果中 `{nonexistent}` 替换为空字符串，不抛异常

#### Scenario: 模板包含 Python 代码（注入尝试）
- **WHEN** `location_rule` 值为 `{__import__('os').system('rm -rf /')}`
- **THEN** `str.format_map` 将整个字符串视为普通模板，`__import__('os').system('rm -rf /')` 作为键名查找，不在白名单中，替换为空字符串，不执行任何代码

#### Scenario: 自定义规则包含逻辑表达式（旧格式）
- **WHEN** `location_rule` 值为 `actor+'/'+number+' '+title if len(actor)<10 else '多人作品'`（旧 Python 表达式格式）
- **THEN** `str.format_map` 无法解析该格式，渲染结果为原始字符串（不抛异常，不执行代码）。Alembic 迁移脚本对已知默认值做自动替换，自定义规则需用户手动改写为 `{actor}/{number} {title}` 格式
