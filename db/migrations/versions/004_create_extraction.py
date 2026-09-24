"""Sprint 4: extraction, procedure_fact, procedure_standard, term + view đã duyệt.

Revision ID: 004_create_extraction
Revises: 003_create_measurement_framework
"""

from alembic import op
import sqlalchemy as sa

from db.views import create_approved_views, drop_approved_views

revision = "004_create_extraction"
down_revision = "003_create_measurement_framework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = sa.Enum(
        "pending",
        "approved",
        "rejected",
        "superseded",
        name="extraction_status",
    )
    op.create_table(
        "extraction",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.String(128), sa.ForeignKey("document.id"), nullable=False),
        sa.Column("section_path", sa.String(512), nullable=True),
        sa.Column("chunk_id", sa.String(128), nullable=True),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("char_start", sa.Integer, nullable=True),
        sa.Column("char_end", sa.Integer, nullable=True),
        sa.Column("extractor", sa.String(128), nullable=False),
        sa.Column("extractor_version", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("supersedes_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_extraction_document_id", "extraction", ["document_id"])
    op.create_index("ix_extraction_status", "extraction", ["status"])

    op.create_table(
        "procedure_fact",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("fact_kind", sa.String(32), nullable=False),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("rel_op", sa.String(16), nullable=True),
        sa.Column("value_min", sa.Float, nullable=True),
        sa.Column("value_max", sa.Float, nullable=True),
        sa.Column("unit_id", sa.Integer, sa.ForeignKey("unit.id"), nullable=True),
        sa.Column("value_text", sa.Text, nullable=True),
        sa.Column("condition_text", sa.Text, nullable=True),
    )
    op.create_index("ix_procedure_fact_extraction_id", "procedure_fact", ["extraction_id"])
    op.create_index("ix_procedure_fact_procedure_id", "procedure_fact", ["procedure_id"])
    op.create_index("ix_procedure_fact_fact_kind", "procedure_fact", ["fact_kind"])

    op.create_table(
        "procedure_standard",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("ord", sa.Integer, nullable=True),
        sa.Column("name_vi", sa.Text, nullable=False),
        sa.Column("range_text", sa.Text, nullable=True),
        sa.Column("accuracy_text", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_procedure_standard_extraction_id", "procedure_standard", ["extraction_id"]
    )
    op.create_index(
        "ix_procedure_standard_procedure_id", "procedure_standard", ["procedure_id"]
    )

    op.create_table(
        "term",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("term_vi", sa.Text, nullable=False),
        sa.Column("term_en", sa.Text, nullable=True),
        sa.Column("definition", sa.Text, nullable=True),
    )
    op.create_index("ix_term_extraction_id", "term", ["extraction_id"])
    op.create_index("ix_term_procedure_id", "term", ["procedure_id"])

    # P3: view đã duyệt — nguồn sự thật chung ở db/views.py.
    create_approved_views(op.get_bind())


def downgrade() -> None:
    drop_approved_views(op.get_bind())

    op.drop_index("ix_term_procedure_id", table_name="term")
    op.drop_index("ix_term_extraction_id", table_name="term")
    op.drop_table("term")

    op.drop_index("ix_procedure_standard_procedure_id", table_name="procedure_standard")
    op.drop_index("ix_procedure_standard_extraction_id", table_name="procedure_standard")
    op.drop_table("procedure_standard")

    op.drop_index("ix_procedure_fact_fact_kind", table_name="procedure_fact")
    op.drop_index("ix_procedure_fact_procedure_id", table_name="procedure_fact")
    op.drop_index("ix_procedure_fact_extraction_id", table_name="procedure_fact")
    op.drop_table("procedure_fact")

    op.drop_index("ix_extraction_status", table_name="extraction")
    op.drop_index("ix_extraction_document_id", table_name="extraction")
    op.drop_table("extraction")
    sa.Enum(name="extraction_status").drop(op.get_bind(), checkfirst=True)
