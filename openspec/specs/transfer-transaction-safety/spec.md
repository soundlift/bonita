# transfer-transaction-safety Specification

## Purpose
TBD - created by archiving change transfer-safety-transaction. Update Purpose after archive.
## Requirements
### Requirement: celery_transfer_group SHALL 支持 force_refresh 参数实现完全重新开始

`celery_transfer_group` 任务 SHALL 新增 `force_refresh: bool = False` 参数。当 `force_refresh=True` 时，任务 SHALL 在处理每个文件前无条件删除该记录已有的 `destpath` 指向的目标文件（若文件存在），然后将 `force_refresh` 透传给 `celery_scrapping` 任务。

**修改约束**: force_refresh 流程同样受新的转移事务状态机约束。刷新时删除旧 destpath 后，若新的 transfer + verify 流程失败，SHALL 进入状态机的对应回滚阶段（清理半成品、保留源文件），而非当前的"文件状态不明但 record 标记失败"行为。

当 `force_refresh=False` 时（默认），行为 SHALL 引入新的 verify 校验和回滚保护，不影响 monitor 自动入库的成功路径。

#### Scenario: force_refresh 时新转移 verify 失败

- **WHEN** `celery_transfer_group` 以 `force_refresh=True` 调用，旧 destpath 已被删除，新的 transfer + verify 在 verify 阶段失败
- **THEN** 状态机 SHALL 回滚（清理半成品目标），`record.success = False`；用户可重新触发重试

