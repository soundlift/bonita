## Why

Records 页面目前功能固定，用户无法根据自身关注点定制视图：

1. **无法按状态筛选** —— 状态列展示了成功/失败，但没有对应的筛选器。当用户只想看失败的记录（需要排查问题）或只想看成动的记录时，只能在几百条数据里用眼睛扫。
2. **无法选择显示哪些列** —— 表格有 11 列（含选择框和操作列），在中小屏幕上信息过载。有些用户只关心名称和目标路径，有些只关心时间和状态，但目前无法隐藏不关心的列。
3. **视图设置不持久** —— 每次打开页面都回到默认状态。如果上次设了筛选或排序列，关掉浏览器再打开就丢了，体验断裂。

## What Changes

### 状态筛选（后端 + 前端）

- 后端 `GET /records/all` 新增 `success: Optional[bool]` 查询参数，`record_service.get_records()` 新增对应的 `.filter()` 逻辑
- 前端 Records 页面工具栏新增状态筛选下拉框（全部 / 成功 / 失败），与现有的搜索框、任务 ID 过滤并排
- 状态筛选变化时触发数据重新加载（带防抖，复用现有 watch 机制）

### 列选择（纯前端）

- Records 页面工具栏新增"列选择"按钮 + 下拉菜单（`v-btn` + `v-menu` + `v-checkbox` 列表）
- 用户可勾选/取消勾选各列的可见性
- "名称"和"操作"列始终可见，不可取消（核心交互列）
- 表格 `headers` 根据用户选择动态过滤渲染

### 设置持久化（纯前端）

- 用 `localStorage`（key: `records-view-settings`）存储以下设置：
  - 状态筛选值
  - 可见列列表
  - 当前排序字段和方向
  - 每页条数
- 页面 `onMounted` 时读取存储，恢复上次设置
- 不存储搜索词和任务 ID（这些是一次性查询意图，不应跨会话保留）
- 遵循项目现有的 `localStorage.getItem`/`setItem` 模式（参考 `app.store.ts` 主题持久化）

## Capabilities

### New Capabilities

- `records-view-customization`: Records 页面视图定制能力——状态筛选、列可见性控制、视图设置浏览器持久化

### Modified Capabilities

（无）

## Impact

- **后端路由**: `backend/bonita/api/routes/records.py` — `get_records` 新增 `success` 参数
- **后端服务层**: `backend/bonita/services/record_service.py` — `get_records` 方法新增 `success` 过滤逻辑
- **前端页面**: `frontend/src/pages/Records.vue` — 新增状态筛选 UI、列选择 UI、localStorage 读写逻辑、headers 动态过滤
- **前端 store**: `frontend/src/stores/record.store.ts` — `getRecords` 方法新增 `success` 参数透传
- **前端 client**: 需重新生成 `services.gen.ts` 以包含新的 `success` 查询参数
- **前端 i18n**: `frontend/src/plugins/i18n/locales/zh.ts` 和 `en.ts` — 新增筛选/列选择相关标签
