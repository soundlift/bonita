## 1. 后端：黑名单存储与 API

- [x] 1.1 在 `backend/bonita/services/setting_service.py` 中新增 `get_parse_blacklist() -> List[Dict]` 方法：从 `SystemSetting` 读取 key=`parse_blacklist` 的值，`json.loads` 解析为列表。如果 key 不存在或解析失败，返回空列表
- [x] 1.2 在 `setting_service.py` 中新增 `update_parse_blacklist(blacklist: List[Dict]) -> Dict` 方法：将列表 `json.dumps` 序列化为字符串，调用 `self.set_setting("parse_blacklist", json_str, "番号解析黑名单")` 保存
- [x] 1.3 在 `backend/bonita/api/routes/settings.py` 中新增 `GET /parse-blacklist` 端点：调用 `setting_service.get_parse_blacklist()`，返回 `{"data": [...], "success": true}`
- [x] 1.4 在 `settings.py` 中新增 `POST /parse-blacklist` 端点：接收 `blacklist: List[Dict]` body，调用 `setting_service.update_parse_blacklist(blacklist)`，返回 `schemas.Response(success=True, message="黑名单已更新")`
- [x] 1.5 在 `settings.py` 中新增 `POST /parse-blacklist/preview` 端点：接收 `{"filename": str, "blacklist": [...]}` body，使用传入的黑名单对 filename 执行清理（调用 `number_parser` 的清理逻辑）+ `rules_parser` 解析，返回 `{"cleaned_filename": str, "parsed_number": str|null}`

## 2. 后端：解析逻辑前置清理

- [x] 2.1 在 `backend/bonita/modules/scraping/number_parser.py` 中新增 `apply_blacklist(filename: str, blacklist: List[Dict]) -> str` 函数：遍历黑名单中 `enabled=true` 的规则，`literal` 模式用 `filename.replace(value, "")`，`regex` 模式用 `try: re.sub(value, "", filename) except: logger.warning(...)` 跳过无效正则
- [x] 2.2 在 `get_number()` 函数中，在 `(filename, ext) = os.path.splitext(basename)`（第 155 行）之后、`file_number = rules_parser(filename)`（第 156 行）之前，插入两步清理：① `filename = G_spat.sub("", filename)` ② `filename = apply_blacklist(filename, get_blacklist_from_db())`。需新增 `get_blacklist_from_db()` 辅助函数读取数据库（考虑用 `SessionFactory()` 获取 session）
- [x] 2.3 在 `number_parser.py` 中新增 `get_blacklist_from_db() -> List[Dict]` 函数：用 `SessionFactory()` 获取 session，调用 `SettingService(session).get_parse_blacklist()`，返回黑名单列表。需 `from bonita.db import SessionFactory` 和 `from bonita.services.setting_service import SettingService`。注意避免循环导入（函数内导入）
- [x] 2.4 回归测试：运行 `number_parser.py` 的 `__main__` 测试用例（第 306-340 行），确认所有现有用例解析结果不变（G_spat 前置不应影响不含网站前缀的文件名）
- [x] 2.5 手动验证：构造 `hhd800.com@MKMP-725.mp4` 测试路径，确认 G_spat 前置后解析为 `MKMP-725`（无需黑名单配置即可修复）

## 3. 前端：Store 层

- [x] 3.1 在 `frontend/src/stores/setting.store.ts` 中新增 `parseBlacklist: []` state 和 `fetchParseBlacklist()` / `updateParseBlacklist(data)` / `previewParse(filename, blacklist)` actions
- [x] 3.2 在 `frontend/src/client/services.gen.ts` 中手动添加 `getParseBlacklist`、`updateParseBlacklist`、`previewParse` 方法（或运行 `npm run generate-client` 重新生成）。在 `types.gen.ts` 中添加相关类型

## 4. 前端：设置页面合并

- [x] 4.1 新建 `frontend/src/views/settings/ServiceSettingsPanel.vue`，将 `ServiceSettings.vue` 的全部 `<script setup>` 和 `<template>` 内容迁移过来（逻辑保持不变）
- [x] 4.2 新建 `frontend/src/views/settings/ParseBlacklistPanel.vue`，包含黑名单管理 UI（列表、新增/编辑/删除/启用切换）和预览区域。结构：顶部说明文字 → 黑名单规则表格 → 新增按钮 → 底部预览区。使用 `settingStore` 的 actions 读写数据
- [x] 4.3 新建 `frontend/src/pages/Settings.vue`，包含 `VTabs`（安全 | 服务 | 番号解析）+ `VWindow`，三个 `VWindowItem` 分别引用 `AccountSettingsSecurity.vue`、`ServiceSettingsPanel.vue`、`ParseBlacklistPanel.vue`。读取 `route.query.tab` 设置初始 tab，tab 切换时 `router.replace({ query: { tab } })` 更新 URL
- [x] 4.4 在 `frontend/src/plugins/router/routes.ts` 中：新增 `/settings` 路由指向 `Settings.vue`；将 `/settings/user` 改为 `redirect: "/settings?tab=security"`；将 `/settings/service` 改为 `redirect: "/settings?tab=service"`
- [x] 4.5 在 `frontend/src/layouts/components/NavItems.vue` 中：移除"服务设置"和"用户设置"两个 `VerticalNavLink`，替换为一个"设置"入口（`title: t('navitems.settings'), icon: 'bxs-cog', to: '/settings'`）

## 5. 前端：i18n

- [x] 5.1 在 `frontend/src/plugins/i18n/locales/zh.ts` 的 `navitems` 命名空间中新增 `settings: "设置"`。移除或保留 `serviceSettings` 和 `userSettings`（如果其他地方引用了就保留）
- [x] 5.2 在 `zh.ts` 中新增 `pages.settings` 命名空间，包含 tab 标题（`tabs: { security: "安全", service: "服务", parse: "番号解析" }`）和黑名单相关文案（`parseBlacklist: { title: "番号解析黑名单", description: "...", addRule: "新增规则", mode: "匹配模式", literal: "精确匹配", regex: "正则表达式", value: "规则值", enabled: "启用", preview: "预览", previewPlaceholder: "输入测试文件名", cleanedResult: "清理后", parsedResult: "解析结果", saveSuccess: "黑名单已保存" }`）
- [x] 5.3 在 `en.ts` 中新增对应英文翻译

## 6. 验证

- [x] 6.1 打开 `/settings`，确认显示三个标签页，默认激活"安全"tab
- [x] 6.2 切换到"服务"tab，确认代理/Emby/Jellyfin/Transmission 设置正常显示和保存（与原 ServiceSettings.vue 行为一致）
- [x] 6.3 访问旧链接 `/settings/service`，确认重定向到 `/settings?tab=service`
- [x] 6.4 导航栏确认只有一个"设置"入口
- [x] 6.5 切换到"番号解析"tab，确认黑名单列表加载正常（首次为空）
- [x] 6.6 新增一条黑名单规则（`hhd800.com`，精确匹配），保存，刷新页面确认规则持久化
- [x] 6.7 在预览区输入 `hhd800.com@MKMP-725.mp4`，点击预览，确认显示清理后 `@MKMP-725` 和解析结果 `MKMP-725`
- [x] 6.8 新增一条正则模式规则（`^\w+\.(com|net)@`），预览 `test.net@ABC-456.mp4`，确认解析为 `ABC-456`
- [x] 6.9 测试禁用规则：将 `hhd800.com` 规则禁用，保存，预览 `hhd800.com@MKMP-725.mp4`，确认 G_spat 仍然清理（因为 G_spat 内置了 .com@ 模式），解析仍为 `MKMP-725`
- [x] 6.10 测试无效正则：新增一条正则规则 `[invalid`，保存，预览功能不崩溃（该规则被跳过）
