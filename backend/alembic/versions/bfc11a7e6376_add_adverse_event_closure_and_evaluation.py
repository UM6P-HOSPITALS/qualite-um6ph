"""add adverse event closure and evaluation

Revision ID: bfc11a7e6376
Revises: e319063e2dcb
Create Date: 2026-09-14 11:34:42.944179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfc11a7e6376'
down_revision: Union[str, None] = 'e319063e2dcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('adverse_events', sa.Column('efficacite_evaluee', sa.Boolean(), nullable=True))
    op.execute("UPDATE adverse_events SET efficacite_evaluee = false WHERE efficacite_evaluee IS NULL")
    op.alter_column('adverse_events', 'efficacite_evaluee', nullable=False)
    op.add_column('adverse_events', sa.Column('evaluation_efficacite', sa.Text(), nullable=True))
    op.add_column('adverse_events', sa.Column('date_cloture', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('adverse_events', 'date_cloture')
    op.drop_column('adverse_events', 'evaluation_efficacite')
    op.drop_column('adverse_events', 'efficacite_evaluee')