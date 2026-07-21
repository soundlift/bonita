## Context

当前单文件处理流程（`celery_transfer_group` for 循环体内）是**线性串行**的，没有任何事务边界：

```
[现状]
  解析 record
    ↓
  刮削（网络）→ metadata_mixed
    ↓
  process_nfo_file  ← 直接写目标目录
  process_cover     ← 直接写目标目录，失败仅 warning
    ↓
  transSingleFile → shutil.move(src, dst)   ← 源文件消失
    ↓
  record.destpath = dst
  record.deleted = False
  record.success = True
    ↓
  session.commit()
```

破坏点在于 **`shutil.move` 之后零校验**：

- `shutil.move` 同卷是 `os.rename`（原子），跨卷退化为 copy+unlink。跨卷 copy 中途失败时 unlink 被跳过、源保留——**这部分本身是安全的**。
- 但异常被 `tasks.py:357` 的 `except Exception` 吞，只 `record.success = False`，**不校验目标文件状态、不清理半成品、不确认源文件去向**。
- 如果 move 看似成功（无异常抛出）但目标文件实际不完整（NFS 缓存延迟、SMB 静默丢失等），当前流程照常标记 `success = True`，用户以为成功。

## Goals / Non-goals

**Goals:**
- `transSingleFile` 返回后、标记 success 前，校验目标文件存在 + 字节数一致
- 校验失败时清理半成品目标文件、保留源文件（若还在）、`record.success = False`
- NFO 写入失败（本地 I/O 错）阻断 move，封面失败不阻断
- 引入显式状态机让失败处理有确定性
- 前端明确告知 MOVE 的破坏性

**Non-goals:**
- 不改 `shutil.move` / `linkFile` 的实现（它们本身是安全的）
- 不处理 Celery worker 进程被 kill 的崩溃恢复（文件已正确，monitor 会自愈）
- 不改造 HARD_LINK/SYMLINK/COPY 三种模式（源不被破坏，天然安全）
- 不引入分布式事务或持久化事务日志（SQLite 单库，进程内状态机足够）
- 不解决 monitor 模块的 `startswith` 前缀匹配陷阱（独立 bug）
- 不引入多文件分组刮削（CD1/CD2，已确认为独立 proposal）

## Decisions

### 决策 1: 保留 shutil.move，verify 加在调用层

**选择**: `OperationMethod.MOVE` 继续走 `shutil.move`（同卷 os.rename 原子、跨卷 copy+unlink 安全）。在 `celery_transfer_group` 调用 `transSingleFile` 之后、标记 `success = True` 之前，插入 verify 步骤：

```python
# 伪代码
destpath = transSingleFile(...)              # shutil.move 内部完成
if not verify_transfer(destpath, expected_size):
    rollback_transfer(destpath)              # 清理半成品
    record.success = False
    continue
record.destpath = destpath
record.success = True
```

`verify_transfer(dst, expected_size)` 校验：`os.path.exists(dst)` and `os.path.getsize(dst) == expected_size`。

**理由**:
- `shutil.move` 的跨卷退化本身是安全的——`copy2` 成功才执行 `unlink`，copy 中途失败则源保留。问题不在 move 本身，而在调用方不做事后校验。
- 同卷 `os.rename` 是原子操作，几乎不会出现"返回成功但文件不完整"——但 NFS/SMB 挂载下仍有静默丢失的罕见案例，verify 是低成本保险。
- 跨卷 copy 在网络挂载场景可能因超时产生不完整文件，verify 能捕获。
- 字节数校验成本极低（一次 stat），不增加可感知的耗时。

**备选方案（否决）**:
- 改用 `os.rename` 拒绝跨卷：用户体验倒退，很多用户的 source/output 本就在不同卷。
- 用 hash 校验：大文件全量读成本不可接受。
- 改 `shutil.move` 源码：维护负担且无必要。

### 决策 2: 状态机五阶段 + 回滚动作

**选择**: 单文件处理流程显式建模为五个状态，每个阶段失败有明确动作：

```
┌─────────────────────────────────────────────────────────────────┐
│                    转移事务状态机                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PENDING ──▶ AUX_READY ──▶ TRANSFERRED ──▶ VERIFIED ──▶ COMMITTED│
│    │            │              │              │                 │
│    │ 刮削失败    │ NFO写失败     │ move异常     │ verify失败      │
│    ▼            ▼              ▼              ▼                 │
│  [保留源]    [清理产物]      [异常向上抛]   [清理目标+保留源]    │
│  success=F   [保留源]        except处理     success=F           │
│              success=F                                         │
│                                                                 │
│  TRANSFERRED 阶段 move 异常：shutil.move 失败时源天然保留，      │
│  走原有 except Exception → record.success=False 即可            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

| 状态 | 进入条件 | 失败回滚 |
|---|---|---|
| PENDING | record 加载完成 | 无（尚未动文件），`record.success = False` |
| AUX_READY | 刮削完成 + NFO 已写入目标目录 | 清理本次写入的 NFO（按 number filter），保留源，`record.success = False` |
| TRANSFERRED | `transSingleFile`（含 shutil.move）成功返回 | move 抛异常时源大概率保留（shutil 语义），走 except 块标记失败 |
| VERIFIED | `verify_transfer` 通过 | 删除目标半成品，`record.success = False` |
| COMMITTED | record 字段更新 + `session.commit()` | 不回滚（文件已正确，DB 状态最多滞后，monitor 自愈） |

**理由**: 状态机让失败处理有确定性，不再是"异常被吞，文件状态听天由命"。

### 决策 3: NFO 前置写入，封面失败不阻断

**选择**: NFO 在 move 源文件**之前**写入目标目录。NFO 写入失败 → 阻断 move（本地 I/O 失败说明目录不可写，move 过去也会失败）。封面下载失败 → 不阻断（网络资源，失败率高）。

**理由**: NFO 是纯本地 I/O，失败意味着目标目录不可写；封面是网络资源，失败不应阻断本地操作。

### 决策 4: 回滚时的文件清理粒度

**选择**: 回滚时按 `destpath` 的 basename（不含扩展名）作为 filter 清理目标目录下所有匹配文件。复用现有 `cleanFilebyFilter(clean_folder, name_filter)`。

### 决策 5: 前端 MOVE 风险提示形态

**选择**: `TransferConfigDetailForm.vue` 的操作方式 `VRadioGroup`（inline）下，当 `currentTask.operation === 3`（MOVE）时，在选择器下方渲染警告色说明文字。文案明确："移动模式会删除源文件，若转移过程中刮削或磁盘出错，源文件可能不可恢复。建议优先使用硬链接。"

i18n key: `components.task.form.moveWarning`。

## Risks / Trade-offs

- **[verify 字节数不够严格]**: 罕见的静默 bit rot 不会被字节数检测到。→ 概率极低，shutil 本身有校验；引入 hash 成本不值得。
- **[状态机复杂度]**: 五状态比线性流程难读。→ 用注释 + 阶段分隔 + 回滚辅助函数让代码自文档化。
- **[worker 崩溃留下中间态]**: 进程被 kill 时可能"已 move 但 record 未 commit"。→ 文件已正确，monitor 扫到会自愈；记录为已知限制。
- **[封面失败不阻断]**: 用户可能得到无封面的转移结果。→ 与现有行为一致，封面本就是尽力而为；record 状态只反映转移本身。
