## 1. 后端：verify_transfer 辅助函数

- [x] 1.1 在 `backend/bonita/modules/transfer/transfer.py` 新增 `TransferVerifyError(Exception)` 异常类
- [x] 1.2 在 `backend/bonita/modules/transfer/transfer.py` 新增 `verify_transfer(destpath: str, expected_size: int) -> bool` 函数：校验 `os.path.exists(destpath)` and `os.path.getsize(destpath) == expected_size`；返回 False 时调用方应执行回滚

> 实现备注：`TransferVerifyError` 已定义但调用方目前通过 `verify_transfer` 返回值判断失败，未直接 raise 该异常。保留为后续硬失败语义扩展用。

## 2. 后端：转移事务状态机

- [x] 2.1 在 `backend/bonita/celery_tasks/tasks.py` 的 `celery_transfer_group` 单文件 for 循环内，用注释/分隔线标记五个状态阶段：`PENDING → AUX_READY → TRANSFERRED → VERIFIED → COMMITTED`
- [x] 2.2 PENDING 阶段：刮削调用失败（`celery_scrapping` 返回 None 或抛异常）SHALL `record.success = False; continue`，不进入文件操作
- [x] 2.3 进入 AUX_READY：将 `process_nfo_file` 调用移到 `transSingleFile` **之前**；NFO 写入抛异常 SHALL 阻断 `transSingleFile`，`record.success = False`，源文件保留
- [x] 2.4 封面处理（`process_cover`）保持现有位置和 warning-only 行为，失败不阻断
- [x] 2.5 TRANSFERRED → VERIFIED：`transSingleFile` 返回后，调用 `verify_transfer(destpath, record.filesize)`；校验失败 SHALL 执行回滚（调用 `rollback_transfer(destpath)`），`record.success = False`
- [x] 2.6 VERIFIED → COMMITTED：校验通过后更新 `record.destpath`、`record.deleted = False`、`record.success = True`，`session.commit()`
- [x] 2.7 重构 `except Exception` 块：保持标记 `record.success = False` 的行为，确保异常路径不遗漏 record 状态更新

## 3. 后端：回滚辅助函数

- [x] 3.1 在 `backend/bonita/celery_tasks/tasks.py` 新增 `_rollback_transfer(destpath: str)` 辅助函数：调用 `cleanFilebyFilter(os.path.dirname(destpath), os.path.splitext(os.path.basename(destpath))[0])`，异常仅记录 error 不抛出
- [x] 3.2 在状态机的 VERIFIED 失败分支、NFO 写入失败分支调用对应的回滚（NFO 失败回滚用相同的 cleanFilebyFilter 清理 NFO 文件）

> 实现备注：函数实际命名为 `rollback_transfer`（无下划线前缀），定义在 `backend/bonita/modules/transfer/transfer.py:39`。NFO 失败分支目前仅阻断并保留源文件，未调用 `rollback_transfer` 清理已写入的 NFO（因为 NFO 写入本身失败时无成功产物需清理）。

## 4. 前端：MOVE 风险提示

- [x] 4.1 在 `frontend/src/plugins/i18n/locales/zh.ts` 的 `components.task.form` 下新增 `moveWarning` key，文案："移动模式会删除源文件，若转移过程中刮削或磁盘出错，源文件可能不可恢复。建议优先使用硬链接。"
- [x] 4.2 在 `frontend/src/plugins/i18n/locales/en.ts` 同步新增 `moveWarning` key，英文文案语义一致
- [x] 4.3 在 `frontend/src/components/task/TransferConfigDetailForm.vue` 的操作方式 `VRadioGroup` 下方，当 `currentTask.operation === 3` 时渲染警告色说明文字（VAlert type="warning" 或 text-warning class），内容绑定 `t('components.task.form.moveWarning')`
- [x] 4.4 验证选中其他三种模式（1/2/4）时风险提示不显示

## 5. 验证

- [x] 5.1 验证 MOVE 同卷转移成功：源消失、目标存在、size 一致、`record.success = True`
- [x] 5.2 验证 MOVE 跨卷转移成功：shutil.move 退化为 copy+unlink，verify 通过，`record.success = True`
- [x] 5.3 模拟 verify 失败（destpath 不存在或 size 不一致）：目标半成品被清理、`record.success = False`、无未捕获异常
- [x] 5.4 模拟 NFO 写入失败（目标目录只读）：源文件保留、不调用 transSingleFile、`record.success = False`
- [x] 5.5 验证封面下载失败不阻断转移：文件正常 transfer + verify 通过、`record.success = True`、日志有 warning
- [x] 5.6 验证 HARD_LINK/SYMLINK/COPY 模式同样走 verify（回归 + 新增保护）
- [x] 5.7 验证 force_refresh 重试时新转移 verify 失败：半成品被清理、`record.success = False`、可重新触发重试
- [x] 5.8 验证前端：选中移动显示风险提示，选中其他模式不显示，中英文文案同步
- [x] 5.9 验证 monitor 自动入库（默认参数）行为正常
