## Context

Bonita 的 Records 页面展示转移记录（`TransRecords`），当前默认按 `updatetime` 降序排序。`updatetime` 字段带有 `onupdate=datetime.now`，任何 UPDATE 操作（改 season、批量替换路径前缀、重置删除状态等）都会刷新它，导致记录在列表中频繁跳动。

数据库中已存在 `createtime` 列（`record.py:39`），它只有 `default=datetime.now` 而没有 `onupdate`，在 INSERT 时写入一次后永不变更。入库路径（`celery_tasks/tasks.py:180-186`）通过 `srcpath` 去重，同一文件不会重复创建记录。因此 `createtime` 天然是文件入库的固定时间锚点。

后端排序逻辑（`record_service.py:67`）已通过 `getattr(TransRecords, sort_by, TransRecords.updatetime)` 动态解析排序字段，无需改动 service 层。

Mediaitem 页面（`Mediaitem.vue`）已有 createtime 排序的先例，包括 i18n 标签 `sortCreatetime`，证明此模式在项目中成立。

## Goals / Non-Goals

**Goals:**

- 在 API 响应中暴露 `createtime`，使前端能展示和排序该字段
- 将 Records 页面默认排序改为 `createtime` 降序
- 同时保留 `updatetime` 列和排序能力，用户可手动切换

**Non-Goals:**

- 不修改 `createtime` 的写入逻辑（它已经是正确的一次性写入）
- 不做旧数据回填（2025-03-15 迁移前的记录 `createtime` 为迁移时间，可接受）
- 不引入 Mediaitem 那样的下拉排序菜单（Records 用的是 v-data-table 表头点击排序，保持一致）
- 不修改后端 service 层的排序逻辑（已兼容）

## Decisions

### 决策 1：排序交互沿用 v-data-table 表头点击，不引入下拉菜单

**选择**: 在现有表格中新增 `createtime` 列，通过表头点击排序。

**理由**: Records 页面已用 Vuetify `v-data-table` 的 `@update:sort-by` 机制，列头自带排序箭头。新增一列即可获得排序能力，无需额外 UI 组件。Mediaitem 的下拉菜单模式适用于它的特殊场景（多排序字段 + 自定义图标），Records 不需要。

**备选方案**: 仿照 Mediaitem 加排序下拉菜单——增加了 UI 复杂度且与当前页面风格不一致，放弃。

### 决策 2：默认排序列从 updatetime 改为 createtime

**选择**: 前端 `sortBy` ref 默认值改为 `transfer_record.createtime`；后端 `sort_by` 参数默认值改为 `"createtime"`。

**理由**: 用户明确要求"固定锚点"作为默认视图。后端默认值同步修改是为了保持 API 直接调用时的一致性。

### 决策 3：createtime 列位置放在 updatetime 之前

**选择**: 表格列顺序为 `... [创建时间] [更新时间] [删除截止] [操作]`。

**理由**: 创建时间是更根本的属性（锚点），更新时间是派生属性，逻辑上创建在前。两张时间列相邻便于用户对比。

### 决策 4：不做 createtime 的数据回填

**选择**: 不执行任何数据迁移脚本去修正旧记录的 `createtime`。

**理由**: 迁移 `eca431b007aa`（2025-03-15）已用 `server_default=CURRENT_TIMESTAMP` 回填了非 NULL 值。旧记录的 `createtime` 为迁移执行时间，虽非真实入库时间，但排序不会报错且影响范围有限（仅迁移前数据）。用户未对此提出要求，留作后续可选优化。

## Risks / Trade-offs

- **[旧数据排序精度]** 2025-03-15 之前创建的记录，`createtime` 为迁移时间而非真实入库时间，按 createtime 排序时这些记录会聚集在同一时间点 → 可接受，用户已知晓；如需修正可后续补一个一次性 SQL 脚本
- **[表格宽度增加]** 新增一列使表格更宽 → createtime 列宽与 updatetime 一致（120px），在现有响应式布局下可接受；极端窄屏已有横向滚动
- **[API 响应体积]** 新增一个 datetime 字段 → 微乎其微，单条记录仅增加约 30 字节
