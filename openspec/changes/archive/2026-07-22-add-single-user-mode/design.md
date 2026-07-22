## Context

Bonita 是个人媒体管理工具，设计为单用户系统。`WatchHistory`、评分、收藏等数据无 `user_id` 隔离。当前代码支持多用户注册（`USERS_OPEN_REGISTRATION`），但多用户场景下数据混存，体验不佳。

## Goals / Non-Goals

**Goals:**
- 明确单用户定位，防止误开启多用户注册。
- 启动时检测多用户并输出警告。
- 保持现有 admin 账户功能不变。

**Non-Goals:**
- 不改造 `WatchHistory` 添加 `user_id`。
- 不删除多用户注册代码（向后兼容）。
- 不强制删除多余用户。

## Decisions

### D1 · `USERS_OPEN_REGISTRATION` 默认关闭

```python
# Before:
USERS_OPEN_REGISTRATION: bool = True

# After:
USERS_OPEN_REGISTRATION: bool = False
```

**理由**：默认关闭防止误开启。已通过环境变量开启的用户不受影响。

### D2 · 启动时多用户警告

在 `main.py` 的 startup 事件中，查询 `User` 表记录数。若 > 1，输出 `WARNING` 日志。

```python
if user_count > 1:
    logger.warning(f"检测到 {user_count} 个用户账户。Bonita 设计为单用户系统，多用户场景下观看历史、收藏、评分等数据不隔离。")
```

**理由**：警告不阻断，仅提示。用户可自行决定是否清理多余账户。

### D3 · API 文档标注

`create_user` 端点的 docstring 添加说明：`"""创建用户。注意：Bonita 为单用户设计，多用户场景下数据不隔离。"""`

## Risks / Trade-offs

- **默认关闭注册**：新部署的用户需要通过 admin 账户创建其他用户，或通过环境变量开启注册。影响极小。
- **不强制删除多余用户**：已有多个用户的部署不会被阻断，仅收到警告。这是有意为之——不破坏现有部署。
