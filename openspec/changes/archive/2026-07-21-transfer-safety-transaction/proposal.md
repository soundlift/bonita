## Why

当前 `celery_transfer_group` 在 `operation=MOVE` + 刮削模式下存在数据丢失风险：`shutil.move(src, dst)` 执行后流程对"目标文件是否真的写成功""源文件是否还在"**零校验**，异常被 `except Exception` 吞掉后只标记 `record.success = False`，文件状态听天由命。

具体缺陷链（`backend/bonita/celery_tasks/tasks.py` + `backend/bonita/modules/transfer/transfer.py`）：

1. `transSingleFile` → `linkFile(..., MOVE)` → `shutil.move` 后只返回"期望路径"，**不校验 `os.path.exists(destpath)`，不比对文件大小**。
2. 刮削产物（NFO/封面）失败时仅 `logger.warning` 跳过，**不影响后续 move**，用户得到一个"元数据残缺但源文件已被搬走"的结果。
3. `tasks.py:357` 的 `except Exception` 是裸捕获，**无 rollback 语义**：若异常发生在 move 之后、commit 之前，源已不在、目标可能不完整、record 状态对不上，下次 `get_records_to_cleanup` 扫到 `srcdeleted` 会把它当孤儿清理。
4. 前端 `TransferConfigDetailForm.vue` 的操作方式选项（硬链接/软链接/移动/复制）**并列展示无风险提示**，用户无法预知 MOVE 的破坏性。

## What Changes

- **NEW（校验层）**: `celery_transfer_group` 单文件处理流程 SHALL 在 `transSingleFile` 调用后、设置 `record.success = True` 前，执行 transfer verify：校验 `os.path.exists(destpath)` 且 `os.path.getsize(destpath)` 与源文件大小一致（源已 move 的情况）或与预期大小一致。verify 失败 SHALL 执行回滚（清理半成品目标文件 + 标记 `record.success = False`）。
- **NEW（状态机层）**: 单文件处理流程 SHALL 引入显式的转移事务状态：`PENDING → AUX_READY → TRANSFERRED → VERIFIED → COMMITTED`，每个阶段失败时 SHALL 执行对应的回滚动作。
- **NEW（NFO 前置）**: 刮削模式下，NFO 写入 SHALL 在源文件 move 之前完成；NFO 写入失败 SHALL 阻断 move（本地 I/O 失败说明目录不可写）。封面下载失败 SHALL NOT 阻断转移。
- **NEW（前端层）**: `TransferConfigDetailForm.vue` 的操作方式选择器 SHALL 对"移动"选项展示风险提示；i18n 中文/英文 SHALL 同步。
- **保持不变**: `shutil.move` 本身的实现不改（它跨卷退化为 copy+unlink 是安全的——copy 成功才 unlink，失败保留源）。`HARD_LINK` / `SYMLINK` / `COPY` 三种模式保持现有行为。

## Capabilities

### New Capabilities
- `transfer-transaction-safety`: 覆盖 `celery_transfer_group` 单文件处理流程的事务状态机、transfer 后的 verify 校验、NFO 前置写入、失败回滚契约。

### Modified Capabilities
- `task-rerun-refresh`: force_refresh 流程同样受新事务语义约束——刷新时删除旧 destpath 后若新转移 verify 失败，SHALL 进入回滚状态。
- `task-config-form`（新增 delta 约束）: 操作方式选择器对 MOVE 选项的风险提示。

## Impact

- **后端核心改动**:
  - `backend/bonita/modules/transfer/transfer.py`：新增 `verify_transfer` / `TransferVerifyError`；`transSingleFile` 返回后由调用方校验。
  - `backend/bonita/celery_tasks/tasks.py`：`celery_transfer_group` 单文件 for 循环重构为状态机；NFO 写入前置到 move 之前。
  - `backend/bonita/utils/filehelper.py`：无改动（`linkFile` 保持原样）。
- **前端**: `frontend/src/components/task/TransferConfigDetailForm.vue`（操作方式选项风险提示）、`frontend/src/plugins/i18n/locales/{zh,en}.ts`。
- **外部副作用**: MOVE 模式多一次 getsize 校验（微秒级，可忽略）；verify 失败时会删除半成品目标文件。
- **风险**:
  - verify 用字节数一致性而非 hash：大文件全量 hash 成本不可接受；字节数 + shutil 无异常返回已覆盖绝大多数失败场景。
  - 状态机引入中间状态，若 Celery worker 进程被 kill，可能留下"已 move 但 record 未 commit"——此场景文件已正确，下次 monitor 扫到会自愈（已知限制）。
- **向后兼容**: `OperationMethod` 枚举值不变，API 契约不变；所有模式的成功路径外部可观察结果不变，只是失败路径多了回滚保护。
