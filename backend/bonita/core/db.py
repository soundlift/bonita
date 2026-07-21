
import os
import logging
import secrets
from alembic.command import upgrade, stamp
from alembic.config import Config

from bonita.core.config import settings
from bonita.core.security import get_password_hash

logger = logging.getLogger(__name__)
from bonita.db import Base, engine, SessionFactory
from bonita.db.models import *


def init_db():
    """
    初始化数据库
    """
    location = settings.DATABASE_LOCATION
    if not os.path.exists(location):
        Base.metadata.create_all(bind=engine)
        init_super_user()
        stamp_db()
    else:
        upgrade_db()

def init_super_user():
    """
    初始化超级管理员
    """
    pwd = settings.FIRST_SUPERUSER_PASSWORD
    if pwd is None:
        # 不应走到这里——_ensure_admin_password 已在 config.py 中处理
        pwd = secrets.token_urlsafe(12)
        logger.warning("[BONITA] init_super_user: 密码未在配置阶段生成，临时密码: %s", pwd)
    with SessionFactory() as session:
        _user = User.get_user_by_email(session=session, email=settings.FIRST_SUPERUSER_EMAIL)
        if not _user:
            _user = User(
                name=settings.FIRST_SUPERUSER,
                email=settings.FIRST_SUPERUSER_EMAIL,
                hashed_password=get_password_hash(pwd),
                is_active=True,
                is_superuser=True
            )
            _user.create(session)


def upgrade_db():
    """
    更新数据库
    """
    alembic_cfg = Config()
    alembic_cfg.set_main_option('script_location', settings.ALEMBIC_LOCATION)
    alembic_cfg.set_main_option('sqlalchemy.url', settings.SQLALCHEMY_DATABASE_URI)
    upgrade(alembic_cfg, 'head')


def stamp_db():
    """
    打标签
    """
    alembic_cfg = Config()
    alembic_cfg.set_main_option('script_location', settings.ALEMBIC_LOCATION)
    alembic_cfg.set_main_option('sqlalchemy.url', settings.SQLALCHEMY_DATABASE_URI)
    stamp(alembic_cfg, 'head')
