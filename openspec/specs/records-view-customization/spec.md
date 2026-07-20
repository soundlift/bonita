# Records View Customization Specification

## Purpose

定义 Records 页面的后端过滤能力与前端视图定制项（可见列、排序、分页等）。

## Requirements

### Requirement: 后端 SHALL 支持按 success 字段过滤记录

`GET /api/v1/records/all` 端点 SHALL 接受 `success` 查询参数（`Optional[bool]`，默认 `None`）。当 `success` 为 `None` 时 SHALL 不应用状态过滤。当 `success` 为 `True` 时 SHALL 只返回 `transfer_record.success == True` 的记录。当 `success` 为 `False` 时 SHALL 只返回 `transfer_record.success != True` 的记录（即 `False` 与 `NULL`/中断记录）。`record_service.get_records()` 的 count 查询 SHALL 同步应用此过滤条件，确保分页总数正确。

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all` 且未提供 `success` 查询参数
- **THEN** 返回的记录 SHALL 包含所有状态（成功、失败、中断），行为与当前版本完全一致（向后兼容）

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all?success=true`
- **THEN** 返回的记录 SHALL 只包含 `transfer_record.success == True` 的记录，`count` 字段 SHALL 反映过滤后的总数

#### Scenario: WHEN 客户端调用 `GET /api/v1/records/all?success=false`
- **THEN** 返回的记录 SHALL 同时包含 `transfer_record.success == False` 与 `transfer_record.success IS NULL` 的记录（即所有 `success IS NOT TRUE` 的记录），`count` 字段 SHALL 反映这两类的总数
