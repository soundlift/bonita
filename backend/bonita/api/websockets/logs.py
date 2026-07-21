import os
import re
import asyncio
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState
from jose import jwt, JWTError
from pydantic import ValidationError

from bonita import schemas
from bonita.core.config import settings
from bonita.core import security
router = APIRouter()

# 清理 LOGGING_FORMAT 中的 PID/TID/[task_id] 前缀，只保留纯消息
_CLEAN_PID_TID = re.compile(r'^PID:\d+ TID:\d+ \[.*?\]\s*')


async def verify_ws_token(websocket: WebSocket, token: str) -> schemas.TokenPayload:
    """
    验证WebSocket连接的令牌
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

    async def connect(self, websocket: WebSocket):
        """
        注册已认证的WebSocket连接并启动日志监控
        """
        self.active_connections.append(websocket)

        # 启动日志监控任务（如果尚未启动）
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
        持续监控日志文件并发送新的日志条目
        """
        log_file_path = settings.LOGGING_LOCATION
        if not os.path.exists(log_file_path):
            return

        log_pattern = r"\[(.*?)\] (\w+) in ([\w\.]+): (.*)"

        # 获取当前文件大小作为初始位置
        file_size = os.path.getsize(log_file_path)

        # 读取整个日志文件
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                # 直接读取整个文件
                lines = f.readlines()

            # 批量处理日志
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

            # 一次性发送所有日志
            if log_entries:
                # 创建批量日志对象
                batch_data = {"logs": [entry.model_dump() for entry in log_entries]}
                # 向所有连接的客户端一次性发送所有日志
                disconnected_websockets = []
                for websocket in self.active_connections:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            await websocket.send_json(batch_data)
                        except (WebSocketDisconnect, Exception):
                            disconnected_websockets.append(websocket)

                # 移除断开连接的WebSocket
                for websocket in disconnected_websockets:
                    if websocket in self.active_connections:
                        self.active_connections.remove(websocket)
        except Exception as e:
            print(f"读取历史日志时出错: {e}")

        # 持续监控日志文件变化
        while not self.stop_flag and self.active_connections:
            # 检查文件是否增长
            new_size = os.path.getsize(log_file_path)

            if new_size > file_size:
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

                    # 批量处理新增日志
                    for entry in log_entries:
                        await self.send_log(entry)

                file_size = new_size

            # 减少等待时间，提高日志更新频率
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
