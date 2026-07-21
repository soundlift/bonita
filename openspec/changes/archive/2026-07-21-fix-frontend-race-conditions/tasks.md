## 1. Records.vue: Request Sequencing

- [x] 1.1 新增 `requestGeneration = ref(0)` 计数器
- [x] 1.2 在 `loadData` 入口 `++requestGeneration.value`，在 await 返回后检查 generation 是否仍匹配，不匹配则丢弃结果
- [x] 1.3 在 `onBeforeUnmount` 中清除 `searchTimeout` 并递增 generation 使进行中请求失效
- [x] 1.4 验证：快速切换页签/搜索/排序时，最终显示的数据与最后一次操作一致

## 2. Records.vue: localStorage 校验

- [x] 2.1 `loadSettings` 中对 `sortBy` 增加结构校验（Array、length > 0、key 为 string），无效则使用默认值
- [x] 2.2 将 `visibleColumnKeys` 的恢复条件从 `length > 0` 改为 `Array.isArray`，允许空数组
- [x] 2.3 旧 `successFilter` 迁移后立即调用 `saveSettings()` 回写
- [x] 2.4 验证：畸形 localStorage 数据不导致页面报错，空列选择可正确恢复

## 3. Records.vue: Clear Handler 去重

- [x] 3.1 检查 `handleClearSearch` 等清除函数，移除其中直接调用 `loadData` 的代码，依赖 watcher 防抖触发
- [x] 3.2 验证：清除筛选条件时只发送一次请求

## 4. Records.vue: Delete 保留上下文

- [x] 4.1 确认 `handleDeleteSelected` 调用的 `loadData` 读取当前 reactive refs（activeTab、searchQuery、sortBy）
- [x] 4.2 如有遗漏则修复，确保删除后列表保持当前筛选/排序/页签状态
- [x] 4.3 验证：在"已刮削"页签删除一条记录后，列表仍停留在"已刮削"页签

## 5. ScrapeLogDrawer.vue: Request Identity

- [x] 5.1 新增 `fetchGeneration = ref(0)` 计数器
- [x] 5.2 在 `loadLatestLog` 入口递增 generation，await 后检查是否匹配且 drawer 仍打开
- [x] 5.3 在 `recordId` 或 `modelValue` 变化时重置 generation
- [x] 5.4 新增 `error` ref，非 404 错误设置错误信息并在模板中显示（含重试按钮）
- [x] 5.5 修改 404 处理：不永久停止轮询，改为继续轮询但不更新 UI（任务创建日志后自动出现）
- [x] 5.6 轮询增加 `pollingInFlight` 守卫，防止请求重叠
- [x] 5.7 验证：快速切换 record 时 drawer 显示正确的日志，404 后任务开始日志自动出现

## 6. Logs.vue: WebSocket Identity

- [x] 6.1 新增 `wsInstanceId` 计数器，在 `connectLogs` 中递增
- [x] 6.2 所有 ws 事件处理器（onopen/onmessage/onclose/onerror）检查 id 是否匹配，不匹配则 return
- [x] 6.3 将 token 捕获移到 `connectLogs` 函数内部，确保使用最新 token
- [x] 6.4 新增 `authError` ref，认证失败时（close code 1008）显示明确错误信息
- [x] 6.5 验证：断开重连后日志正常接收，认证失败有明确 UI 提示
