## 1. 后端：success 过滤参数

- [x] 1.1 在 `backend/bonita/services/record_service.py` 的 `get_records` 方法中，新增 `success: Optional[bool] = None` 参数；当 `success is not None` 时，在主查询和 count 查询中均添加 `.filter(TransRecords.success == success)`
- [x] 1.2 在 `backend/bonita/api/routes/records.py` 的 `get_records` 路由函数中，新增 `success: Optional[bool] = None` 查询参数，并将其透传给 `record_service.get_records(success=success)`

## 2. 前端 Store 透传

- [x] 2.1 在 `frontend/src/stores/record.store.ts` 的 `getRecords` 方法的 `options` 参数类型中新增 `success?: boolean | null` 字段
- [x] 2.2 在 `getRecords` 方法体内，将 `options.success` 透传给 `RecordService.getRecords({ success: options.success, ... })`（`null` 时不传该参数）

## 3. 前端 i18n 标签

- [x] 3.1 在 `frontend/src/plugins/i18n/locales/zh.ts` 的 `records` 命名空间中新增：`statusFilter: "状态筛选"`、`columnSettings: "列设置"`、`successStatus: "成功"`、`failedStatus: "失败"`、`allStatus: "全部"`
- [x] 3.2 在 `frontend/src/plugins/i18n/locales/en.ts` 的 `records` 命名空间中新增对应英文翻译：`statusFilter: "Status Filter"`、`columnSettings: "Columns"`、`successStatus: "Success"`、`failedStatus: "Failed"`、`allStatus: "All"`

## 4. 前端 Records 页面：状态筛选 UI

- [x] 4.1 在 `frontend/src/pages/Records.vue` 中新增 `successFilter` ref（类型 `ref<boolean | null>(null)`，默认 `null`）
- [x] 4.2 定义状态筛选选项数组：`[{ value: null, title: t('pages.records.allStatus') }, { value: true, title: t('pages.records.successStatus') }, { value: false, title: t('pages.records.failedStatus') }]`
- [x] 4.3 在工具栏的 `search-fields` 区域（任务 ID 输入框之后）新增 `v-select` 组件，绑定 `successFilter`，选项为上述数组，宽度约 120px
- [x] 4.4 将 `successFilter` 加入现有的 `watch` 监听列表（与 `searchQuery`、`taskIdQuery` 并列），复用 300ms 防抖机制触发 `loadData`
- [x] 4.5 在 `loadData` 函数中，当 `successFilter.value !== null` 时，将 `success: successFilter.value` 添加到 `searchParams` 对象中并透传给 `recordStore.getRecords`
- [x] 4.6 在搜索筛选 chips 区域（`.search-filters`），当 `successFilter !== null` 时显示对应的筛选 chip，可点击移除

## 5. 前端 Records 页面：列选择 UI

- [x] 5.1 定义一个 `allHeaders` 常量数组（复制现有 `headers` 的完整定义），作为所有可配置列的源数据
- [x] 5.2 新增 `visibleColumnKeys` ref（类型 `ref<string[]>([])`），初始值为所有可选列的 key 列表（即除 `actions` 外的数据列 key；`transfer_record.srcname` 虽然始终可见但也纳入 ref 以便统一管理）
- [x] 5.3 新增 `computed` 属性 `displayedHeaders`，基于 `allHeaders` 过滤出 `visibleColumnKeys` 中包含的 key，加上始终显示的 `actions` 列
- [x] 5.4 将 `v-data-table` 的 `:headers` 绑定从 `headers` 改为 `displayedHeaders`
- [x] 5.5 在工具栏操作区（刷新控件旁）新增列选择按钮：`v-btn`（图标 `mdi-view-column`，`size="small"`）+ `v-menu`，menu 内含 `v-checkbox` 列表（遍历 `allHeaders` 中除 `actions` 外的列）
- [x] 5.6 "名称"列（`transfer_record.srcname`）对应的 checkbox 设为 `disabled`（始终选中）

## 6. 前端 Records 页面：表格模板适配

- [x] 6.1 由于 `v-data-table` 的自定义行模板（`v-slot:item`）中 `<td>` 是手动列出的，需确保隐藏列时对应的 `<td>` 不渲染。将自定义行模板改为使用 `v-data-table` 的 `v-slot:item.{key}` 模式（按列 key 定义单元格），或用 `v-for` 遍历 `displayedHeaders` 动态渲染 `<td>`
- [x] 6.2 确保 checkbox 选择列（`show-select`）不受列选择影响，始终显示

## 7. 前端 Records 页面：localStorage 持久化

- [x] 7.1 定义 `STORAGE_KEY = "records-view-settings"` 常量
- [x] 7.2 新增 `saveSettings()` 函数：将 `successFilter`、`visibleColumnKeys`、`sortBy`、`recordStore.itemsPerPage` 序列化为 JSON，调用 `localStorage.setItem(STORAGE_KEY, JSON.stringify(...))`。用 `try/catch` 包裹，存储失败时静默忽略
- [x] 7.3 新增 `loadSettings()` 函数：`try` 读取 `localStorage.getItem(STORAGE_KEY)`，`JSON.parse` 后校验字段存在性，将值赋给对应的 ref。`catch` 块中静默忽略，使用默认值
- [x] 7.4 在 `onMounted` 中，先调用 `loadSettings()` 恢复设置，再调用 `initial()` 加载数据
- [x] 7.5 添加 `watch`（`deep: true`）监听 `successFilter`、`visibleColumnKeys`、`sortBy`、`recordStore.itemsPerPage`，任一变化时调用 `saveSettings()`。`watch` 应在 `loadSettings()` 之后激活（避免恢复设置时触发写入——可用 `nextTick` 延迟注册 watch 或用 flag 控制）

## 8. 前端 Client 类型重新生成

- [x] 8.1 后端运行后，执行 `npm run generate-client` 重新生成 `frontend/src/client/services.gen.ts` 和 `types.gen.ts`，使 `RecordService.getRecords` 的参数包含 `success`。若后端未运行，手动在 `services.gen.ts` 的 `getRecords` 方法参数中添加 `success?: boolean | null`

## 9. 验证

- [ ] 9.1 调用 `GET /api/v1/records/all?success=true`，确认只返回成功记录，count 与过滤后总数一致
- [ ] 9.2 调用 `GET /api/v1/records/all?success=false`，确认只返回失败记录
- [ ] 9.3 调用 `GET /api/v1/records/all`（不传 success），确认返回所有记录（向后兼容）
- [ ] 9.4 打开 Records 页面，在状态筛选中选择"成功"，确认表格只显示成功记录；切换回"全部"恢复
- [ ] 9.5 点击列选择按钮，取消勾选若干列，确认对应列从表格中消失；重新勾选后恢复
- [ ] 9.6 确认"名称"和"操作"列的 checkbox 为禁用状态，无法取消
- [ ] 9.7 设置状态筛选、隐藏部分列、切换排序，刷新页面，确认设置被恢复
- [ ] 9.8 在搜索框输入文字后刷新页面，确认搜索框为空（搜索词未持久化）但状态筛选/列可见性保持
- [ ] 9.9 清除 localStorage 中的 `records-view-settings`，刷新页面，确认使用默认设置
