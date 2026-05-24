"""Add IMEI/serial tracking — device_instances table + product flags + repair link

Revision ID: f1a2b3c4d5e6
Revises: c2325ea7abea
Create Date: 2026-05-25 10:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "c2325ea7abea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Product flags ---------------------------------------------------
    op.add_column(
        "products",
        sa.Column("track_by_imei", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "products",
        sa.Column("track_by_serial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "products",
        sa.Column(
            "warranty_period_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # --- 2. device_status enum + device_instances table ---------------------
    device_status = postgresql.ENUM(
        "in_stock", "sold", "under_repair", "returned", "damaged", "archived",
        name="device_status",
    )
    device_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "device_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("imei", sa.String(20), nullable=True),
        sa.Column("serial_number", sa.String(80), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="device_status", create_type=False),
            nullable=False,
            server_default="in_stock",
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sale_line_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("warranty_ends_at", sa.Date(), nullable=True),
        sa.Column(
            "purchase_cost",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT",
                                name="fk_device_instances_tenant_id_tenants"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT",
                                name="fk_device_instances_product_id_products"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT",
                                name="fk_device_instances_branch_id_branches"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT",
                                name="fk_device_instances_customer_id_customers"),
        sa.CheckConstraint(
            "imei IS NOT NULL OR serial_number IS NOT NULL",
            name="ck_device_instances_id_required",
        ),
        sa.UniqueConstraint("tenant_id", "imei", name="uq_device_instances_tenant_imei"),
        sa.UniqueConstraint(
            "tenant_id", "serial_number", name="uq_device_instances_tenant_serial"
        ),
    )

    # Performance indexes
    op.create_index(
        "ix_device_instances_status", "device_instances", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_device_instances_customer", "device_instances", ["tenant_id", "customer_id"]
    )
    op.create_index(
        "ix_device_instances_product", "device_instances", ["tenant_id", "product_id"]
    )
    op.create_index(
        "ix_device_instances_imei", "device_instances", ["tenant_id", "imei"]
    )
    op.create_index(
        "ix_device_instances_serial", "device_instances", ["tenant_id", "serial_number"]
    )
    op.create_index("ix_device_instances_tenant_id", "device_instances", ["tenant_id"])

    # --- 3. Repair → DeviceInstance link -----------------------------------
    op.add_column(
        "repair_tickets",
        sa.Column(
            "device_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "device_instances.id",
                ondelete="SET NULL",
                name="fk_repair_tickets_device_instance_id_device_instances",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_repair_tickets_device_instance_id",
        "repair_tickets",
        ["device_instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_repair_tickets_device_instance_id", table_name="repair_tickets")
    op.drop_column("repair_tickets", "device_instance_id")

    op.drop_index("ix_device_instances_tenant_id", table_name="device_instances")
    op.drop_index("ix_device_instances_serial", table_name="device_instances")
    op.drop_index("ix_device_instances_imei", table_name="device_instances")
    op.drop_index("ix_device_instances_product", table_name="device_instances")
    op.drop_index("ix_device_instances_customer", table_name="device_instances")
    op.drop_index("ix_device_instances_status", table_name="device_instances")
    op.drop_table("device_instances")

    device_status = postgresql.ENUM(name="device_status")
    device_status.drop(op.get_bind(), checkfirst=True)

    op.drop_column("products", "warranty_period_days")
    op.drop_column("products", "track_by_serial")
    op.drop_column("products", "track_by_imei")
