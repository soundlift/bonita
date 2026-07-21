"""migrate scraping rules from eval format to str.format

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-21 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 已知的旧默认规则 → 新 str.format 格式
_RULE_MIGRATIONS = {
    # location_rule 常见默认值
    "actor+'/'+number+' '+title":      "{actor}/{number} {title}",
    "number+' '+title":                "{number} {title}",
    # naming_rule 常见默认值（与 location_rule 相同的表达式形式）
    "actor+'/'+number+' '+title":      "{actor}/{number} {title}",
    "number+' '+title":                "{number} {title}",
}


def upgrade() -> None:
    """对 scraping_config 表中匹配已知旧默认规则的行做迁移，
    无法识别的自定义规则保留原值（需用户手动改写）。
    """
    conn = op.get_bind()

    # 查询所有行
    rows = conn.execute(
        sa.text("SELECT id, location_rule, naming_rule FROM scrapingconfig")
    ).fetchall()

    migrated = 0
    for row in rows:
        row_id, location_rule, naming_rule = row
        new_location = _RULE_MIGRATIONS.get(location_rule, location_rule)
        new_naming = _RULE_MIGRATIONS.get(naming_rule, naming_rule)

        if new_location != location_rule or new_naming != naming_rule:
            conn.execute(
                sa.text(
                    "UPDATE scrapingconfig SET location_rule = :loc, naming_rule = :nam WHERE id = :id"
                ),
                {"loc": new_location, "nam": new_naming, "id": row_id},
            )
            migrated += 1

    print(f"[Bonita] 迁移完成：{migrated}/{len(rows)} 条刮削配置规则已更新为 str.format 格式")
    if migrated < len(rows):
        print(f"[Bonita] 警告：{len(rows) - migrated} 条自定义规则未自动迁移，请手动改写为 {{field}} 格式")


def downgrade() -> None:
    """回滚：将新格式规则还原为旧 eval 表达式格式。"""
    conn = op.get_bind()

    # 反向映射
    reverse = {v: k for k, v in _RULE_MIGRATIONS.items()}

    rows = conn.execute(
        sa.text("SELECT id, location_rule, naming_rule FROM scrapingconfig")
    ).fetchall()

    for row in rows:
        row_id, location_rule, naming_rule = row
        old_location = reverse.get(location_rule, location_rule)
        old_naming = reverse.get(naming_rule, naming_rule)

        if old_location != location_rule or old_naming != naming_rule:
            conn.execute(
                sa.text(
                    "UPDATE scrapingconfig SET location_rule = :loc, naming_rule = :nam WHERE id = :id"
                ),
                {"loc": old_location, "nam": old_naming, "id": row_id},
            )
