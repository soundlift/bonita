"""add scrape_log table and skip_on_success field

Revision ID: 1463157dd573
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20 22:56:13.396671

Scope:
- 新增 scrape_log 表（含 record_id 索引与 (record_id, started_at DESC) 复合索引）
- TransferConfig 新增 skip_on_success 字段（默认 True，server_default='1'）

Note: autogenerate 还检测到了 kombu_*/celery_taskmeta 等表的 drop 以及
metadata.media_item_id 的 drop，但这些是 Celery broker 表与历史遗留字段，
不在本次 change 范围内，已手动从迁移中剔除以避免破坏 Celery 运行时。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1463157dd573'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. scrape_log 表
    op.create_table(
        'scrapelog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False, comment='关联的转移记录ID'),
        sa.Column('celery_task_id', sa.String(), server_default='', nullable=True, comment='Celery 任务ID'),
        sa.Column('status', sa.String(), server_default='running', nullable=True, comment='执行状态: running|success|failed|interrupted'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='开始时间'),
        sa.Column('finished_at', sa.DateTime(), nullable=True, comment='结束时间'),
        sa.Column('log_text', sa.Text(), server_default='', nullable=True, comment='完整日志文本（追加写）'),
        sa.Column('error_msg', sa.Text(), server_default='', nullable=True, comment='失败/异常原因摘要'),
        sa.ForeignKeyConstraint(['record_id'], ['transrecords.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('scrapelog', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_scrapelog_record_id'), ['record_id'], unique=False)
        batch_op.create_index(
            'ix_scrapelog_record_id_started_at',
            ['record_id', sa.text('started_at DESC')],
            unique=False,
        )

    # 2. TransferConfig.skip_on_success 字段
    with op.batch_alter_table('transferconfig', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'skip_on_success',
                sa.Boolean(),
                server_default='1',
                nullable=True,
                comment='扫描时是否跳过已成功记录',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('transferconfig', schema=None) as batch_op:
        batch_op.drop_column('skip_on_success')

    with op.batch_alter_table('scrapelog', schema=None) as batch_op:
        batch_op.drop_index('ix_scrapelog_record_id_started_at')
        batch_op.drop_index(batch_op.f('ix_scrapelog_record_id'))

    op.drop_table('scrapelog')
