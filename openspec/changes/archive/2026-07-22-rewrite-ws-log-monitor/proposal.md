## Why

`logs.py` 的 WebSocket 日志监控存在 5 个子问题：(1) 连接时 `readlines()` 一次性读取整个日志文件；(2) `RotatingFileHandler` 轮转后 `new_size < file_size` 分支未处理，新日志丢失直到客户端重连；(3) 0.5s 轮询即使无新日志也持续唤醒；(4) `log_task` 创建存在竞态（无锁判空）；(5) 正则匹配虽经 NEW-2 修复了 PID/TID 噪声，但依赖"先污染再清洗"的脆弱模式。

## What Changes

- **增量读取替代全量读取**：连接时读取最后 N 行（tail）而非整个文件，后续轮询仅读取新增内容。
- **日志轮转感知**：检测文件大小减小（轮转信号），重置读取位置到文件头。
- **`log_task` 竞态修复**：用 `asyncio.Lock` 保护 `log_task` 创建逻辑。
- **正则匹配加固**：使用更健壮的解析方式，降低对格式字符串的敏感度。

## Capabilities

### Modified Capabilities

- `ws-log-monitor`：WebSocket 日志监控的文件读取、轮转检测、并发安全。

## Impact

- **向后兼容**：WebSocket 消息格式不变，前端无需修改。
- **性能改善**：连接时不再全量读取（最高节省 25MB 内存），轮询期间仅读取增量。
- **非目标**：不引入 `watchdog` 等新依赖（改进轮询即可满足需求）。不修改 P1-8、P2-16。
