from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index

from bonita.db import Base


class ScrapeLog(Base):
    """ 刮削日志记录

    每条 record 每次刮削执行产生一条 scrape_log，
    通过 record_id 关联 TransRecords，存储完整过程日志与执行状态。
    """
    id = Column(Integer, primary_key=True)
    record_id = Column(
        Integer,
        ForeignKey("transrecords.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联的转移记录ID",
    )
    celery_task_id = Column(String, default="", server_default="", comment="Celery 任务ID")
    status = Column(
        String,
        default="running",
        server_default="running",
        comment="执行状态: running|success|failed|interrupted",
    )
    started_at = Column(DateTime, default=datetime.now, comment="开始时间")
    finished_at = Column(DateTime, default=None, nullable=True, comment="结束时间")
    log_text = Column(Text, default="", server_default="", comment="完整日志文本（追加写）")
    error_msg = Column(Text, default="", server_default="", comment="失败/异常原因摘要")


# 复合索引：加速按 record_id 查询并按 started_at 倒序取最新/历史
Index("ix_scrapelog_record_id_started_at", ScrapeLog.record_id, ScrapeLog.started_at.desc())
