## ADDED Requirements

### Requirement: Records 页面页签化布局
Records 页面 SHALL 在页面顶部使用 `v-tabs` 组件展示两个固定页签：「未刮削」与「已刮削」。页签 SHALL 替代原工具栏中的状态筛选 `v-select` 下拉框（该下拉框 SHALL 被移除）。

「未刮削」页签 SHALL 展示所有 `success IS NOT TRUE` 的记录（即 `success == False` 或 `success IS NULL`）。「已刮削」页签 SHALL 展示所有 `success == True` 的记录。

页面初次加载时 SHALL 默认聚焦「未刮削」页签。页签切换 SHALL 触发数据重新加载（带 300ms 防抖），将对应的 `success` 参数传递给 store 和后端 API。

#### Scenario: 用户首次进入 Records 页面
- **WHEN** 用户首次访问 Records 页面（localStorage 中无 `records-active-tab`）
- **THEN** 页面 SHALL 默认聚焦「未刮削」页签，并加载 `success=False` 的记录列表

#### Scenario: 切换到「已刮削」页签
- **WHEN** 用户点击「已刮削」页签
- **THEN** 表格 SHALL 在 300ms 内重新加载数据，只显示 `success == True` 的记录，分页总数 SHALL 更新为筛选后的数量

#### Scenario: 页签状态持久化
- **WHEN** 用户选择了「已刮削」页签后关闭并重新打开 Records 页面
- **THEN** 页面 SHALL 自动聚焦到「已刮削」页签（从 localStorage `records-active-tab` 读取）

#### Scenario: 旧 localStorage 数据迁移
- **WHEN** 用户浏览器中存在旧 key `records-view-settings` 且包含 `successFilter` 字段
- **THEN** 页面 SHALL 将 `successFilter=true` 迁移为 `activeTab="done"`，`successFilter=false` 或 `null` 迁移为 `activeTab="pending"`，迁移后从存储对象中删除 `successFilter` 字段

#### Scenario: 页签切换与其他过滤器联动
- **WHEN** 用户在「未刮削」页签下输入搜索词"abc"并输入任务ID 5
- **THEN** 后端 SHALL 同时应用 `success=False`、搜索词、任务 ID 三个过滤条件，返回交集记录

### Requirement: 后端 success 参数语义统一
`GET /api/v1/records/all` 端点的 `success` 查询参数 SHALL 保持现有签名（`Optional[bool]`，默认 `None`）。当 `success is None` 时 SHALL 不应用状态过滤（行为不变）。当 `success is True` 时 SHALL 只返回 `success == True` 的记录（行为不变）。当 `success is False` 时 SHALL 返回所有 `success IS NOT TRUE` 的记录（覆盖 `False` 与 `NULL`）。

`record_service.RecordService.get_records()` 的 count 查询 SHALL 同步应用此过滤条件。

#### Scenario: success=false 包含 NULL 记录
- **WHEN** 客户端调用 `GET /api/v1/records/all?success=false`
- **THEN** 返回的记录 SHALL 同时包含 `success == False` 与 `success IS NULL` 的记录，`count` 字段 SHALL 反映这两类的总数

#### Scenario: success=true 行为不变
- **WHEN** 客户端调用 `GET /api/v1/records/all?success=true`
- **THEN** 返回的记录 SHALL 只包含 `success == True` 的记录（与现有行为完全一致）

#### Scenario: 不传 success 行为不变
- **WHEN** 客户端调用 `GET /api/v1/records/all` 且未提供 `success` 查询参数
- **THEN** 返回的记录 SHALL 包含所有状态（成功、失败、中断），行为与现有版本完全一致（向后兼容）
