# Delta Spec: ws-log-monitor

> 基线: 无现有 spec（新能力）

## ADDED Requirements

### R1 · 增量读取日志文件

`LogConnectionManager.monitor_log_file()` SHALL 使用增量读取模式：连接时仅读取最后 N 行（默认 500），后续轮询仅读取新增内容。

**行为要求**：
- 连接时调用 `_tail_file(path, n=500)` 读取最后 N 行，不得使用 `f.readlines()` 全量读取。
- 轮询时通过 `f.seek(prev_size)` 定位到上次读取位置，仅读取 `new_content = f.read()`。
- 读取后更新 `prev_size = os.path.getsize(path)`。

#### Scenario: 大日志文件连接
- **GIVEN** 日志文件 20MB（约 10 万行）
- **WHEN** 新 WebSocket 客户端连接
- **THEN** 仅发送最后 500 行给客户端
- **AND** 内存占用不超过 200KB

#### Scenario: 增量读取新增日志
- **GIVEN** 客户端已连接，`prev_size = 1000`
- **WHEN** 日志文件增长到 1500 字节
- **THEN** 仅读取并发送新增的 500 字节内容

### R2 · 日志轮转感知

`monitor_log_file()` SHALL 检测日志文件轮转（文件大小减小），并在轮转后从新文件头开始读取。

**行为要求**：
- 每次轮询检查 `new_size = os.path.getsize(path)`。
- 若 `new_size < prev_size`，判定为轮转发生，重置 `prev_size = 0`。
- 下次轮询时从文件头开始读取（`seek(0)`）。

#### Scenario: 轮转后继续接收日志
- **GIVEN** 客户端正在接收日志，`prev_size = 5000000`（5MB）
- **WHEN** `RotatingFileHandler` 轮转日志文件，新文件大小为 1000
- **THEN** 检测到 `new_size < prev_size`，重置 `prev_size = 0`
- **AND** 下次轮询从新文件头开始读取
- **AND** 客户端继续接收新日志，无中断

### R3 · `log_task` 创建加锁

`LogConnectionManager.connect()` SHALL 使用 `asyncio.Lock` 保护 `log_task` 创建逻辑，消除并发连接的竞态。

**行为要求**：
- `__init__` 中创建 `self._task_lock = asyncio.Lock()`。
- `connect` 中在锁内检查 `self.log_task is None or self.log_task.done()` 后创建任务。

#### Scenario: 并发连接不创建重复任务
- **GIVEN** 两个 WebSocket 客户端几乎同时连接
- **WHEN** 两个 `connect` 调用并发执行
- **THEN** 仅创建一个 `monitor_log_file` 任务
- **AND** 两个客户端都收到相同的日志流

### R4 · 初始读取发送批量日志

连接时的初始日志 SHALL 以批量 JSON 格式发送（`{"logs": [...]}`），与增量日志的逐条发送格式区分。

**行为要求**：
- 初始读取的 N 行日志解析后，以 `{"logs": [entry1, entry2, ...]}` 格式一次性发送。
- 增量日志逐条通过 `send_log()` 发送单个 `LogEntry`。
- 前端需兼容两种格式（已有 `batch_data` 处理逻辑）。
