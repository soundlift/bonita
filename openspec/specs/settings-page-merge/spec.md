# Spec: Settings Page Merge

## Purpose

Consolidate the separate user settings and service settings pages into a single tabbed Settings page, with backward-compatible redirects for old routes.

## ADDED Requirements

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
