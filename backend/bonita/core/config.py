import os
import logging
import secrets
import tempfile
import yaml
from typing import Any, Dict, Optional, Tuple
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    自定义 YAML 配置源：
    - 通过环境变量 `BONITA_CONFIG` 指定 YAML 文件路径；否则使用默认路径 `./data/config.yaml`
    - 若文件不存在或为空，则返回空配置
    """

    def __init__(self, settings_cls: type[BaseSettings], yaml_file_path: str) -> None:
        super().__init__(settings_cls)
        self.yaml_file_path = yaml_file_path

    def __call__(self) -> Dict[str, Any]:  # type: ignore[override]
        yaml_path = self.yaml_file_path
        if not yaml_path or not os.path.exists(yaml_path):
            return {}
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            # 仅返回一层平铺键，和 Settings 字段名一致即可
            return {str(k): v for k, v in data.items()}
        except Exception:
            # 读取失败时不阻断启动，交由其他配置源接管
            return {}

    # 为兼容 pydantic-settings 抽象基类要求，提供占位实现。
    # 实际不会被调用，因为我们覆写了 __call__ 并返回完整字典。
    def get_field_value(self, *args, **kwargs):  # type: ignore[override]
        return None, None, False


class Settings(BaseSettings):
    # 默认不区分大小写；支持在容器/服务器上通过环境变量覆盖
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )
    PROJECT_NAME: str = "Bonita"
    API_V1_STR: str = "/api/v1"
    # 与 alembic.ini 同步
    ALEMBIC_LOCATION: str = "./bonita/alembic"
    # DATABASE_LOCATION
    DATABASE_LOCATION: str = "./data/db.sqlite3"
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{DATABASE_LOCATION}"
    # CACHE_LOCATION
    CACHE_LOCATION: str = "./data/cache"
    # CELERY — broker 与业务数据库分离，避免高并发写入踩踏
    CELERY_BROKER_DB_LOCATION: str = "./data/celery_broker.sqlite3"
    CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL", f"sqla+sqlite:///{CELERY_BROKER_DB_LOCATION}")
    CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND", f"db+sqlite:///{DATABASE_LOCATION}")
    # 最大并发任务数, 受 worker 数量影响
    MAX_CONCURRENT_TASKS: int = os.environ.get("MAX_CONCURRENT_TASKS", 5)
    # 日志
    LOGGING_FORMAT: str = "[%(asctime)s] %(levelname)s in %(module)s: PID:%(process)d TID:%(thread)d [%(task_id)s] %(message)s"
    LOGGING_LOCATION: str = "./data/bonita.log"
    LOGGING_LEVEL: int = logging.INFO
    # 首次启动时自动生成并持久化到 config.yaml；源码中不保留硬编码默认值
    SECRET_KEY: Optional[str] = None
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    # 跨域
    BACKEND_CORS_ORIGINS: list = []
    # 初始化管理员
    FIRST_SUPERUSER: str = "admin"
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None
    # 是否开放注册
    USERS_OPEN_REGISTRATION: bool = False

    # 文件监控设置
    # 是否使用轮询模式（推荐用于 SMB/CIFS 网络挂载文件夹）
    MONITOR_USE_POLLING: bool = False
    # 轮询间隔（秒）
    MONITOR_POLLING_INTERVAL: int = 30
    # 文件浏览器路径白名单（空列表=不限制，向后兼容）
    ALLOWED_FILE_ROOTS: list[str] = []

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        配置读取优先级（前者优先级更高）：
        1) 初始化传入的值（init）
        2) YAML 文件（通过 `BONITA_CONFIG` 指定，默认 `./data/config.yaml`）
        3) 环境变量（env）
        """
        yaml_path = os.environ.get("BONITA_CONFIG", "./data/config.yaml")
        yaml_settings = YamlConfigSettingsSource(settings_cls, yaml_path)
        return (
            init_settings,
            yaml_settings,
            env_settings,
        )


settings = Settings()

_INSECURE_SECRET_KEYS = {None, "", "secret key"}
_yaml_path = os.environ.get("BONITA_CONFIG", "./data/config.yaml")
_logger = logging.getLogger(__name__)


def _ensure_secret_key(cfg: Settings) -> None:
    """检测 SECRET_KEY 是否为不安全的默认值，若是则生成随机密钥并持久化。
    通过文件锁保护并发写入（uvicorn reload + Celery worker 同时启动）。
    """
    if cfg.SECRET_KEY not in _INSECURE_SECRET_KEYS:
        return

    new_key = secrets.token_urlsafe(32)

    # 读取现有 YAML（若存在）
    existing: dict = {}
    if os.path.exists(_yaml_path):
        try:
            with open(_yaml_path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception:
            existing = {}

    # 若其他进程已写入安全密钥，直接使用
    existing_key = existing.get("SECRET_KEY")
    if existing_key and existing_key not in _INSECURE_SECRET_KEYS:
        cfg.SECRET_KEY = existing_key
        return

    existing["SECRET_KEY"] = new_key

    # 原子写入：先写临时文件，再 os.replace（跨平台原子操作）
    try:
        os.makedirs(os.path.dirname(os.path.abspath(_yaml_path)), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(os.path.abspath(_yaml_path)),
            suffix=".tmp",
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(existing, f, default_flow_style=False, allow_unicode=True)
        os.replace(tmp_path, _yaml_path)
    except Exception as e:
        _logger.error(f"[BONITA] 写入 SECRET_KEY 到 {_yaml_path} 失败: {e}")
        # 写入失败仍继续，使用内存中的密钥（与旧行为一致）

    cfg.SECRET_KEY = new_key


    _logger.warning(
        "[BONITA] SECRET_KEY 已自动生成并写入 %s。"
        "已签发的 Token 将失效，用户需重新登录。", _yaml_path
    )


def _ensure_admin_password(cfg: Settings) -> None:
    """若管理员密码为 None，生成随机密码并打印到日志。"""
    if cfg.FIRST_SUPERUSER_PASSWORD is not None:
        return
    random_pwd = secrets.token_urlsafe(12)
    cfg.FIRST_SUPERUSER_PASSWORD = random_pwd
    _logger.warning(
        "[BONITA] 临时管理员密码: %s （用户: %s）\n"
        "请首次登录后立即修改！", random_pwd, cfg.FIRST_SUPERUSER
    )


_ensure_secret_key(settings)
_ensure_admin_password(settings)
