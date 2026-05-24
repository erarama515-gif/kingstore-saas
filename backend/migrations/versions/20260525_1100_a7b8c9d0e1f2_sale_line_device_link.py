"""Add sale_lines.device_instance_id — tracked-device sale linkage

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-05-25 11:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sale_lines",
        sa.Column(
            "device_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "device_instances.id",
                ondelete="RESTRICT",
                name="fk_sale_lines_device_instance_id_device_instances",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sale_lines_device_instance_id",
        "sale_lines",
        ["device_instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sale_lines_device_instance_id", table_name="sale_lines")
    op.drop_column("sale_lines", "device_instance_id")
