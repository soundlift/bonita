## ADDED Requirements

### Requirement: 转移完成后 SHALL 校验目标文件完整性

`celery_transfer_group` 在调用 `transSingleFile` 返回后、设置 `record.success = True` 之前，SHALL 调用 `verify_transfer(destpath, expected_size)` 校验目标文件。校验维度为：`os.path.exists(destpath)` 且 `os.path.getsize(destpath) == expected_size`。其中 `expected_size` SHALL 为转移前源文件的大小（由 `record.filesize` 或转移前 `os.path.getsize(srcpath)` 提供）。

校验失败 SHALL 执行回滚（清理半成品目标文件）、设置 `record.success = False`，不进入 COMMITTED 阶段。

其他三种 `OperationMethod`（HARD_LINK / SYMLINK / COPY）SHALL 同样执行该校验——成本极低且能捕获网络挂载的静默丢失。

#### Scenario: 转移成功且 verify 通过

- **WHEN** `transSingleFile` 成功返回 destpath，且 `os.path.exists(destpath)` 为 True，且 `os.path.getsize(destpath) == expected_size`
- **THEN** 流程 SHALL 设置 `record.destpath = destpath`、`record.success = True`，进入 COMMITTED 阶段

#### Scenario: 转移后目标文件不存在

- **WHEN** `transSingleFile` 返回 destpath，但 `os.path.exists(destpath)` 为 False
- **THEN** 流程 SHALL 执行回滚（清理可能残留的半成品），设置 `record.success = False`，不更新 `record.destpath`

#### Scenario: 转移后目标文件大小不一致

- **WHEN** `transSingleFile` 返回 destpath，目标文件存在，但 `os.path.getsize(destpath) != expected_size`
- **THEN** 流程 SHALL 执行回滚（删除大小不一致的目标文件），设置 `record.success = False`

### Requirement: celery_transfer_group 单文件处理 SHALL 实现转移事务状态机

`celery_transfer_group` 的 for 循环内单文件处理流程 SHALL 显式经过五个状态阶段：`PENDING → AUX_READY → TRANSFERRED → VERIFIED → COMMITTED`。每个阶段失败时 SHALL 执行对应的回滚动作：

| 阶段 | 失败回滚动作 |
|---|---|
| PENDING → AUX_READY | 无（保留源文件），`record.success = False` |
| AUX_READY → TRANSFERRED | 清理本次写入目标目录的 NFO 产物，保留源文件，`record.success = False` |
| TRANSFERRED → VERIFIED | `transSingleFile` 抛异常时走 except 块；shutil.move 失败时源天然保留 |
| VERIFIED → COMMITTED | 删除目标半成品文件，`record.success = False` |

`COMMITTED` 阶段（record 字段更新 + session.commit）失败 SHALL 不回滚文件操作——此时文件状态已正确，仅 DB 状态可能滞后，下次 monitor 扫描会自愈。

#### Scenario: 刮削阶段失败保留源文件

- **WHEN** `celery_scrapping` 返回 None（刮削失败）或抛出异常
- **THEN** 流程 SHALL 停在 PENDING 阶段，不执行任何文件移动，`record.success = False`，源文件保留

#### Scenario: NFO 写入失败阻断转移

- **WHEN** `process_nfo_file` 因目标目录不可写抛出异常
- **THEN** 流程 SHALL 停在进入 AUX_READY 前，保留源文件，`record.success = False`，不调用 `transSingleFile`

#### Scenario: transSingleFile 抛异常

- **WHEN** `transSingleFile`（含 shutil.move）抛出 OSError 或其他异常
- **THEN** 流程 SHALL 走 except 块，`record.success = False`；shutil.move 失败时源文件天然保留

#### Scenario: verify 阶段失败回滚

- **WHEN** 状态进入 TRANSFERRED 后 `verify_transfer` 校验不通过（文件不存在或大小不一致）
- **THEN** 回滚 SHALL 删除目标半成品文件，`record.success = False`

#### Scenario: 全流程成功进入 COMMITTED

- **WHEN** transfer + verify 全部成功，record 字段更新并 commit 成功
- **THEN** 状态 SHALL 进入 COMMITTED，`record.success = True`，`record.deleted = False`

### Requirement: NFO 写入失败 SHALL 阻断转移

当 `TransferConfig.sc_enabled == True` 时，`process_nfo_file` 写入目标目录 SHALL 在源文件 transfer 之前完成。若 NFO 写入抛出异常（磁盘满、权限错、路径无效），流程 SHALL 阻断后续的 `transSingleFile`，保留源文件。

封面图片（`process_cover`）失败 SHALL NOT 阻断转移——封面是外部网络资源，失败率高，仅记录 warning 日志，允许文件继续转移。

#### Scenario: NFO 写入失败阻断

- **WHEN** `process_nfo_file(output_folder, ...)` 抛出 OSError（目录不可写）
- **THEN** 流程 SHALL 不调用 `transSingleFile`，源文件保留，`record.success = False`

#### Scenario: 封面下载失败不阻断

- **WHEN** `process_cover` 返回空列表或封面下载失败
- **THEN** 流程 SHALL 记录 warning 日志，继续执行 `transSingleFile`，`record.success` 按转移 + verify 结果设置

### Requirement: 回滚 SHALL 清理目标目录的半成品文件

状态机任一阶段失败时，若目标目录已写入文件（NFO/视频半成品），回滚 SHALL 调用 `cleanFilebyFilter(clean_folder, name_filter)` 清理以本次目标 basename 为 filter 的所有关联文件（视频本体 + .nfo + 封面图）。清理失败 SHALL 记录 error 日志但不影响 `record.success` 的设置（已设为 False）。

#### Scenario: 回滚清理半成品目标文件

- **WHEN** VERIFIED 阶段失败，目标目录已存在大小不一致的视频文件
- **THEN** 回滚 SHALL 调用 `cleanFilebyFilter` 清理该 basename 对应的视频及关联文件

#### Scenario: 回滚时清理本身失败

- **WHEN** 回滚调用 `cleanFilebyFilter` 时目标目录已不可访问（网络挂载掉线）
- **THEN** 流程 SHALL 记录 error 日志，不抛出二次异常，`record.success` 保持 False

## ADDED Requirements

### Requirement: celery_transfer_group SHALL 支持 force_refresh 参数实现完全重新开始

`celery_transfer_group` 任务 SHALL 新增 `force_refresh: bool = False` 参数。当 `force_refresh=True` 时，任务 SHALL 在处理每个文件前无条件删除该记录已有的 `destpath` 指向的目标文件（若文件存在），然后将 `force_refresh` 透传给 `celery_scrapping` 任务。

**修改约束**: force_refresh 流程同样受新的转移事务状态机约束。刷新时删除旧 destpath 后，若新的 transfer + verify 流程失败，SHALL 进入状态机的对应回滚阶段（清理半成品、保留源文件），而非当前的"文件状态不明但 record 标记失败"行为。

当 `force_refresh=False` 时（默认），行为 SHALL 引入新的 verify 校验和回滚保护，不影响 monitor 自动入库的成功路径。

#### Scenario: force_refresh 时新转移 verify 失败

- **WHEN** `celery_transfer_group` 以 `force_refresh=True` 调用，旧 destpath 已被删除，新的 transfer + verify 在 verify 阶段失败
- **THEN** 状态机 SHALL 回滚（清理半成品目标），`record.success = False`；用户可重新触发重试
