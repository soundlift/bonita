## Why

当前设置分散在两个独立页面（`UserSettings.vue` 安全设置、`ServiceSettings.vue` 服务连接设置），导航栏有两个入口，用户需要来回切换。同时，番号解析存在已知的"网站前缀污染"问题（如 `hhd800.com@MKMP-725.mp4` 被错误解析为 `HHD-800`），用户需要一个可自定义的黑名单来过滤这类干扰字符串。这两个需求自然合流——合并设置页面并新增"番号解析"标签页放置黑名单配置。

## What Changes

### 合并设置页面（前端重构）

- 新建 `frontend/src/pages/Settings.vue` 统一设置页面，使用 `VTabs` + `VWindow` 组织内容，包含三个标签页：
  - **安全**（复用现有 `AccountSettingsSecurity.vue`）
  - **服务**（复用现有 `ServiceSettings.vue` 的全部内容，提取为子组件或直接内联）
  - **番号解析**（新增）
- 路由调整：`/settings` 下使用子路由或 query param 切换 tab（如 `/settings?tab=security`）
- 导航栏两个入口（"服务设置"、"用户设置"）合并为一个"设置"入口

### 番号解析黑名单（后端 + 前端）

- **后端存储**: `SystemSetting` 表新增 `parse_blacklist` key，值为 JSON 数组 `[{"id": 1, "mode": "literal"|"regex", "value": "hhd800.com", "enabled": true}]`
- **后端 API**: `GET /api/v1/settings/parse-blacklist` 获取黑名单，`POST /api/v1/settings/parse-blacklist` 保存黑名单
- **后端解析逻辑**: `number_parser.py` 的 `get_number()` 函数中，在 `rules_parser(filename)` 调用之前，从数据库读取黑名单并清理 filename（literal 模式用 `str.replace`，regex 模式用 `re.sub`）。同时将已有的 `G_spat` 清理前置到 `rules_parser` 之前（修复内置的网站前缀清理逻辑执行太晚的问题）
- **前端 UI**: "番号解析"标签页包含黑名单列表（增删改）、每条规则可选模式（精确匹配/正则表达式）、实时预览功能（输入测试文件名，显示清理后的解析结果）、说明文字

## Capabilities

### New Capabilities

- `parse-blacklist`: 番号解析黑名单能力——用户可配置需要过滤的字符串或正则表达式，解析番号时在规则匹配前清理文件名
- `settings-page-merge`: 设置页面合并能力——将分散的用户设置和服务设置合并为统一的标签页式设置页面

### Modified Capabilities

（无）

## Impact

- **前端页面**: `frontend/src/pages/Settings.vue`（新建）、`frontend/src/pages/UserSettings.vue`（保留或重定向）、`frontend/src/pages/ServiceSettings.vue`（内容迁移）
- **前端路由**: `frontend/src/plugins/router/routes.ts` — 调整 `/settings` 路由结构
- **前端导航**: `frontend/src/layouts/components/NavItems.vue` — 合并两个设置入口
- **前端 store**: `frontend/src/stores/setting.store.ts` — 新增黑名单相关 state 和 actions
- **后端路由**: `backend/bonita/api/routes/settings.py` — 新增 `GET/POST /parse-blacklist`
- **后端服务层**: `backend/bonita/services/setting_service.py` — 新增 `get_parse_blacklist()` 和 `update_parse_blacklist()` 方法
- **后端解析**: `backend/bonita/modules/scraping/number_parser.py` — `get_number()` 前置黑名单清理 + `G_spat` 前置
- **前端 client**: 重新生成 `services.gen.ts` 包含新的黑名单端点
- **前端 i18n**: `zh.ts` 和 `en.ts` — 新增设置页 tab 标题、黑名单相关文案
