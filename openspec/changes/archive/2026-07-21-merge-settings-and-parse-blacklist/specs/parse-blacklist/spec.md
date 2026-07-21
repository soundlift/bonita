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

### Requirement: 前端 SHALL 提供统一的标签页式设置页面

新建 `Settings.vue` 页面 SHALL 使用 `VTabs` + `VWindow` 组织三个标签页："安全"、"服务"、"番号解析"。标签页内容分别为：
- 安全：引用现有 `AccountSettingsSecurity.vue` 组件
- 服务：引用从 `ServiceSettings.vue` 提取的内容（新子组件 `ServiceSettingsPanel.vue`）
- 番号解析：新增的黑名单管理界面

路由 `/settings` SHALL 指向此页面，通过 `?tab=security|service|parse` query param 控制激活的 tab。原有 `/settings/user` 和 `/settings/service` SHALL 重定向到对应 tab。

导航栏 SHALL 将两个设置入口合并为一个"设置"入口指向 `/settings`。

#### Scenario: 从导航栏进入设置

- **WHEN** 用户点击导航栏的"设置"入口
- **THEN** SHALL 导航到 `/settings`，默认显示"安全"标签页

#### Scenario: 切换标签页

- **WHEN** 用户点击"服务"标签
- **THEN** SHALL 显示服务连接设置内容，URL 更新为 `/settings?tab=service`

#### Scenario: 旧链接兼容

- **WHEN** 用户访问 `/settings/service`（旧链接）
- **THEN** SHALL 重定向到 `/settings?tab=service`

### Requirement: 前端 SHALL 提供番号解析黑名单管理界面

"番号解析"标签页 SHALL 包含：
- 黑名单规则列表（表格或列表形式），每条显示模式类型、值、启用状态
- 新增规则按钮：弹出行内表单或对话框，输入值并选择模式（精确匹配/正则表达式）
- 每条规则可编辑值、切换模式、启用/禁用、删除
- 保存按钮：将完整列表提交到后端 `POST /api/v1/settings/parse-blacklist`
- 说明文字区域：解释黑名单的作用范围（仅在解析番号时过滤，不修改原始文件名）、两种模式的区别、注意事项
- 实时预览区域：输入测试文件名，点击预览按钮，显示清理后的文件名和解析出的番号

#### Scenario: 新增黑名单规则

- **WHEN** 用户点击"新增规则"，输入值 `hhd800.com`，选择模式"精确匹配"，确认
- **THEN** 规则列表 SHALL 新增一行，用户点击"保存"后该规则被持久化

#### Scenario: 实时预览解析结果

- **WHEN** 用户在预览输入框输入 `hhd800.com@MKMP-725.mp4`，点击"预览"
- **THEN** SHALL 调用预览 API，显示"清理后: @MKMP-725"和"解析结果: MKMP-725"

#### Scenario: 切换规则启用状态

- **WHEN** 用户将某条规则的启用开关关闭
- **THEN** 该规则在列表中显示为禁用状态，保存后解析时该规则不被应用
