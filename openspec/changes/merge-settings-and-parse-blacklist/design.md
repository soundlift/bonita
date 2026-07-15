## Context

### 设置页面现状

项目有两个独立设置页面：
- `UserSettings.vue`（`/settings/user`）——只有"安全"标签页，内容为 `AccountSettingsSecurity.vue` 组件，用 `VTabs`/`VWindow` 组织但只有一个 tab
- `ServiceSettings.vue`（`/settings/service`）——纯卡片堆叠（无 tab），包含代理、Emby、Jellyfin、Transmission 四个 `VCard` 区块

导航栏 `NavItems.vue` 有两个独立入口指向这两个页面。用户经常需要在两个页面间切换，体验断裂。

### 番号解析现状

`number_parser.py` 的 `get_number()` 函数中，`rules_parser(filename)`（第 156 行）是最先执行的解析逻辑，它遍历 12 条正则规则，first-match-wins。问题是文件名中的网站域名（如 `hhd800.com@MKMP-725.mp4` 中的 `HHD800`）会被通用规则 `RE_RULE_GENERAL`（`[A-Za-z]{2,6}\-?\d{3,4}`）匹配，返回错误结果 `HHD-800`。

代码中已有 `G_spat` 正则（第 5-9 行）用于清理网站前缀，但它只在 `get_number()` 的第 165 和 171 行（"字幕组"和"含 - 或 _"分支）被调用，远在 `rules_parser()` 之后。只要 `rules_parser` 匹配成功就直接返回，`G_spat` 永远没有执行机会。

### 设置基础设施

项目已有完善的 key-value 设置系统：`SystemSetting` 模型 + `SettingService` + `/api/v1/settings/` 路由。代理、Emby、Jellyfin、Transmission 都用这套模式。新增黑名单设置完全复用这个模式。

## Goals / Non-Goals

**Goals:**

- 用户在一个统一的设置页面中通过标签页切换所有设置（安全、服务、番号解析）
- 番号解析黑名单同时支持精确字符串匹配和正则表达式模式
- 黑名单清理在解析流程的最前面执行，确保 `rules_parser` 收到的是已清理的文件名
- 内置的 `G_spat` 清理也前置到 `rules_parser` 之前，修复已有 bug
- 提供实时预览功能，用户输入测试文件名即可看到清理和解析结果

**Non-Goals:**

- 不自动修复已有的错误解析数据（用户可手动重试）
- 不做黑名单的导入/导出
- 不修改 `G_spat` 正则本身的内容（只是改变它的执行时机）
- 不修改 `rules_parser` 内部的规则顺序或匹配逻辑

## Decisions

### 决策 1：合并方式——新建 `Settings.vue`，ServiceSettings 内容提取为子组件

**选择**: 新建 `frontend/src/pages/Settings.vue`，包含 `VTabs`（安全 | 服务 | 番号解析）。`AccountSettingsSecurity.vue` 保持不变直接引用。`ServiceSettings.vue` 的 `<script>` 和 `<template>` 内容提取为新的子组件 `views/settings/ServiceSettingsPanel.vue`，在 Settings.vue 的"服务"tab 中引用。原 `ServiceSettings.vue` 和 `UserSettings.vue` 可保留为重定向或删除。

**理由**: `ServiceSettings.vue` 目前有 514 行，直接内联到 Settings.vue 会让文件过大。提取为子组件保持每个 tab 的独立性，也符合 `UserSettings.vue` 已有的模式（安全 tab 引用 `AccountSettingsSecurity.vue` 子组件）。

**备选方案**: 将 ServiceSettings.vue 全部内容内联到 Settings.vue——文件过长（会超过 700 行），维护困难，放弃。

### 决策 2：路由策略——单一路由 + query param 切 tab

**选择**: 路由 `/settings` 指向新的 `Settings.vue`，通过 `?tab=security|service|parse` query param 控制激活的 tab。原有 `/settings/user` 和 `/settings/service` 重定向到 `/settings?tab=security` 和 `/settings?tab=service`，保持书签/链接兼容。

**理由**: 单一路由 + query param 是多 tab 页面的常见模式，用户可以收藏特定 tab 的 URL。重定向保证旧链接不会 404。

**备选方案**: `/settings/security`、`/settings/service`、`/settings/parse` 子路由——更 RESTful 但需要更多路由配置，且 tab 间切换会产生历史记录。query param 方式更轻量。

### 决策 3：导航栏合并为一个"设置"入口

**选择**: `NavItems.vue` 中将"服务设置"和"用户设置"两个入口合并为一个"设置"入口，指向 `/settings`（默认显示"安全"tab 或上次访问的 tab）。

**理由**: 减少导航项数量，用户从一处入口进入后通过 tab 切换所有设置，体验更连贯。

### 决策 4：黑名单数据结构

**选择**: `SystemSetting` 中 key 为 `parse_blacklist`，value 为 JSON 字符串：

```json
[
  {"id": "uuid-or-timestamp", "mode": "literal", "value": "hhd800.com", "enabled": true},
  {"id": "...", "mode": "regex", "value": "^\\w+\\.(com|net)@", "enabled": true}
]
```

- `mode`: `"literal"`（精确字符串，用 `str.replace(value, "")` 删除所有出现）或 `"regex"`（正则表达式，用 `re.sub(value, "", filename)` 替换）
- `enabled`: `false` 时不应用该条规则（方便临时禁用）
- `id`: 用于前端的增删改标识（生成方式用 `Date.now().toString()` 或 uuid）

**理由**: JSON 数组结构清晰，支持多种模式和启用/禁用。存储为 `SystemSetting.value` 字符串，复用现有 key-value 模式，不需要新建数据库表或 migration。

### 决策 5：黑名单清理 + G_spat 前置到 rules_parser 之前

**选择**: 在 `get_number()` 函数中，第 155-156 行之间（`(filename, ext) = os.path.splitext(basename)` 之后、`file_number = rules_parser(filename)` 之前）插入：
1. `G_spat.sub("", filename)` 清理内置模式（网站前缀、画质标记等）
2. 读取黑名单，逐条应用清理（literal 用 replace，regex 用 sub）
3. 然后再调用 `rules_parser(filename)` 解析

**理由**: 这是治本方案。清理必须在规则匹配之前，否则错误结果已经被返回了。

**备选方案**: 只做用户黑名单前置，不动 `G_spat`——但 `G_spat` 中已有的一批域名后缀清理就没用了（因为执行太晚），浪费了已有逻辑。同时前置两者最合理。

### 决策 6：实时预览功能

**选择**: "番号解析" tab 底部提供一个测试输入框和结果显示区。用户输入文件名（如 `hhd800.com@MKMP-725.mp4`），前端实时显示：① 每条黑名单规则的匹配/清理过程 ② 最终解析结果。预览功能调用后端 API（`POST /api/v1/settings/parse-blacklist/preview`），因为解析逻辑在后端。

**理由**: 解析逻辑（`FileNumInfo` / `get_number`）在后端 Python，前端无法独立复现。预览必须调用后端。

## Risks / Trade-offs

- **[页面重构的回归风险]** 合并设置页面会移动现有代码，可能引入回归。缓解：提取 ServiceSettings 为独立子组件，尽量保持内部逻辑不变；保留旧路由重定向。
- **[黑名单性能]** 每次解析番号都要读取数据库黑名单。缓解：可以在 `number_parser.py` 中缓存黑名单（类似 `G_cache_uncensored_conf` 的模式），通过一个全局缓存变量 + TTL 或手动刷新机制。首版可以先不缓存（番号解析不是高频操作），后续按需优化。
- **[正则表达式安全]** 用户输入的正则可能有灾难性回溯（ReDoS）风险。缓解：用 `re.compile` 包裹 `try/except`，编译失败或超时的正则跳过并记录。可以加 `re.sub` 的超时保护（但 Python `re` 模块本身不支持超时，需用 `regex` 第三方库或信号机制——首版可以不处理，低风险）。
- **[G_spat 前置的副作用]** `G_spat` 原来只在特定分支执行，前置到全局后可能影响原来不经过 `G_spat` 清理的文件名。但 `G_spat` 匹配的都是明确的前缀/后缀模式（网站域名@、画质标记），不太可能误伤正常番号。需在实现后回归测试现有的解析用例。
