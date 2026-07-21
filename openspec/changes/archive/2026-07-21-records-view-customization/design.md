## Context

Records 页面（`Records.vue`）是 Bonita 中查看文件转移记录的主要界面。它使用 Vuetify 3 的 `v-data-table` 渲染一个 11 列的表格，通过 Pinia store（`record.store.ts`）调用 FastAPI 后端（`records.py` → `record_service.py`）获取分页数据。

当前筛选能力有限：文本搜索（匹配 `srcname`/`srcpath`）和任务 ID 精确过滤。状态列（`transfer_record.success`）只是展示，无法按它过滤。所有列固定显示，用户无法定制可见性。页面设置不持久化，每次打开都回到默认。

项目中有两个可参考的先例：

1. **Mediaitem 页面**（`Mediaitem.vue`）——已有多个下拉筛选器（媒体类型、观看状态、收藏状态），使用 `v-select` + 三态值（`null` 表示"全部"）模式。这是 Records 状态筛选的 UI 参考。
2. **app.store.ts** ——主题持久化使用 `localStorage.getItem`/`setItem`，是项目已建立的浏览器存储模式。未引入 VueUse `useStorage` 或 pinia 持久化插件。

后端 `record_service.get_records()` 已有清晰的过滤链路（`task_id`、`search`），添加 `success` 过滤只需追加一个 `.filter()` 条件，模式完全一致。

## Goals / Non-Goals

**Goals:**

- 用户可按状态（全部/成功/失败）筛选记录列表
- 用户可选择表格中显示哪些列（名称和操作列除外，始终可见）
- 用户的视图设置（状态筛选、可见列、排序、每页条数）持久化到浏览器，下次打开页面时自动恢复
- 后端支持按 `success` 字段过滤

**Non-Goals:**

- 不做 `deleted`/`srcdeleted`/`ignored`/`locked` 等其他状态维度的筛选（当前只做 `success`，后续按需扩展）
- 不持久化搜索词和任务 ID（一次性查询意图，不应跨会话保留）
- 不引入 VueUse `useStorage` 或 pinia 持久化插件（遵循项目现有的 raw localStorage 模式）
- 不修改后端排序逻辑（已通过 `getattr` 兼容）
- 不做列拖拽排序（列顺序固定，仅控制可见性）

## Decisions

### 决策 1：状态筛选用 `v-select` 三态下拉，不用按钮组

**选择**: 使用 `v-select` 下拉框，值为 `null`（全部）/ `true`（成功）/ `false`（失败），与 Mediaitem 页面的筛选 UI 风格一致。

**理由**: Records 页面工具栏已有多个输入控件（搜索框、任务 ID），空间紧凑。`v-select` 占用空间小，且与 Mediaitem 的观看状态/收藏状态筛选模式一致，用户认知成本低。按钮组（`v-btn-toggle`）三个选项占宽更大，且在工具栏中视觉权重过高。

**备选方案**: `v-btn-toggle` 三按钮组（全部/成功/失败）——视觉更突出但占空间大，与现有工具栏密度不匹配，放弃。

### 决策 2：列选择用"按钮 + 下拉菜单 + 复选框列表"模式

**选择**: 在工具栏放一个 `v-btn`（图标 `mdi-view-column`），点击弹出 `v-menu`，内含各列对应的 `v-checkbox`。

**理由**: 这是表格列控制的通用 UI 范式（Ant Design、AG Grid、Notion 都用类似模式），用户一看就懂。按钮收起时只占一个图标位，展开后是清晰的复选框列表。比侧边抽屉（`v-navigation-drawer`）更轻量。

**备选方案**: 侧边设置抽屉——对于"仅控制列可见性"这个需求来说过重，放弃。

### 决策 3：名称和操作列始终可见，不可取消勾选

**选择**: "名称"（`transfer_record.srcname`）和"操作"（`actions`）列在列选择菜单中显示为禁用状态（`disabled`），始终选中。

**理由**: 名称是每条记录的核心标识，操作列包含编辑和重跑按钮——隐藏这两列会让记录无法辨识和操作。其他数据列（状态、路径、季、集、编号、标签、时间列）都可以自由开关。

### 决策 4：localStorage 存储以下设置，不含搜索词和任务 ID

**选择**: 存储 key 为 `records-view-settings`，值为 JSON：

```json
{
  "successFilter": null | true | false,
  "visibleColumns": ["transfer_record.success", "transfer_record.destpath", ...],
  "sortBy": [{ "key": "transfer_record.createtime", "order": "desc" }],
  "itemsPerPage": 25
}
```

**不存储**: `searchQuery`、`taskIdQuery`、`autoRefresh`、`refreshInterval`。

**理由**: 搜索词和任务 ID 是一次性的查询意图——用户输入它们是为了"找到某条特定记录"，找到后这次查询就结束了，下次打开页面不应该继续过滤。而状态筛选、列可见性、排序、每页条数是"视图偏好"——用户希望以某种方式看数据，这个偏好是持续的。自动刷新属于实时行为控制，不属于视图配置。

### 决策 5：后端 `success` 参数用 `Optional[bool]`，`None` 表示不过滤

**选择**: 后端 `get_records` 路由新增 `success: Optional[bool] = None` 参数，service 层在 `success is not None` 时添加 `.filter(TransRecords.success == success)`。

**理由**: 与现有 `task_id`/`search` 参数的模式完全一致——`None` 表示不应用此过滤条件。前端 `null` 值直接映射为不传此参数，`true`/`false` 传入精确过滤。向后兼容（不传参数时行为不变）。

## Risks / Trade-offs

- **[列选择菜单中的列标题]** headers 数组中的 `title` 字段是 i18n 翻译后的字符串，列选择菜单复用这些标题——如果用户切换语言，已存储的 `visibleColumns` 用 key（如 `"transfer_record.createtime"`）而非 title 存储，切换语言后显示正确 ✓
- **[向后兼容性]** 新增的 localStorage key 是首次引入，用户第一次打开页面时没有存储值——代码需对缺失值做 fallback（全部列可见、无状态筛选、默认排序），已纳入设计
- **[后端 count 查询]** `record_service.get_records()` 的 count 查询需同步应用 `success` 过滤条件，否则分页总数不匹配——与现有 `task_id`/`search` 的 count 逻辑一致，已纳入设计
- **[状态筛选与搜索防抖]** 状态筛选变化应触发数据重载，但不应每次点击都立即请求——复用现有的 `watch` + `setTimeout` 防抖机制（300ms），与搜索词一致
