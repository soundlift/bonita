## ADDED Requirements

### Requirement: 设置页面 SHALL 合并为统一的标签页结构

前端 SHALL 新建 `Settings.vue` 页面作为所有设置的统一入口，使用 `VTabs`/`VWindow` 组织以下标签页：
- "安全"（`security`）—— 引用 `AccountSettingsSecurity.vue`
- "服务"（`service`）—— 引用从 `ServiceSettings.vue` 提取的 `ServiceSettingsPanel.vue` 子组件
- "番号解析"（`parse`）—— 引用 `ParseBlacklistPanel.vue` 子组件

页面 SHALL 读取 URL query param `tab` 来确定初始激活的标签页。切换标签页 SHALL 更新 URL query param（不产生新的历史记录）。

#### Scenario: 默认进入安全标签页

- **WHEN** 用户访问 `/settings`（无 query param）
- **THEN** SHALL 默认激活"安全"标签页

#### Scenario: 通过 query param 指定标签页

- **WHEN** 用户访问 `/settings?tab=parse`
- **THEN** SHALL 激活"番号解析"标签页

### Requirement: 导航栏 SHALL 合并设置入口

`NavItems.vue` SHALL 移除独立的"服务设置"和"用户设置"两个导航入口，替换为一个"设置"入口指向 `/settings`。

#### Scenario: 导航栏显示单一设置入口

- **WHEN** 用户查看导航栏
- **THEN** SHALL 只看到一个"设置"入口（图标 `bxs-cog` 或 `bxs-server`），点击导航到 `/settings`

### Requirement: 旧路由 SHALL 重定向到新页面

路由配置 SHALL 为 `/settings/user` 和 `/settings/service` 添加重定向：
- `/settings/user` → `/settings?tab=security`
- `/settings/service` → `/settings?tab=service`

#### Scenario: 旧书签兼容

- **WHEN** 用户通过书签访问 `/settings/service`
- **THEN** SHALL 重定向到 `/settings?tab=service`，显示服务标签页内容
