## 1. Bug 1: destpath None Guard

- [x] 1.1 在 `backend/bonita/celery_tasks/tasks.py:360` 将 `if record.destpath != destpath:` 改为 `if record.destpath and record.destpath != destpath:`
- [x] 1.2 在 `backend/bonita/celery_tasks/tasks.py:390` 将 `if record.destpath != target_file.full_path:` 改为 `if record.destpath and record.destpath != target_file.full_path:`
- [x] 1.3 验证：新记录（destpath=None）走转移流程时不再抛 TypeError

## 2. Bug 2: Logs Regex 清理（降级为 P2 改善）
- [x] 2.1 在 `backend/bonita/api/websockets/logs.py` 的正则匹配后，增加 message 清理逻辑：`re.sub(r'^PID:\d+ TID:\d+ \[.*?\]\s*', '', message)` 去除 PID/TID/task_id 前缀
- [x] 2.2 验证：WebSocket 日志页面显示的 message 不再包含 PID/TID/task_id 前缀

## 3. Bug 3: Double WebSocket accept

- [x] 3.1 从 `backend/bonita/api/websockets/logs.py` 的 `LogConnectionManager.connect()` 方法中移除 `await websocket.accept()` 调用（line 46）
- [x] 3.2 验证：WebSocket 日志连接正常建立，认证流程不受影响

## 4. Bug 4: LOGGING_LOCATION 绝对路径

- [x] 4.1 在 `backend/bonita/utils/logger.py` 的 `init_log_config()` 中，将 `settings.LOGGING_LOCATION` 通过 `os.path.abspath()` 解析为绝对路径，并用 `os.makedirs()` 确保父目录存在
- [x] 4.2 将解析后的绝对路径回写到 `settings.LOGGING_LOCATION`，使 WebSocket 监控也使用正确路径
- [x] 4.3 验证：uvicorn 和 Celery worker 写入同一日志文件
