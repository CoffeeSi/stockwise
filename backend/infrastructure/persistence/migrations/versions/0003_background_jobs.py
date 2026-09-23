"""Persist leased calculation/import jobs and idempotent calculation requests.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("calculation_run_id", sa.Uuid(), nullable=True),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload", document, nullable=False),
        sa.Column("progress", document, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('calculation', 'import')", name=op.f("ck_background_jobs_valid_job_kind")),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name=op.f("ck_background_jobs_valid_job_status")),
        sa.CheckConstraint("(kind = 'calculation' AND calculation_run_id IS NOT NULL AND import_batch_id IS NULL) OR "
                           "(kind = 'import' AND import_batch_id IS NOT NULL AND calculation_run_id IS NULL)",
                           name=op.f("ck_background_jobs_valid_job_resource")),
        sa.ForeignKeyConstraint(["calculation_run_id"], ["calculation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calculation_run_id"),
        sa.UniqueConstraint("import_batch_id"),
        sa.UniqueConstraint("kind", "created_by", "idempotency_key", name="uq_background_jobs_idempotency"),
    )
    op.create_index("ix_background_jobs_claim", "background_jobs", ["status", "lease_until", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs")
    op.drop_table("background_jobs")
