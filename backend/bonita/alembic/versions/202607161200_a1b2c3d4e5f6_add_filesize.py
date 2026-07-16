"""add filesize to transrecords

Revision ID: a1b2c3d4e5f6
Revises: 3aadc460e69a
Create Date: 2026-07-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3aadc460e69a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transrecords', schema=None) as batch_op:
        batch_op.add_column(sa.Column('filesize', sa.Integer(), nullable=True, comment='源文件大小(字节)'))


def downgrade() -> None:
    with op.batch_alter_table('transrecords', schema=None) as batch_op:
        batch_op.drop_column('filesize')
