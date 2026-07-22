# Spec: Input Validation

## Purpose

确保 API 参数经过类型安全和白名单校验，防止属性注入和不一致行为。

## Requirements

### R1 · sort_by 白名单校验

所有接受 `sort_by` 参数的 API 端点 SHALL 对非法值返回 `HTTPException(400)`，不得静默回退到默认值。

**受影响端点**：
- `mediaitem.py`：`_ALLOWED_SORT_FIELDS_MEDIAITEM` 白名单
- `metadata.py`：`_ALLOWED_SORT_FIELDS_METADATA` 白名单
- `record_service.py`：`_ALLOWED_SORT_FIELDS_RECORDS` 白名单

#### Scenario: 非法 sort_by 返回 400
- **GIVEN** 调用任意支持 `sort_by` 的 API，传入 `sort_by=invalid_field`
- **WHEN** `sort_by` 不在对应白名单中
- **THEN** 返回 `HTTP 400`，body 含 `"无效排序字段: invalid_field"`
- **AND** 不返回默认排序结果

#### Scenario: 合法 sort_by 正常工作
- **GIVEN** 调用记录列表 API，`sort_by=createtime`
- **WHEN** `sort_by` 在白名单中
- **THEN** 按 `createtime` 排序返回结果
