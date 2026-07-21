## Context

`TransRecords.success` 字段在数据库中定义为 `Boolean`（SQLAlchemy `Column(Boolean, default=False)`），但实际运行中存在 `NULL` 值。这是因为 `celery_transfer_group`（`celery_tasks/tasks.py`）在开始处理每个文件时执行 `record.success = None`（第 193 行）表示"进行中"，随后在成功时设为 `True`（第 343 行）、在刮削/配置失败时设为 `False`（第 199、206 行）。但如果在 `success=None` 之后、成功/失败判定之前发生未预期的异常，第 344 行的 `except` 块只记日志就 `commit` 了，`success` 保持 `None` 被持久化。

当前 Records 页面的状态筛选（`records-view-customization` change 引入）使用 `success == False` 精确匹配，漏掉了这些 `NULL` 记录。前端状态列模板用 `v-if="item.transfer_record.success !== null"` 判断，`null` 时不渲染任何 chip，显示为空白。

## Goals / Non-Goals

**Goals:**

- 异常中断的记录被正确标记为失败（`success = False`），不再遗留 `NULL`
- "失败"筛选包含 `NULL` 状态的记录（语义为"未成功"）
- 前端能辨识 `NULL` 状态记录，与普通失败有视觉区分（"中断" vs "失败"）

**Non-Goals:**

- 不做历史 `NULL` 数据的批量修复迁移（用户可通过筛选"失败"找到这些记录后手动重试）
- 不修改 `success` 字段的数据库定义（不改 schema、不加 migration）
- 不修改 `ignored` 记录的处理逻辑（`ignored=True` 的记录 `continue` 时 `success` 保持 `None` 是预期行为——被忽略的记录本身不应显示为失败）

## Decisions

### 决策 1：`except` 块中设置 `record.success = False`

**选择**: 在 `celery_transfer_group` 的 `except Exception as e:` 块（约第 344 行）中，在 `logger.error(e)` 之后，将当前循环变量 `record` 的 `success` 设为 `False`。

**理由**: 异常意味着处理未成功完成，`success` 应反映这个事实。`finally` 块的 `session.commit()` 会将这个值持久化。需要确认 `record` 变量在 `except` 作用域中可访问——当前代码结构中 `record` 在 `for` 循环内定义（第 180-186 行），`try` 块在 `for` 循环内（第 165 行的 `try` 对齐缩进与 `for` 相同），因此 `except` 可以访问到当前迭代的 `record`。但如果异常发生在 `record` 赋值之前（如 `session = SessionFactory()` 失败），`record` 可能未定义，需要用 `try/except` 或 `locals().get('record')` 保护。

**备选方案**: 在 `finally` 块中检查 `record.success is None` 则设为 `False`——但 `finally` 在正常成功路径也会执行，此时 `success` 已为 `True`，不会有干扰。不过 `finally` 块无法区分"正常完成但某些子步骤用了 continue 跳过"的情况（如 `ignored` 记录），可能导致 `ignored` 记录被误设为 `False`。因此选择在 `except` 块中设置更精确。

### 决策 2：后端筛选 `success=False` 改为 `success IS NOT True`

**选择**: `record_service.get_records()` 中，当 `success` 参数为 `False` 时，过滤条件从 `TransRecords.success == False` 改为 `TransRecords.success != True`（SQLAlchemy 会生成 `success IS NOT 1` / `success != true`，覆盖 `False` 和 `NULL`）。`success=True` 时保持 `TransRecords.success == True`。

**理由**: 用户筛选"失败"的意图是"找出没成功的记录"，`NULL`（中断）本质上是失败的一种。使用 `!= True` 可以同时匹配 `False` 和 `NULL`，符合用户预期。

**备选方案**: 使用 `or_(TransRecords.success == False, TransRecords.success.is_(None))` 显式写两个条件——语义更清晰但代码更长。`!= True` 更简洁，在 SQLite/PostgreSQL 上行为一致。选择简洁方案。

### 决策 3：前端 `null` 状态显示"中断"图标

**选择**: Records 页面状态列模板中，`success === null` 时显示灰色警告 chip（`mdi-alert` 图标，`color="grey"`），与成功（绿色 `bx-check`）和失败（红色 `bx-x`）三者区分。

**理由**: 虽然 `NULL` 在筛选时归入"失败"，但视觉上区分"中断"和"失败"有助于用户理解记录的状态——中断的记录可能是 worker 崩溃导致的，重试成功率更高；失败的记录可能是刮削配置问题，需要先修复配置。

## Risks / Trade-offs

- **[except 块中 record 变量可能未定义]** 如果异常发生在 `record` 赋值之前（第 180-186 行之前），`except` 中访问 `record` 会抛 `NameError`。需在 `except` 块中用 `locals().get('record')` 或检查 `record` 是否存在再赋值。
- **[!= True 在不同数据库的行为]** SQLAlchemy 的 `!= True` 对 `NULL` 的处理依赖数据库三值逻辑。SQLite 中 `NULL != 1` 返回 `NULL`（不被 `WHERE` 选中），需要用 `or_(col == False, col.is_(None))` 才能正确包含 `NULL`。**这一点需要在实现时验证，可能需要改用显式 `or_` 写法。**
- **[向后兼容]** 已有 `NULL` 数据不会被自动修复。用户筛选"失败"可以看到这些记录（修复后），然后手动重试或删除。
