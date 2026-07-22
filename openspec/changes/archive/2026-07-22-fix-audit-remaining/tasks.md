## 1. sort_by 行为统一

- [x] 1.1 在 `backend/bonita/services/record_service.py` 中，将 `sort_by` 白名单校验的静默回退改为 `raise HTTPException(status_code=400, detail=f"无效排序字段: {sort_by}")`
- [x] 1.2 确保 `HTTPException` 已导入（`from fastapi import HTTPException`）
- [x] 1.3 验证：调用记录列表 API 传入 `sort_by=invalid` 返回 400

## 2. clean_others 路径规范化

- [x] 2.1 在 `backend/bonita/celery_tasks/tasks.py` 的 `celery_clean_others` 中，新增 `_normalize(p)` 辅助函数：`os.path.normcase(os.path.realpath(os.path.normpath(p)))`
- [x] 2.2 将 `known_paths` 构建改为 `{_normalize(r.destpath) for r in records}`
- [x] 2.3 将比较逻辑改为 `if _normalize(dest) not in known_paths:`，移除 `real_dest not in known_paths and dest not in known_paths` 的双重检查
- [x] 2.4 验证：路径含 `./`、符号链接、大小写差异时均正确匹配

## 3. SECRET_KEY 锁超时增强

- [x] 3.1 在 `backend/bonita/core/config.py` 的 `_ensure_secret_key` 中，将锁等待循环从 `range(20)` + `time.sleep(0.1)` 改为 `range(50)` + `time.sleep(0.2)`
- [x] 3.2 在尝试获取锁前，添加僵尸锁检测：若 `lock_path` 存在且 `time.time() - os.path.getmtime(lock_path) > 30`，删除锁文件
- [x] 3.3 验证：语法检查通过

## 4. 验证

- [x] 4.1 `python -c "from bonita.services.record_service import RecordService"` 无异常
- [x] 4.2 `python -c "from bonita.celery_tasks.tasks import celery_clean_others"` 无异常
- [x] 4.3 `python -c "from bonita.core.config import settings"` 无异常
