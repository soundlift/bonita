import logging
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple

from bonita.core.config import settings


# 复合上下文：(celery_task_id, record_id)
# record_id 为 None 表示当前不在刮削流程内（如全局日志），ScrapeLogHandler 会跳过
scrape_ctx: ContextVar[Tuple[str, Optional[int]]] = ContextVar(
    "scrape_ctx", default=("", None)
)

# 向后兼容：旧名 task_id_ctx 仍可被其他代码引用
task_id_ctx: ContextVar[str] = ContextVar("task_id", default="")


def set_scrape_context(celery_task_id: str = "", record_id: Optional[int] = None) -> None:
    """设置当前线程的刮削上下文，供 ScrapeLogHandler 关联日志到 record。

    在 celery_transfer_group 处理每条 record 前调用；
    record 处理结束（成功/失败/异常）后调用此函数清空上下文。
    """
    scrape_ctx.set((celery_task_id or "", record_id))
    # 同步 task_id_ctx 保持兼容
    task_id_ctx.set(celery_task_id or "")


def get_current_record_id() -> Optional[int]:
    """返回当前线程上下文中的 record_id，无则 None"""
    _celery_id, record_id = scrape_ctx.get()
    return record_id


def get_current_celery_task_id() -> str:
    """返回当前线程上下文中的 celery_task_id"""
    celery_id, _record_id = scrape_ctx.get()
    return celery_id


class ContextFilter(logging.Filter):
    """
    日志上下文过滤器，添加额外的上下文信息到日志记录中
    """

    def filter(self, record: logging.LogRecord):
        record.task_id = task_id_ctx.get()
        return True


class ScrapeLogHandler(logging.Handler):
    """将刮削流程产生的日志按 record_id 缓冲，批量写入 scrape_log.log_text。

    设计要点：
    - 通过 ContextVar 读取当前 record_id；为空时直接忽略（避免污染全局日志）
    - 内存缓冲 Dict[record_id, List[str]]，threading.Lock 保护
    - flush 触发条件：缓冲行数 >= 50 / 距上次 flush >= 1 秒 / 显式 flush_for_record
    - DB 写入延迟导入 SessionFactory 与 ScrapeLog，避免循环依赖

    注意：本 Handler 只做追加，不创建 scrape_log 记录。
    记录的生命周期（create/update status/finished_at）由 celery_transfer_group 负责。
    """

    FLUSH_LINE_THRESHOLD = 50
    FLUSH_INTERVAL_SECONDS = 1.0

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self._buffer: Dict[int, List[str]] = {}
        self._last_flush_at: Dict[int, float] = {}
        self._lock = threading.Lock()
        # 自定义简洁格式（不含 PID/TID 等噪音），由调用方覆盖
        self._formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            record_id = get_current_record_id()
            if record_id is None:
                return  # 非刮削流程，忽略

            line = self._formatter.format(record)
            with self._lock:
                self._buffer.setdefault(record_id, []).append(line)
                should_flush = (
                    len(self._buffer[record_id]) >= self.FLUSH_LINE_THRESHOLD
                    or (
                        time.time() - self._last_flush_at.get(record_id, 0.0)
                        >= self.FLUSH_INTERVAL_SECONDS
                    )
                )
            if should_flush:
                self.flush_for_record(record_id)
        except Exception:
            # Handler 内部异常不能影响主流程
            self.handleError(record)

    def flush_for_record(self, record_id: int) -> None:
        """将该 record_id 的缓冲日志追加写入对应 scrape_log.log_text。

        目标 scrape_log 取该 record_id 最新一条（按 started_at 倒序）。
        若找不到（理论上不应发生），丢弃缓冲以避免无限堆积。
        """
        with self._lock:
            lines = self._buffer.pop(record_id, [])
            self._last_flush_at[record_id] = time.time()
        if not lines:
            return

        try:
            from bonita.db import SessionFactory
            from bonita.db.models.scrape_log import ScrapeLog

            appended_text = "".join(line + "\n" for line in lines)
            session = SessionFactory()
            try:
                log = (
                    session.query(ScrapeLog)
                    .filter(ScrapeLog.record_id == record_id)
                    .order_by(ScrapeLog.started_at.desc())
                    .first()
                )
                if log is None:
                    # 目标日志不存在（异常时序），丢弃缓冲
                    return
                existing = log.log_text or ""
                log.log_text = existing + appended_text
                session.commit()
            finally:
                session.close()
        except Exception:
            # DB 写入失败不能影响主流程；缓冲已 pop，相当于丢弃
            pass

    def flush_all(self) -> None:
        """强制 flush 所有 record 的缓冲（用于进程退出或测试）"""
        with self._lock:
            record_ids = list(self._buffer.keys())
        for rid in record_ids:
            self.flush_for_record(rid)


# 全局单例（在 init_log_config 中注册到 root logger）
_scrape_log_handler: Optional[ScrapeLogHandler] = None


def get_scrape_log_handler() -> Optional[ScrapeLogHandler]:
    """返回已注册的 ScrapeLogHandler 单例，未注册时返回 None"""
    return _scrape_log_handler


def init_log_config():
    """
    日志配置：RotatingFileHandler + ScrapeLogHandler（叠加，非替换）
    """
    global _scrape_log_handler

    max_log_size = 5 * 1024 * 1024  # 5 MB
    backup_count = 5
    formatter = logging.Formatter(settings.LOGGING_FORMAT)
    file_handler = RotatingFileHandler(
        settings.LOGGING_LOCATION,
        maxBytes=max_log_size,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(ContextFilter())

    # ScrapeLogHandler：捕获刮削流程日志并按 record_id 写入 DB
    _scrape_log_handler = ScrapeLogHandler()
    _scrape_log_handler.setLevel(logging.INFO)

    logging.basicConfig(
        level=settings.LOGGING_LEVEL,
        handlers=[file_handler, _scrape_log_handler],
        force=True,
    )
