## Why

批次 1/2 已消除 P0 安全链和 P1-6/7/9/11 的基础设施问题。本批次继续修复剩余 P1/P2 输入校验和数据安全问题：

1. **P2-15** `MAX_CONCURRENT_TASKS` 环境变量类型错误：`os.environ.get` 返回 `str`，`Semaphore("5")` 会抛 `TypeError`。
2. **P2-20** `update_task_config` / `update_config` 未排除 `id` 字段：请求体可篡改主键。
3. **P1-13** `get_media_items` 和 `record_service` 的 `sort_by` 参数无白名单校验：可注入任意 `MediaItem`/`TransRecords` 属性。
4. **P1-12** `celery_clean_others` 基于内存 `done_list` 删除文件，路径差异/并发/异常均可导致误删。
5. **P1-14** WebSocket JWT 通过 URL 查询参数传递，会出现在服务器日志、浏览器历史、Referer 头中。

## What Changes

- **P2-15**：`config.py` 中 `MAX_CONCURRENT_TASKS` 改为 `int(os.environ.get("MAX_CONCURRENT_TASKS", "5"))`。
- **P2-20**：`task_config.py` 和 `scraping_config.py` 的 `update_*` 端点中 `model_dump(exclude_unset=True)` 改为 `model_dump(exclude_unset=True, exclude={"id"})`。
- **P1-13**：
  - `mediaitem.py` 中 `sort_by` 参数添加白名单校验 `ALLOWED_SORT_FIELDS`。
  - `record_service.py` 中 `sort_by` 参数添加白名单校验。
- **P1-12**：`celery_clean_others` 改为基于 `TransRecords` 表中 `output_folder` 下的成功记录查询，而非内存中的 `done_list`。
- **P1-14**：
  - 后端：`logs.py` WebSocket 端点改为从第一条消息接收 token（移除 URL Query 参数），或保持 Query 但后端仅在建立时使用（URL 仍泄露，但比放在永久 URL 中好——实际上最安全的方案是第一条消息认证）。
  - 前端：`Logs.vue` 改为先建立 WS 连接，再发送 `{type: "auth", token: "..."}` 认证消息。

## Capabilities

### New Capabilities

- `input-validation`：API 参数的白名单校验（排序字段、主键一致性）。

### Modified Capabilities

- `data-safety`：清理任务的安全性，从内存列表改为数据库记录。
- `ws-auth`：WebSocket 认证方式。

## Impact

- **向后兼容**：排序字段白名单拒绝未知字段返回 400（之前返回默认排序），前端需使用合法字段名。
- **非目标**：不重构 P1-8（Celery 嵌套 get）、P1-10（WS 日志监控）、P2-16（WatchHistory user_id）。
