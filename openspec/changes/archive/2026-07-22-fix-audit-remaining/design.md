## Context

批次 1/2 的安全修复已消除 P0 和主要 P1/P2 问题。审计验证阶段发现 3 处实现细节问题：sort_by 行为不一致、clean_others 路径规范化不足、SECRET_KEY 锁超时过短。

## Goals / Non-Goals

**Goals:**
- 统一 `sort_by` 非法值的拒绝行为（全部返回 400）。
- 消除 clean_others 因路径规范化差异导致的误删风险。
- 提升 SECRET_KEY 并发生成的可靠性。

**Non-Goals:**
- 不重写 sort_by 白名单机制（已工作正常）。
- 不重构 clean_others 架构（基于 DB 查询的方案已正确）。
- 不修改 P1-8、P1-10、P2-16。

## Decisions

### D1 · sort_by 统一抛 400

`record_service.py:80` 的静默回退改为 `raise HTTPException(400)`，与 `mediaitem.py:109` 和 `metadata.py:71` 一致。

```python
# Before:
if sort_by not in _ALLOWED_SORT_FIELDS_RECORDS:
    sort_by = "updatetime"  # 静默回退

# After:
if sort_by not in _ALLOWED_SORT_FIELDS_RECORDS:
    raise HTTPException(status_code=400, detail=f"无效排序字段: {sort_by}")
```

**理由**：行为一致性。静默回退让用户以为排序生效实际没有，是隐式 bug。

### D2 · clean_others 路径规范化

比较前对两侧路径统一 `os.path.normcase(os.path.realpath(os.path.normpath()))`。

```python
# Before:
known_paths = {r.destpath for r in records}
real_dest = os.path.realpath(dest)
if real_dest not in known_paths and dest not in known_paths:

# After:
def _normalize(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.normpath(p)))

known_paths = {_normalize(r.destpath) for r in records}
norm_dest = _normalize(dest)
if norm_dest not in known_paths:
```

**理由**：`normpath` 消除 `./`/`//` 差异，`realpath` 解析符号链接，`normcase` 统一大小写（Windows）。三者组合覆盖所有常见路径差异。

### D3 · SECRET_KEY 锁超时增强

锁等待从 20×0.1s（2s）增加到 50×0.2s（10s）。添加僵尸锁清理：若锁文件存在超过 30 秒，视为僵尸锁删除后重新获取。

```python
# 锁等待
for _ in range(50):
    time.sleep(0.2)
    ...

# 僵尸锁清理
if os.path.exists(lock_path):
    lock_age = time.time() - os.path.getmtime(lock_path)
    if lock_age > 30:
        os.remove(lock_path)  # 僵尸锁，删除后重试
```

**理由**：2 秒对 SMB/NFS 不够。僵尸锁清理防止进程崩溃后锁文件残留导致永久阻塞。

## Risks / Trade-offs

- **sort_by 400**：前端如传入未列入白名单的字段会收到 400。已验证前端使用 `createtime`/`updatetime`，均在白名单中。
- **路径规范化**：`os.path.realpath` 会解析符号链接，如果 DB 存储的是符号链接路径而实际文件在真实路径下，规范化后能正确匹配。但若符号链接指向不同挂载点，`realpath` 可能产生意外路径。风险极低。
- **僵尸锁清理**：30 秒阈值是经验值。极端慢速 I/O 下可能误删活跃锁。但 `O_EXCL` 的原子性保证了即使误删，重新创建锁的进程也能正确写入。
