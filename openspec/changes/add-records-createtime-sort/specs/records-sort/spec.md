## ADDED Requirements

### Requirement: API 响应 SHALL 包含 createtime 字段

`TransferRecordBase` schema SHALL 包含 `createtime` 字段（`Optional[datetime]`），使 `/records/all` 端点的响应中每条记录都携带创建时间。该字段映射 `TransRecords.createtime` 数据库列。

#### Scenario: API 返回 createtime

- **WHEN** 客户端调用 `GET /api/v1/records/all`
- **THEN** 响应 `data` 数组中每条记录的 `transfer_record` 对象 SHALL 包含 `createtime` 字段，值为该记录的 INSERT 时间（ISO datetime 字符串或 null）

#### Scenario: createtime 在记录更新后保持不变

- **WHEN** 用户通过 `PUT /api/v1/records/record` 更新某记录的 season 或 top_folder
- **THEN** 该记录的 `createtime` 值 SHALL 保持为原始入库时间，不随更新操作变化

### Requirement: Records 列表 SHALL 默认按 createtime 排序

Records API 端点 `GET /api/v1/records/all` 的 `sort_by` 参数默认值 SHALL 为 `"createtime"`，`sort_desc` 默认值 SHALL 为 `True`（降序，最新入库的记录排在最前）。

#### Scenario: 不传 sort_by 参数时默认按 createtime 降序

- **WHEN** 客户端调用 `GET /api/v1/records/all` 且未提供 `sort_by` 查询参数
- **THEN** 返回的记录 SHALL 按 `createtime` 降序排列

#### Scenario: 显式传 sort_by=updatetime 仍可按更新时间排序

- **WHEN** 客户端调用 `GET /api/v1/records/all?sort_by=updatetime`
- **THEN** 返回的记录 SHALL 按 `updatetime` 排序（向后兼容）

### Requirement: 前端 Records 页面 SHALL 展示创建时间列并默认按其排序

Records 页面（`Records.vue`）的 `v-data-table` SHALL 新增"创建时间"列，列 key 为 `transfer_record.createtime`，可排序。页面默认排序状态 SHALL 为 `{ key: "transfer_record.createtime", order: "desc" }`。"更新时间"列 SHALL 保留，用户可通过表头点击切换排序列。

#### Scenario: 用户打开 Records 页面看到按创建时间排序的列表

- **WHEN** 用户导航到 Records 页面
- **THEN** 表格 SHALL 默认按"创建时间"降序排列，最新入库的记录显示在最上方

#### Scenario: 用户可切换到更新时间排序

- **WHEN** 用户点击"更新时间"列表头
- **THEN** 表格 SHALL 切换为按"更新时间"排序，排序方向通过再次点击切换

#### Scenario: 创建时间列展示格式化时间

- **WHEN** 表格渲染某行的"创建时间"单元格
- **THEN** 该单元格 SHALL 显示格式化后的本地时间字符串（复用现有 `formatDateTime` 函数）；若 `createtime` 为 null 则显示空字符串
