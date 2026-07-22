# Spec: Single User Mode

## Purpose

明确 Bonita 为单用户系统，禁用开放注册，检测多用户并输出警告。

## Requirements

### R1 · 开放注册默认关闭

`config.py` 中 `USERS_OPEN_REGISTRATION` 的默认值 SHALL 为 `False`。

**行为要求**：
- 环境变量 `USERS_OPEN_REGISTRATION=True` 可覆盖为开启（向后兼容）。
- YAML 配置文件中显式设置也可覆盖。
- 默认部署（无环境变量、无 YAML 配置）下注册端点不可用。

#### Scenario: 默认部署不可注册
- **GIVEN** 全新部署，未设置 `USERS_OPEN_REGISTRATION` 环境变量
- **WHEN** 调用 `POST /api/v1/users/register`
- **THEN** 返回 403 或提示注册未开放

#### Scenario: 环境变量覆盖仍可用
- **GIVEN** 设置 `USERS_OPEN_REGISTRATION=True`
- **WHEN** 调用注册端点
- **THEN** 正常注册（向后兼容）

### R2 · 启动时多用户警告

`main.py` 的 startup 事件 SHALL 检查数据库中用户数量，若 > 1 则输出 `WARNING` 日志。

**行为要求**：
- 查询 `User` 表 `count()`。
- 若 > 1，`logger.warning` 输出提示 Bonita 为单用户系统，多用户数据不隔离。
- 不阻断启动，不删除多余用户。

#### Scenario: 多用户部署启动警告
- **GIVEN** 数据库中存在 3 个用户
- **WHEN** 服务启动
- **THEN** 日志输出 `WARNING: 检测到 3 个用户账户。Bonita 设计为单用户系统...`

#### Scenario: 单用户部署无警告
- **GIVEN** 数据库中仅 1 个 admin 用户
- **WHEN** 服务启动
- **THEN** 无多用户警告

### R3 · API 文档标注单用户设计

`create_user` 端点的 docstring SHALL 包含单用户设计说明。
