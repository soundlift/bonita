## Context

Bonita 当前认证授权体系存在 5 项互相耦合的 P0 缺陷（详见 `openspec/SYSTEM_ISSUES.md` P0-1 至 P0-5）。攻击链：默认弱口令或硬编码 SECRET_KEY → 登录/伪造 JWT → 越权修改刮削配置 → `eval()` 任意代码执行。CORS `["*"]` + `allow_credentials=True` 进一步放大攻击面。

当前代码已有 `get_current_active_superuser` 依赖（`api/deps.py:51-56`），`YamlConfigSettingsSource` 已支持从 `./data/config.yaml` 读取配置，复用空间充分。

约束：SQLite 单文件数据库、无 Redis；已部署实例需平滑升级；前端使用 Bearer Token 无 cookie 需求；开发脚本需保留快速启动能力。

## Goals / Non-Goals

**Goals:**
- 消除 P0-1 至 P0-5 五项缺陷，切断攻击链。
- 已部署实例升级时自动收敛不安全默认配置。
- 变更类 API 端点统一由超级管理员独占。
- 刮削规则渲染消除任意代码执行能力。
- 修正 `get_password_hash` 返回类型。

**Non-Goals:**
- 不重构认证体系（不引入 refresh token、不改为 Redis session）。
- 不修改用户表结构、不引入多租户。
- 不处理 P1 及以下问题。
- 不更换 `python-jose` 为其他 JWT 库。
- 不引入速率限制或登录失败锁定。

## Decisions

### D1 · SECRET_KEY 生成与持久化

**选择**：首次启动检测到默认值 `"secret key"` 时，生成 `secrets.token_urlsafe(32)` 并写入 `./data/config.yaml`，同时记录 WARNING 日志提示已签发 token 将失效。

**备选**：A) 要求环境变量必填，缺失则拒绝启动——破坏 Docker 一键部署。B) 每次启动随机生成——Celery worker 与 uvicorn 进程需共享密钥，不可行。C) 独立 `secret.key` 文件——与 YAML 配置机制重复。

**并发安全**：uvicorn reload + Celery worker 同时启动时用文件锁保护写入；检测到文件已被写入新值则直接读取，不重复生成。

**写入位置**：`Settings` 单例实例化后、`init_db()` 之前，在 `core/config.py` 底部或 `main.py` 启动序列中执行。

### D2 · CORS 默认收紧

**选择**：`BACKEND_CORS_ORIGINS` 默认 `[]`；`allow_credentials` 默认 `False`。

**理由**：Bonita 默认 nginx 同源部署，无需 CORS。跨域部署是例外，应显式配置。

### D3 · 默认管理员密码治理

**选择**：
- `FIRST_SUPERUSER_PASSWORD` 默认值改为 `None`。
- 创建超管时若密码为 `None`，生成 `secrets.token_urlsafe(12)` 打印到启动日志。
- `dev.sh` / `dev.ps1` 仅在 `BONITA_DEV_MODE=true` 时沿用 `changepwd`。
- Dockerfile 不设置该环境变量。

### D4 · 写操作超管校验

**选择**：路由级追加 `dependencies=[Depends(get_current_active_superuser)]`：

| 路由 | 端点 | 当前 | 改后 |
|---|---|---|---|
| `scraping_config.py` | POST `/` | CurrentUser | 超管 |
| `scraping_config.py` | PUT `/{id}` | verify_token | 超管 |
| `scraping_config.py` | DELETE `/{id}` | verify_token | 超管 |
| `task_config.py` | POST `/` | CurrentUser | 超管 |
| `task_config.py` | PUT `/{id}` | verify_token | 超管 |
| `task_config.py` | DELETE `/{id}` | verify_token | 超管 |
| `settings.py` | 所有 POST | verify_token | 超管 |

读取类端点（GET）保持 `verify_token` 不变。

### D5 · 刮削规则模板引擎

**选择**：`str.format_map` + 白名单字典。

```python
def render_rule(rule: str, metadata: schemas.MetadataMixed) -> str:
    safe_keys = {
        'number', 'title', 'actor', 'studio', 'director', 'series',
        'release', 'year', 'genre', 'label', 'tag', 'outline',
        'cover', 'site',
    }
    safe_dict = {k: getattr(metadata, k, '') for k in safe_keys}
    return rule.format_map(_SafeDict(safe_dict))

class _SafeDict(dict):
    def __missing__(self, key):
        return ''
```

**规则迁移**（`scraping_config` 表）：
- `actor+'/'+number+' '+title` → `{actor}/{number} {title}`
- `number+' '+title` → `{number} {title}`
- Alembic 迁移对已知默认值做替换；自定义规则保留原值并记录 WARNING，需用户手动改写。

**风险**：自定义复杂规则（含 `if/else`）无法迁移为 `str.format`，安全性优先于兼容性。

### D6 · get_password_hash 返回类型修正

**选择**：`return hashed_password.decode('utf-8')`，类型注解 `-> str`。

## Risks / Trade-offs

- **已签发 Token 失效**：SECRET_KEY 变更后所有客户端需重新登录。通过日志 WARNING 提示，可接受。
- **自定义刮削规则不兼容**：含逻辑表达式的自定义规则迁移后失效，需用户手动修改。Alembic 迁移脚本对无法识别的规则保留原值并告警，避免静默损坏。
- **并发写 config.yaml**：uvicorn reload 子进程 + Celery worker 同时触发首次写入，需文件锁。失败时日志告警但不阻塞启动（fallback：每次随机，与当前行为一致）。
- **普通用户被降权**：原来能修改配置的普通用户升级后会收到 403。这是预期行为，非回归。
