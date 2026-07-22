## Context

`logs.py` 的 `LogConnectionManager.monitor_log_file()` 使用轮询模式监控日志文件：连接时 `readlines()` 全量读取，之后每 0.5s 检查文件大小，增长时 `seek` 到上次位置读取新增。存在 5 个子问题（见 proposal），其中轮转不感知和全量读取是核心缺陷。

现有依赖：FastAPI WebSocket、`asyncio`、`re`、`os`。项目已有 `RotatingFileHandler`（5MB × 5 备份）。

## Goals / Non-Goals

**Goals:**
- 连接时仅读取最后 N 行（而非整个文件）。
- 轮转后自动检测并从新文件头开始读取。
- `log_task` 创建加锁，消除竞态。
- 保持 WebSocket 消息格式不变。

**Non-Goals:**
- 不引入 `watchdog` 等新依赖。
- 不改为 Python logging 内存 handler 推送（需改 Celery worker 日志配置，侵入性大）。
- 不修改 P1-8、P2-16。

## Decisions

### D1 · 增量读取：`seek` + `read` + 位置追踪

保留轮询架构，修复读取逻辑：

```python
# 连接时：读取最后 N 行（tail）
def _tail_file(path: str, n: int = 500) -> list[str]:
    """读取文件最后 n 行，不加载整个文件"""
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        # 从末尾向前搜索 n 个换行符
        ...

# 轮询时：增量读取 + 轮转检测
file_size = os.path.getsize(path)
if file_size < prev_size:
    # 轮转发生：重置位置，读取新文件
    prev_size = 0
if file_size > prev_size:
    with open(path, 'r') as f:
        f.seek(prev_size)
        new_content = f.read()
    prev_size = file_size
```

**理由**：轮询是最简单的方案，修复后足以满足需求。`watchdog` 增加依赖且需处理平台差异，收益不显著。

### D2 · `log_task` 竞态：`asyncio.Lock`

```python
class LogConnectionManager:
    def __init__(self):
        self._task_lock = asyncio.Lock()
        ...

    async def connect(self, websocket):
        self.active_connections.append(websocket)
        async with self._task_lock:
            if self.log_task is None or self.log_task.done():
                self.log_task = asyncio.create_task(self.monitor_log_file())
```

**理由**：`asyncio.Lock` 是 asyncio 原生锁，不阻塞事件循环，适合保护协程内的临界区。

### D3 · 初始读取：`_tail_file` 替代 `readlines()`

连接时仅发送最后 500 行（可配置），避免 25MB 文件全量加载。

```python
# Before:
lines = f.readlines()  # 全量

# After:
lines = _tail_file(log_file_path, n=500)  # 仅最后 500 行
```

**理由**：日志页面关注最近日志，历史日志可通过文件直接查看。500 行约 100KB，内存友好。

### D4 · 正则匹配保持现状

NEW-2 修复后，`log_pattern` 能匹配 `LOGGING_FORMAT` 输出，`_CLEAN_PID_TID` 剥离 message 中的 PID/TID 前缀。此方案虽依赖"先匹配后清洗"，但实际格式稳定，不值得重写。

## Risks / Trade-offs

- **轮询延迟**：仍为 0.5s，但日志查看场景可接受。未来可降低到 0.2s 或用 `inotify`（Linux）。
- **`_tail_file` 实现**：二进制模式从末尾向前搜索换行符，需处理 UTF-8 多字节边界。简单实现可接受小误差（截断不完整行）。
- **轮转竞态**：轮转瞬间可能丢失 1-2 行日志（在 `getsize` 和 `seek` 之间文件被轮转）。概率极低，可接受。
