"""merge scrape_log and scraping_rules

Revision ID: fb9a7f6888cb
Revises: 1463157dd573, b2c3d4e5f6a7
Create Date: 2026-07-21 22:32:29.108559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb9a7f6888cb'
down_revision: Union[str, None] = ('1463157dd573', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
