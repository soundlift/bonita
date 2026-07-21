## Context

批次 1/2 已修复 P0 安全链和主要 P1 基础设施问题。本批次处理 5 项剩余的输入校验和数据安全问题。

## Goals / Non-Goals

**Goals:**
- 所有 API 参数经过类型安全和白名单校验。
- 清理任务基于数据库记录而非内存列表。
- WebSocket 认证 token 不出现在 URL 中。

**Non-Goals:**
- 不处理 P1-8、P1-10、P2-16、P2-18。

## Decisions

### D1 · MAX_CONCURRENT_TASKS 类型修复

直接用 `int()` 包裹 `os.environ.get` 调用。

### D2 · update 端点 id 排除

`model_dump(exclude_unset=True, exclude={"id"})` — 最小改动，不影响其他字段。

### D3 · sort_by 白名单

```python
_ALLOWED_SORT_FIELDS = {"updatetime", "createtime", "title", "number", ...}
if sort_by not in _ALLOWED_SORT_FIELDS:
    raise HTTPException(400, f"无效排序字段: {sort_by}")
```

### D4 · clean_others 数据库查询

重写为：查询 `TransRecords` 中 `destpath` 以 `output_folder` 为前缀且 `success=True` 的记录，得到数据库中已知的成功文件集合。然后 `findAllFilesWithSuffix(root_path)` 中不在数据库集合的文件才删除。`done_list` 参数保留但降级为辅助日志（向后兼容）。

### D5 · WS token 从 URL 移到首条消息

后端：移除 `token: str = Query(None)` 参数，改为在 WS 连接建立后立即 `await websocket.receive_text()` 读取 JSON `{type: "auth", token: "..."}` 验证。超时 5 秒未认证则关闭连接。

前端：移除 URL 中的 `?token=...`，连接后 `ws.send(JSON.stringify({type: "auth", token}))`。

## Risks / Trade-offs

- **sort_by 白名单**：前端如使用未列入的字段名会收到 400。需要检查前端实际传入的字段。
- **WS 首条消息认证**：WebSocket 连接建立时不验证 token，短暂窗口期可被滥用。实际风险低——WS 连接在 auth 前不做任何业务操作。
- **clean_others 重写**：如果 `TransRecords` 中有脏数据（`destpath` 为空或错误），可能导致误删或漏删。增加 `destpath IS NOT NULL` 和 `destpath != ''` 过滤保护。
