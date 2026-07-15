## Why

Records 列表当前默认按 `updatetime` 排序，而 `updatetime` 在每次操作（改 season、批量替换路径、重置状态等）时都会刷新，导致用户无法保持稳定的时间线视图。用户需要一个固定的"入库锚点"——即文件首次被记录的时间——作为默认排序依据。

`createtime` 列已存在于数据库中（`transrecords.createtime`，INSERT 时写入一次，无 `onupdate`），且后端排序逻辑已通过 `getattr(TransRecords, sort_by)` 支持任意字段。本变更仅需在展示层暴露该字段并将其设为默认排序。

## What Changes

- 在 `TransferRecordBase` schema 中暴露 `createtime` 字段，使 API 响应包含创建时间
- 将 `/records/all` 端点的 `sort_by` 默认值从 `"updatetime"` 改为 `"createtime"`
- 在前端 Records 表格中新增"创建时间"列（保留现有的"更新时间"列）
- 将前端默认排序从 `transfer_record.updatetime` 改为 `transfer_record.createtime`
- 新增 i18n 标签 `createTime`（中/英）

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `records-sort`: 记录列表排序能力——新增 `createtime` 作为可用排序字段并将其设为默认排序字段，同时 API 响应暴露 `createtime` 值

## Impact

- **后端 schema**: `backend/bonita/schemas/record.py` — `TransferRecordBase` 新增 `createtime` 字段
- **后端路由**: `backend/bonita/api/routes/records.py` — `get_records` 的 `sort_by` 参数默认值变更
- **前端页面**: `frontend/src/pages/Records.vue` — 新增表格列、修改默认排序 ref
- **前端 i18n**: `frontend/src/plugins/i18n/locales/zh.ts` 和 `en.ts` — 新增 `createTime` 标签
- **前端 client types**: 需重新生成 `services.gen.ts` / `types.gen.ts` 以包含新字段
- **行为变更**: 用户打开 Records 页面时将默认按创建时间排序（非破坏性，用户仍可手动切换到 updatetime）
