## 1. 实现 `_tail_file` 辅助函数

- [x] 1.1 在 `backend/bonita/api/websockets/logs.py` 中新增 `_tail_file(path: str, n: int = 500) -> list[str]` 函数：二进制模式打开文件，从末尾向前搜索 `n` 个换行符，返回最后 `n` 行
- [x] 1.2 处理文件不存在或为空的情况：返回空列表
- [x] 1.3 验证：`_tail_file` 对 20MB 文件执行时间 < 100ms

## 2. 修复初始读取

- [x] 2.1 将 `monitor_log_file` 中的 `f.readlines()` 替换为 `_tail_file(log_file_path, n=500)`
- [x] 2.2 验证：连接时仅发送最后 500 行，内存占用 < 200KB

## 3. 修复轮转检测

- [x] 3.1 在轮询循环中，添加 `new_size < file_size` 分支：重置 `file_size = 0`，记录轮转日志
- [x] 3.2 确保轮转后下次迭代从文件头 `seek(0)` 开始读取
- [x] 3.3 验证：模拟日志轮转（重命名文件 + 创建新文件），客户端继续接收新日志

## 4. 修复 `log_task` 竞态

- [x] 4.1 在 `LogConnectionManager.__init__` 中添加 `self._task_lock = asyncio.Lock()`
- [x] 4.2 在 `connect` 方法中，用 `async with self._task_lock:` 包裹 `log_task` 判空和创建逻辑
- [x] 4.3 验证：并发连接时仅创建一个 `monitor_log_file` 任务

## 5. 验证

- [x] 5.1 语法检查通过
- [x] 5.2 WebSocket 连接后收到最后 500 行日志（批量格式）
- [x] 5.3 新增日志实时推送到客户端（增量格式）
- [x] 5.4 日志轮转后客户端不中断，继续接收新文件日志
