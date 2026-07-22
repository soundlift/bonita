import os
import re
import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi.websockets import WebSocketState
from jose import jwt, JWTError
from pydantic import ValidationError

from bonita import schemas
from bonita.core.config import settings
from bonita.core import security
router = APIRouter()

# 清理 LOGGING_FORMAT 中的 PID/TID/[task_id] 前缀，只保留纯消息
_CLEAN_PID_TID = re.compile(r'^PID:\d+ TID:\d+ \[.*?\]\s*')

def _tail_file(path: str, n: int = 500) -> list:
    """读取文件最后 n 行，不加载整个文件。"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return []
            # 从末尾向前搜索 n+1 个换行符
            lines_found = 0
            pos = size - 1
            while pos > 0 and lines_found < n + 1:
                f.seek(pos)
                if f.read(1) == b'\n':
                    lines_found += 1
                pos -= 1
            # pos 停在最后一个换行符之前或文件头
            f.seek(max(0, pos + 1))
            return f.read().decode('utf-8', errors='replace').splitlines()[-n:]
    except OSError:
        return []


async def verify_ws_token(websocket: WebSocket, token: str) -> Optional[schemas.TokenPayload]:
    """
    验证WebSocket连接的令牌。验证失败时关闭连接并返回 None。
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return schemas.TokenPayload(**payload)
    except (JWTError, ValidationError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None


class LogConnectionManager:
    """
    日志WebSocket连接管理器
    用于管理连接的WebSocket客户端并向其发送日志更新
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.log_task = None
        self.stop_flag = False
        self._task_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """
        注册已认证的WebSocket连接并启动日志监控
        """
        self.active_connections.append(websocket)

        # 启动日志监控任务（如果尚未启动）
        async with self._task_lock:
            if self.log_task is None or self.log_task.done():
                self.stop_flag = False
                self.log_task = asyncio.create_task(self.monitor_log_file())

    def disconnect(self, websocket: WebSocket):
        """
        断开WebSocket连接
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # 如果没有连接，停止监控
        if not self.active_connections:
            self.stop_flag = True

    async def send_log(self, log_entry: schemas.LogEntry):
        """
        向所有已连接的客户端发送日志条目
        """
        disconnected_websockets = []
        send_tasks = []

        for websocket in self.active_connections:
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # 直接发送日志
                    await websocket.send_json(log_entry.model_dump())
                except (WebSocketDisconnect, Exception):
                    disconnected_websockets.append(websocket)

        # 移除断开连接的WebSocket
        for websocket in disconnected_websockets:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def monitor_log_file(self):
        """
        持续监控日志文件并发送新的日志条目。
        使用增量读取 + 轮转检测，避免全量读取和轮转后丢失日志。
        """
        log_file_path = settings.LOGGING_LOCATION
        if not os.path.exists(log_file_path):
            return

        log_pattern = r"\[(.*?)\] (\w+) in ([\w\.]+): (.*)"
        logger = logging.getLogger(__name__)

        # 初始读取：仅最后 500 行（不加载整个文件）
        try:
            lines = _tail_file(log_file_path, n=500)

            log_entries = []
            for line in lines:
                match = re.match(log_pattern, line.strip())
                if match:
                    timestamp, log_level, log_module, message = match.groups()
                    message = _CLEAN_PID_TID.sub('', message)
                    log_entry = schemas.LogEntry(
                        timestamp=timestamp,
                        level=log_level,
                        module=log_module,
                        message=message
                    )
                    log_entries.append(log_entry)

            # 批量发送历史日志
            if log_entries:
                batch_data = {"logs": [entry.model_dump() for entry in log_entries]}
                disconnected_websockets = []
                for websocket in self.active_connections:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            await websocket.send_json(batch_data)
                        except (WebSocketDisconnect, Exception):
                            disconnected_websockets.append(websocket)

                for websocket in disconnected_websockets:
                    if websocket in self.active_connections:
                        self.active_connections.remove(websocket)
        except Exception as e:
            logger.error(f"读取历史日志时出错: {e}")

        # 增量监控：仅读取新增内容，检测轮转
        file_size = os.path.getsize(log_file_path)

        while not self.stop_flag and self.active_connections:
            try:
                new_size = os.path.getsize(log_file_path)
            except OSError:
                await asyncio.sleep(0.5)
                continue

            # 轮转检测：文件大小减小说明发生了日志轮转
            if new_size < file_size:
                logger.info(f"检测到日志轮转（{file_size} → {new_size}），从新文件头开始读取")
                file_size = 0

            if new_size > file_size:
                try:
                    with open(log_file_path, "r", encoding="utf-8") as f:
                        f.seek(file_size)
                        new_content = f.read()

                    log_entries = []
                    for line in new_content.splitlines():
                        match = re.match(log_pattern, line.strip())
                        if match:
                            timestamp, log_level, log_module, message = match.groups()
                            message = _CLEAN_PID_TID.sub('', message)
                            log_entry = schemas.LogEntry(
                                timestamp=timestamp,
                                level=log_level,
                                module=log_module,
                                message=message
                            )
                            log_entries.append(log_entry)

                    for entry in log_entries:
                        await self.send_log(entry)

                    file_size = new_size
                except Exception as e:
                    logger.error(f"读取增量日志时出错: {e}")

            await asyncio.sleep(0.5)


# 创建WebSocket管理器
log_manager = LogConnectionManager()


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket接口，用于实时接收日志更新。
    认证方式：连接建立后，客户端必须在 5 秒内发送第一条 JSON 消息 {"type": "auth", "token": "..."}
    """
    await websocket.accept()

    # 等待客户端发送认证消息（5 秒超时）
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
    except asyncio.TimeoutError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证超时")
        return

    # 解析认证消息
    import json
    try:
        auth_data = json.loads(auth_msg)
        token = auth_data.get("token", "")
    except (json.JSONDecodeError, AttributeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="无效的认证消息格式")
        return

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="缺少 token")
        return

    token_data = await verify_ws_token(websocket, token)
    if not token_data:
        return  # 连接已在verify_ws_token中关闭

    # 认证成功，发送确认
    await websocket.send_json({"type": "auth", "status": "ok"})
    await log_manager.connect(websocket)
    try:
        while True:
            # 保持连接打开，直到客户端断开
            await websocket.receive_text()
    except WebSocketDisconnect:
        log_manager.disconnect(websocket)
