import os
import logging
import datetime
from fastapi import APIRouter, Query, Depends

from bonita import schemas
from bonita.api.deps import SessionDep
from bonita.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_path_allowed(path: str) -> bool:
    """校验路径是否在允许的根目录范围内。
    ALLOWED_FILE_ROOTS 为空时不限制（向后兼容）。
    """
    allowed_roots = settings.ALLOWED_FILE_ROOTS
    if not allowed_roots:
        return True
    try:
        real_path = os.path.realpath(path)
        return any(
            os.path.commonpath([real_path, os.path.realpath(root)]) == os.path.realpath(root)
            for root in allowed_roots
        )
    except (ValueError, OSError):
        return False


logger = logging.getLogger(__name__)


@router.get("/list", response_model=schemas.FileListResponse)
async def list_directory(
        session: SessionDep,
        directory_path: str = Query(None, description="要浏览的目录路径"),
        ):
    """ 获取指定目录中的文件列表
    """
    directory_path = directory_path or ""

    # 路径白名单校验
    if directory_path and not _is_path_allowed(directory_path):
        logger.warning(f"路径访问被拒绝（不在 ALLOWED_FILE_ROOTS 范围内）: {directory_path}")
        return schemas.FileListResponse(
            data=[],
            current_path=directory_path,
            parent_path=None
        )
    
    # 检查路径是否存在
    if not os.path.exists(directory_path):
        return schemas.FileListResponse(
            data=[],
            current_path=directory_path,
            parent_path=None
        )
    
    # 如果是文件而不是目录，返回该文件信息
    if os.path.isfile(directory_path):
        file_stat = os.stat(directory_path)
        file_info = schemas.FileInfo(
            name=os.path.basename(directory_path),
            path=directory_path,
            is_dir=False,
            size=file_stat.st_size,
            modified_time=datetime.datetime.fromtimestamp(file_stat.st_mtime)
        )
        parent_path = os.path.dirname(directory_path)
        return schemas.FileListResponse(
            data=[file_info],
            current_path=directory_path,
            parent_path=parent_path
        )
    
    # 获取目录内容
    file_list = []
    try:
        items = os.scandir(directory_path)
        for item in items:
            item_path = os.path.join(directory_path, item)
            item_stat = os.stat(item_path)
            is_dir = os.path.isdir(item_path)
            
            file_info = schemas.FileInfo(
                name=item.name,
                path=item_path,
                is_dir=is_dir,
                size=item_stat.st_size if not is_dir else 0,
                modified_time=datetime.datetime.fromtimestamp(item_stat.st_mtime)
            )
            file_list.append(file_info)
        
        # 排序：目录在前，文件在后，按名称排序
        file_list.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        
        # 获取父目录
        parent_path = os.path.dirname(directory_path) if directory_path else None
        
        return schemas.FileListResponse(
            data=file_list,
            current_path=directory_path,
            parent_path=parent_path
        )
    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {str(e)}")
        return schemas.FileListResponse(
            data=[],
            current_path=directory_path,
            parent_path=os.path.dirname(directory_path) if directory_path else None
        ) 