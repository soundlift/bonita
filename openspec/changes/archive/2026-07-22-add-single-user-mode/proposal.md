## Why

P2-16 指出 `WatchHistory` 无 `user_id`，多用户数据混存。产品定位决定 Bonita 为单用户系统，无需改造数据模型。但当前代码允许开启多用户注册（`USERS_OPEN_REGISTRATION=True`），导致用户可能误以为支持多用户隔离。

## What Changes

- **默认关闭开放注册**：`USERS_OPEN_REGISTRATION` 默认值改为 `False`，防止误开启。
- **启动时警告**：若数据库中存在多个用户，启动日志输出警告，提示 Bonita 为单用户系统。
- **API 文档标注**：`create_user` 端点添加说明，标注 Bonita 为单用户设计。

## Capabilities

### New Capabilities

- `single-user-mode`：单用户系统定位，禁用开放注册，多用户警告。

## Impact

- **向后兼容**：已开启 `USERS_OPEN_REGISTRATION=True` 的用户不受影响（环境变量覆盖默认值）。但建议关闭。
- **非目标**：不修改 `WatchHistory` 数据模型，不添加 `user_id`。不修改 P1-8、P1-10。
