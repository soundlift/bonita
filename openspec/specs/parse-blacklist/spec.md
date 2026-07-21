# Spec: Parse Blacklist

## Purpose

Allow users to define filename cleaning rules (blacklist) that are applied before number parsing, with support for literal and regex modes, plus a preview API for testing rules.

## ADDED Requirements

### Requirement: 后端 SHALL 存储和提供番号解析黑名单

`SystemSetting` 表 SHALL 使用 key `parse_blacklist` 存储黑名单，值为 JSON 字符串，结构为 `[{"id": str, "mode": "literal"|"regex", "value": str, "enabled": bool}]`。

`GET /api/v1/settings/parse-blacklist` 端点 SHALL 返回当前黑名单列表。如果未配置，SHALL 返回空列表。

`POST /api/v1/settings/parse-blacklist` 端点 SHALL 接收完整的黑名单列表并覆盖保存。

#### Scenario: 获取空黑名单

- **WHEN** 客户端调用 `GET /api/v1/settings/parse-blacklist` 且未配置过黑名单
- **THEN** SHALL 返回 `{ "data": [], "success": true }`

#### Scenario: 保存并获取黑名单

- **WHEN** 客户端调用 `POST /api/v1/settings/parse-blacklist`，body 为 `[{ "id": "1", "mode": "literal", "value": "hhd800.com", "enabled": true }]`
- **THEN** 后端 SHALL 将其序列化为 JSON 存入 `SystemSetting`，随后 `GET` 请求 SHALL 返回该列表

### Requirement: 番号解析 SHALL 在规则匹配前应用黑名单清理

`number_parser.py` 的 `get_number()` 函数 SHALL 在调用 `rules_parser(filename)` 之前，依次执行以下清理：
1. 应用内置 `G_spat` 正则清理（网站前缀、画质标记等）
2. 从数据库读取 `parse_blacklist`，对每条 `enabled=true` 的规则：`literal` 模式用 `filename.replace(value, "")`，`regex` 模式用 `re.sub(value, "", filename)`（编译失败的正则 SHALL 被跳过并记录日志，不中断解析）

清理后的 filename SHALL 传递给 `rules_parser()` 进行番号提取。

#### Scenario: 黑名单清理后正确解析

- **WHEN** 文件名为 `hhd800.com@MKMP-725.mp4`，黑名单包含 `{ "mode": "literal", "value": "hhd800.com" }`
- **THEN** 清理后 filename 变为 `@MKMP-725`，`rules_parser` SHALL 返回 `MKMP-725`

#### Scenario: 无黑名单时 G_spat 前置修复

- **WHEN** 文件名为 `hhd800.com@MKMP-725.mp4`，黑名单为空
- **THEN** `G_spat` 前置执行，清理掉 `hhd800.com@`，filename 变为 `MKMP-725`，`rules_parser` SHALL 返回 `MKMP-725`

#### Scenario: 正则模式黑名单清理

- **WHEN** 文件名为 `xxx.net@ABC-123.mp4`，黑名单包含 `{ "mode": "regex", "value": "^\\w+\\.(com|net|org)@" }`
- **THEN** 正则替换后 filename 变为 `ABC-123`，`rules_parser` SHALL 返回 `ABC-123`

#### Scenario: 无效正则被跳过

- **WHEN** 黑名单包含一条 `mode=regex` 但 `value` 为无效正则（如 `[invalid`）
- **THEN** 该条规则 SHALL 被跳过（`re.compile` 失败时捕获异常并记录日志），不影响其他规则和整体解析流程

#### Scenario: 已禁用的规则不生效

- **WHEN** 黑名单包含一条 `enabled=false` 的规则
- **THEN** 该条规则 SHALL 不被应用，filename 不受影响

### Requirement: 后端 SHALL 提供解析预览 API

`POST /api/v1/settings/parse-blacklist/preview` 端点 SHALL 接收 `{ "filename": str, "blacklist": [...] }`，使用传入的黑名单（而非数据库中的）对 filename 执行清理和解析，返回 `{ "cleaned_filename": str, "parsed_number": str|null }`。

#### Scenario: 预览清理和解析结果

- **WHEN** 客户端调用 preview，`filename = "hhd800.com@MKMP-725.mp4"`，`blacklist = [{ "mode": "literal", "value": "hhd800.com", "enabled": true }]`
- **THEN** SHALL 返回 `{ "cleaned_filename": "@MKMP-725", "parsed_number": "MKMP-725" }`
