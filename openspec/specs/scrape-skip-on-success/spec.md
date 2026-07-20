# Scrape Skip On Success Specification

## Purpose

允许任务配置在自动扫描时跳过已经成功刮削的记录，避免重复刮削；并在重试路径下强制重新刮削。

## Requirements

### Requirement: TransferConfig 新增 skip_on_success 字段
`TransferConfig` 模型 SHALL 新增字段 `skip_on_success: Boolean`，默认值为 `True`，`server_default='1'`。该字段 SHALL 通过 Alembic 迁移添加到 `transferconfig` 表。

`TransferConfigPublic` schema SHALL 包含 `skip_on_success: bool = True` 字段。`TransferConfigDetailForm.vue` SHALL 在表单中提供 `v-switch` 控件允许用户修改此字段，label 文案 SHALL 为"扫描时跳过已刮削的记录"。

#### Scenario: 新建任务时的默认值
- **WHEN** 用户创建一个新的 TransferConfig 且未指定 `skip_on_success`
- **THEN** 数据库中的 `skip_on_success` 字段 SHALL 为 `True`

#### Scenario: 任务编辑表单展示开关
- **WHEN** 用户打开任务的编辑表单
- **THEN** 表单中 SHALL 显示 `v-switch` 控件，状态反映当前 `skip_on_success` 值，用户可切换并保存

#### Scenario: 数据库迁移向后兼容
- **WHEN** 已部署实例执行迁移添加 `skip_on_success` 字段
- **THEN** 所有现有 TransferConfig 记录 SHALL 通过 `server_default='1'` 自动获得 `True` 值，无需手动回填

### Requirement: celery_transfer_group 跳过已成功记录
`celery_transfer_group` 任务在遍历 `waiting_list` 时，对于每一条已存在的 `record`，当满足以下全部条件时 SHALL 跳过该记录的处理：
1. `force_refresh == False`
2. `task_info.skip_on_success == True`
3. `record.success IS TRUE`
4. `record.ignored == False`

跳过时 SHALL 通过 `logger.info` 记录跳过原因（包含文件名与"已成功"字样），且 SHALL NOT 修改 record 的任何字段、SHALL NOT 调用 `celery_scrapping`、SHALL NOT 将该文件加入 `done_list`。

当 `force_refresh == True`（重试路径）时，SHALL 永远不应用跳过逻辑，即使 `skip_on_success == True`。

#### Scenario: 自动扫描跳过已成功记录
- **WHEN** `celery_transfer_group` 以 `force_refresh=False` 调用，`task_info.skip_on_success=True`，且某 record 的 `success=True`
- **THEN** 任务 SHALL 跳过该 record，日志输出包含文件名与"已成功"字样，record 字段保持不变

#### Scenario: 重试路径不跳过
- **WHEN** `celery_transfer_group` 以 `force_refresh=True` 调用（如来自 `POST /api/v1/records/retry` 或 `POST /tasks/run/{id}` with path）
- **THEN** 任务 SHALL 永远不跳过 `success=True` 的 record，即使 `skip_on_success=True`

#### Scenario: 任务关闭开关时全量扫描
- **WHEN** `celery_transfer_group` 以 `force_refresh=False` 调用，`task_info.skip_on_success=False`
- **THEN** 任务 SHALL 处理所有非 ignored 的 record，包括 `success=True` 的（行为与现状一致）

#### Scenario: 已忽略的记录始终跳过
- **WHEN** 某 record 的 `ignored=True`，无论 `skip_on_success` 与 `force_refresh` 取值
- **THEN** 任务 SHALL 因现有的 `ignored` 检查跳过该 record（不进入 `skip_on_success` 判断逻辑）
