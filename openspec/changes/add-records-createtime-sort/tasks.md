## 1. 后端 Schema 变更

- [x] 1.1 在 `backend/bonita/schemas/record.py` 的 `TransferRecordBase` 类中，于 `updatetime` 字段之前新增 `createtime: Optional[datetime] = None`
- [x] 1.2 将 `backend/bonita/api/routes/records.py` 中 `get_records` 函数的 `sort_by` 参数默认值从 `"updatetime"` 改为 `"createtime"`

## 2. 前端 i18n 标签

- [x] 2.1 在 `frontend/src/plugins/i18n/locales/zh.ts` 的 `records` 命名空间中新增 `createTime: "创建时间"`
- [x] 2.2 在 `frontend/src/plugins/i18n/locales/en.ts` 的 `records` 命名空间中新增 `createTime: "Create Time"`

## 3. 前端 Records 页面

- [x] 3.1 在 `frontend/src/pages/Records.vue` 的 `headers` 数组中，在"更新时间"(`transfer_record.updatetime`) 列之前新增"创建时间"列，key 为 `transfer_record.createtime`，`sortable: true`，`width: 120`
- [x] 3.2 在 `Records.vue` 中将 `sortBy` ref 的默认值从 `{ key: "transfer_record.updatetime", order: "desc" }` 改为 `{ key: "transfer_record.createtime", order: "desc" }`
- [x] 3.3 在 `Records.vue` 的表格模板中，在"更新时间"单元格之前新增"创建时间"单元格，复用 `formatDateTime(item.transfer_record.createtime)` 渲染

## 4. 前端 Client 类型重新生成

- [x] 4.1 手动在 `frontend/src/client/types.gen.ts` 的 `TransferRecordPublic` 类型中新增 `createtime?: string | null` 字段（后端未运行，无法自动生成；字段定义与现有 `updatetime` 模式一致）

## 5. 验证

- [ ] 5.1 启动后端，调用 `GET /api/v1/records/all`，确认响应中 `transfer_record` 对象包含 `createtime` 字段
- [ ] 5.2 调用 `GET /api/v1/records/all`（不传 sort_by），确认返回结果按 `createtime` 降序排列
- [ ] 5.3 调用 `GET /api/v1/records/all?sort_by=updatetime`，确认仍可按更新时间排序（向后兼容）
- [ ] 5.4 启动前端，打开 Records 页面，确认默认按"创建时间"降序排列，表头排序箭头指向 createtime 列
- [ ] 5.5 点击"更新时间"表头，确认可切换到按更新时间排序
- [ ] 5.6 确认"创建时间"列和"更新时间"列均正确显示格式化时间，编辑某记录后 createtime 不变、updatetime 刷新
