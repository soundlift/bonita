## Why

审计验证阶段发现已修复代码存在 3 处遗留问题：

1. **P1-13 行为不一致**：`mediaitem.py` 和 `metadata.py` 的 `sort_by` 非法值返回 400，但 `record_service.py` 静默回退到 `updatetime`。同一非法参数在不同接口表现不同。
2. **clean_others 路径规范化差异**：DB 存储的 `destpath` 与文件系统扫描路径可能存在符号链接/大小写差异，双重检查(`realpath` + 原始路径)仍无法覆盖所有情况。
3. **PA-6 锁超时过短**：`_ensure_secret_key` 的锁等待仅 2 秒（20×0.1s），SMB/NFS 挂载场景下 YAML 写入可能超时，导致两进程密钥不一致。

## What Changes

- **P1-13**：`record_service.py` 的 `sort_by` 校验改为与 `mediaitem.py`/`metadata.py` 一致——非法值抛 `HTTPException(400)`。
- **clean_others**：将 DB 查询的 `destpath` 和扫描路径都通过 `os.path.normcase(os.path.realpath())` 规范化后再比较。
- **PA-6**：`_ensure_secret_key` 锁等待从 20×0.1s 增加到 50×0.2s（共 10 秒），并添加锁文件过期清理（超过 30 秒的锁文件视为僵尸锁删除）。

## Capabilities

### Modified Capabilities

- `input-validation`：`sort_by` 白名单校验行为统一。
- `data-safety`：清理任务的路径匹配准确性。
- `secret-management`：SECRET_KEY 生成的并发安全性。

## Impact

- **向后兼容**：`record_service` 的 `sort_by` 从静默回退改为 400 拒绝，前端需使用合法字段名（前端已使用 `createtime`/`updatetime`，无影响）。
- **非目标**：不修改 P1-8、P1-10、P2-16。
