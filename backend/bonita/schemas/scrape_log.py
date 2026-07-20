from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class ScrapeLogBase(BaseModel):
    """ ScrapeLog 共享属性 """


class ScrapeLogPublic(ScrapeLogBase):
    """ 通过 API 返回的 ScrapeLog 视图 """
    id: int
    record_id: int
    celery_task_id: Optional[str] = ""
    status: str = "running"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    log_text: Optional[str] = ""
    error_msg: Optional[str] = ""

    class Config:
        from_attributes = True


class ScrapeLogPublicList(BaseModel):
    """ ScrapeLog 列表响应 """
    data: List[ScrapeLogPublic]
    count: int
