## ADDED Requirements

### Requirement: 后端 SHALL 支持按 success 字段过滤记录

`GET /api/v1/records/all` 端点 SHALL 新增 `success` 查询参数（`Optional[bool]`，默认 `None`）。当 `success` 为 `None` 时不应用状态过滤；当 `success` 为 `True` 时只返回 `transfer_record.success == True` 的记录；当 `success` 为 `False` 时只返回 `transfer_record.success == False` 的记录。`record_service.get_records()` 的 count 查询 SHALL 同步应用此过滤条件，确保分页总数正确。

#### Scenario: 不传 success 参数时返回所有记录

- **WHEN** 客户端调用 `GET /api/v1/records/all` 且未提供 `success` 查询参数
- **THEN** 返回的记录 SHALL 包含所有状态（成功和失败），行为与当前版本完全一致（向后兼容）

#### Scenario: 传 success=true 只返回成功记录

- **WHEN** 客户端调用 `GET /api/v1/records/all?success=true`
- **THEN** 返回的记录 SHALL 只包含 `transfer_record.success == True` 的记录，`count` 字段 SHALL 反映过滤后的总数

#### Scenario: 传 success=false 只返回失败记录

- **WHEN** 客户端调用 `GET /api/v1/records/all?success=false`
- **THEN** 返回的记录 SHALL 只包含 `transfer_record.success == False` 的记录，`count` 字段 SHALL 反映过滤后的总数

### Requirement: 前端 Records 页面 SHALL 提供状态筛选下拉框

Records 页面工具栏 SHALL 在搜索框和任务 ID 输入框之后新增一个状态筛选 `v-select` 下拉框。该下拉框有三个选项："全部"（值 `null`）、"成功"（值 `true`）、"失败"（值 `false`）。默认值为 `null`（全部）。当用户选择"成功"或"失败"时，SHALL 触发数据重新加载（带 300ms 防抖），将 `success` 参数传递给 store 和后端 API。

#### Scenario: 用户选择"成功"筛选

- **WHEN** 用户在状态筛选下拉框中选择"成功"
- **THEN** 表格 SHALL 在 300ms 内重新加载数据，只显示 `transfer_record.success == True` 的记录，分页总数 SHALL 更新为筛选后的数量

#### Scenario: 用户切换回"全部"

- **WHEN** 用户在状态筛选下拉框中选择"全部"
- **THEN** 表格 SHALL 重新加载所有状态的记录，状态筛选不再作为查询条件传递给后端

#### Scenario: 状态筛选与搜索词可同时使用

- **WHEN** 用户已输入搜索词且选择了状态筛选
- **THEN** 两个过滤条件 SHALL 同时生效，后端返回同时满足文本搜索和状态过滤的记录

### Requirement: 前端 Records 页面 SHALL 提供列选择功能

Records 页面工具栏 SHALL 新增一个列选择按钮（图标 `mdi-view-column`），点击后弹出下拉菜单，内含各数据列对应的复选框。用户可通过勾选/取消勾选来控制对应列的显示和隐藏。

"名称"（`transfer_record.srcname`）和"操作"（`actions`）列 SHALL 始终可见，其在列选择菜单中的复选框 SHALL 显示为禁用（`disabled`）且始终选中状态。选择框列（`show-select` 的 checkbox）SHALL 始终显示，不纳入列选择菜单。

其他数据列（状态、目标路径、季、集、编号、标签、创建时间、更新时间、截止时间）SHALL 可由用户自由切换可见性。

#### Scenario: 用户隐藏某列

- **WHEN** 用户在列选择菜单中取消勾选"更新时间"
- **THEN** 表格 SHALL 立即移除"更新时间"列，其他列不受影响

#### Scenario: 用户重新显示某列

- **WHEN** 用户在列选择菜单中勾选之前隐藏的列
- **THEN** 该列 SHALL 立即重新出现在表格中，位置与原始 headers 定义一致

#### Scenario: 名称和操作列不可隐藏

- **WHEN** 用户打开列选择菜单
- **THEN** "名称"和"操作"对应的复选框 SHALL 显示为禁用状态，无法取消勾选

### Requirement: Records 页面视图设置 SHALL 持久化到浏览器 localStorage

Records 页面 SHALL 将以下设置存储到 `localStorage`，key 为 `records-view-settings`，值为 JSON 对象：

- `successFilter`: 状态筛选值（`null` / `true` / `false`）
- `visibleColumns`: 可见列的 key 数组（如 `["transfer_record.success", "transfer_record.destpath", ...]`）
- `sortBy`: 排序状态数组（`[{ "key": "...", "order": "desc" }]`）
- `itemsPerPage`: 每页条数

页面 `onMounted` 时 SHALL 尝试读取 `localStorage` 中的存储值。如果存在，SHALL 将存储值应用到对应的 ref（状态筛选、可见列、排序、每页条数），然后加载数据。如果存储值不存在或解析失败，SHALL 使用默认值（全部列可见、无状态筛选、默认按 createtime 降序、每页 10 条）。

以下设置 SHALL NOT 被持久化：`searchQuery`（搜索词）、`taskIdQuery`（任务 ID）、`autoRefresh`、`refreshInterval`。

#### Scenario: 用户设置在页面重载后恢复

- **WHEN** 用户选择了状态筛选为"失败"、隐藏了"标签"列、切换排序为"更新时间"降序，然后关闭并重新打开 Records 页面
- **THEN** 页面 SHALL 自动应用上次的设置：状态筛选为"失败"、"标签"列隐藏、排序为"更新时间"降序

#### Scenario: 首次访问使用默认值

- **WHEN** 用户首次访问 Records 页面（localStorage 中无 `records-view-settings`）
- **THEN** 页面 SHALL 使用默认设置：状态筛选为"全部"、所有可选列可见、排序为"创建时间"降序、每页 10 条

#### Scenario: 搜索词不被持久化

- **WHEN** 用户在搜索框输入"movie"、选择状态筛选为"成功"，然后关闭并重新打开 Records 页面
- **THEN** 搜索框 SHALL 为空（搜索词未持久化），但状态筛选 SHALL 仍为"成功"

#### Scenario: 存储值解析失败时优雅降级

- **WHEN** `localStorage` 中的 `records-view-settings` 值不是有效的 JSON 或格式不匹配预期 schema
- **THEN** 页面 SHALL 忽略存储值，使用默认设置，不抛出错误
