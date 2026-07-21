## 1. MAX_CONCURRENT_TASKS 类型修复（P2-15）

- [x] 1.1 修改 `backend/bonita/core/config.py`：`MAX_CONCURRENT_TASKS` 改为 `int(os.environ.get("MAX_CONCURRENT_TASKS", "5"))`
- [x] 1.2 验证：语法检查通过

## 2. update 端点 id 排除（P2-20）

- [x] 2.1 修改 `backend/bonita/api/routes/task_config.py`：`model_dump(exclude_unset=True, exclude={"id"})`
- [x] 2.2 修改 `backend/bonita/api/routes/scraping_config.py`：同上
- [x] 2.3 验证：语法检查通过

## 3. sort_by 白名单（P1-13）

- [x] 3.1 修改 `backend/bonita/api/routes/mediaitem.py`：添加 `ALLOWED_SORT_FIELDS_MEDIAITEM` 白名单集
- [x] 3.2 修改 `backend/bonita/services/record_service.py`：添加 `ALLOWED_SORT_FIELDS_RECORDS` 白名单
- [x] 3.3 验证：语法检查通过；白名单测试通过

## 4. clean_others 数据库查询（P1-12）

- [x] 4.1 修改 `backend/bonita/celery_tasks/tasks.py`：查询 `TransRecords` 获取已知成功文件集合
- [x] 4.2 验证：语法检查通过

## 5. WS token 从 URL 移到首条消息（P1-14）

- [x] 5.1 修改 `backend/bonita/api/websockets/logs.py`：改为连接后等待首条 JSON 消息认证（5 秒超时）
- [x] 5.2 修改 `frontend/src/pages/Logs.vue`：移除 URL 中 token 参数，改为连接后发送认证消息
- [x] 5.3 验证：语法检查通过

## 6. 端到端验证

- [x] 6.1 所有修改文件语法检查通过（7 个文件）
- [x] 6.2 sort_by 白名单拒绝非法值
- [x] 6.3 clean_others 使用 DB 查询
