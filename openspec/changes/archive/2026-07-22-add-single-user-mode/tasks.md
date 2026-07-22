## 1. 默认关闭开放注册

- [x] 1.1 在 `backend/bonita/core/config.py` 中，将 `USERS_OPEN_REGISTRATION: bool = True` 改为 `USERS_OPEN_REGISTRATION: bool = False`
- [x] 1.2 验证：`python -c "from bonita.core.config import settings; assert settings.USERS_OPEN_REGISTRATION == False"`

## 2. 启动时多用户警告

- [x] 2.1 在 `backend/bonita/main.py` 的 startup 事件中（或 `init_db` 后），查询 `User` 表记录数
- [x] 2.2 若 `user_count > 1`，输出 `logger.warning(f"检测到 {user_count} 个用户账户。Bonita 设计为单用户系统，多用户场景下观看历史、收藏、评分等数据不隔离。")`
- [x] 2.3 验证：语法检查通过

## 3. API 文档标注

- [x] 3.1 在 `backend/bonita/api/routes/users.py` 的 `create_user` 端点 docstring 中添加：`注意：Bonita 为单用户设计，多用户场景下观看历史、收藏、评分等数据不隔离。`
- [x] 3.2 验证：语法检查通过

## 4. 验证

- [x] 4.1 `python -c "from bonita.core.config import settings; print(settings.USERS_OPEN_REGISTRATION)"` 输出 `False`
- [x] 4.2 检查 `main.py` 中有多用户查询逻辑
