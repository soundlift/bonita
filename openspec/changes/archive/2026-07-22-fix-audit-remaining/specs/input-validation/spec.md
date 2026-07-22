# Delta Spec: input-validation

> 基线: `openspec/specs/` 中无独立 `input-validation` spec（能力分散在多个 change 中）

## MODIFIED Requirements

### R1 · sort_by 白名单校验行为统一（更新）

所有接受 `sort_by` 参数的 API 端点 SHALL 对非法值返回 `HTTPException(400)`，不得静默回退到默认值。

**受影响端点**：
- `mediaitem.py`：已返回 400 ✅
- `metadata.py`：已返回 400 ✅
- `record_service.py`：静默回退 → 改为 400 ❌

#### Scenario: record_service 非法 sort_by 返回 400
- **GIVEN** 调用记录列表 API，`sort_by=invalid_field`
- **WHEN** `sort_by` 不在 `_ALLOWED_SORT_FIELDS_RECORDS` 白名单中
- **THEN** 返回 `HTTP 400`，body 含 `"无效排序字段: invalid_field"`
- **AND** 不返回默认排序结果

#### Scenario: record_service 合法 sort_by 正常工作
- **GIVEN** 调用记录列表 API，`sort_by=createtime`
- **WHEN** `sort_by` 在白名单中
- **THEN** 按 `createtime` 排序返回结果
