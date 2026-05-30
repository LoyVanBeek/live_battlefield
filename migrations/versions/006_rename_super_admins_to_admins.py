"""Rename super_admins table to admins

Revision ID: 006
Revises: 005
Create Date: 2026-05-24

"""
from alembic import op

revision = "006"
down_revision = "005"


def upgrade():
    op.rename_table("super_admins", "admins")


def downgrade():
    op.rename_table("admins", "super_admins")
