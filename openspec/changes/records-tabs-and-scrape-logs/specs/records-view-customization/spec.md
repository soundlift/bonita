## MODIFIED Requirements

### Requirement: 后端 SHALL 支持按 success 字段过滤记录

`GET /api/v1/records/all` 端点 SHALL 接受 `success` 查询参数（`Optional[bool]`，默认 `None`）。当 `success` 为 `None` 时 SHALL 不应用状态过滤。当 `success` 为 `True` 时 SHALL 只返回 `transfer_record.success == True` 的记录。当 `success` 为 `False` 时 SHALL 只返回 `transfer_record.success != True` 的记录（即 `False` 与 `NULL`/中断记录）。`record_service.get_records()` 的 count 查询 SHALL 同步应用此过滤条件，确保分页总数正确。

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all` 且未提供 `success` 查询参数
- **THEN** 返回的记录 SHALL 包含所有状态（成功、失败、中断），行为与当前版本完全一致（向后兼容）

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all?success=true`
- **THEN** 返回的记录 SHALL 只包含 `transfer_record.success == True` 的记录，`count` 字段 SHALL 反映过滤后的总数

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all?success=false`
- **THEN** 返回的记录 SHALL 同时包含 `transfer_record.success == False` 与 `transfer_record.success IS NULL` 的记录（即所有 `success IS NOT TRUE` 的记录），`count` 字段 SHALL 反映这两类的总数

## REMOVED Requirements

### Requirement: 前端 Records 页面 SHALL 提供状态筛选下拉框
**Reason**: 状态筛选下拉被新的页签布局（`records-tabs` capability）取代。新的「未刮削/已刮削」页签提供更清晰的视觉分离，不再需要"全部"选项。
**Migration**: 工具栏中状态筛选 `v-select` 移除；用户通过点击页签切换视图。localStorage 中的 `successFilter` 字段在加载时迁移为 `activeTab`（详见 `records-tabs` spec）。

### Requirement: Records 页面视图设置 SHALL 持久化到浏览器 localStorage
**Reason**: 原需求中的 `successFilter` 字段被 `activeTab` 取代（详见 `records-tabs` capability）。其余字段（`visibleColumns`、`sortBy`、`itemsPerPage`）保留不变。
**Migration**: `loadSettings()` 函数 SHALL 显式检测旧 `successFilter` 字段并迁移：`true` → `activeTab="done"`，`false` 或 `null` → `activeTab="pending"`；迁移后从存储对象中删除 `successFilter` 字段。`records-view-settings` 这个 key 名称保留，结构内部变化。
