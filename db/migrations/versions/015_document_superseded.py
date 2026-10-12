"""Trạng thái ``superseded`` cho phiên bản cũ của một QTKĐ.

Mỗi số QTKĐ chỉ có một phiên bản trong chỉ mục; bản cũ hơn được gỡ khỏi Qdrant,
giữ tệp gốc + Markdown và mang trạng thái ``superseded``.

``downgrade`` đưa các dòng ``superseded`` về ``pending`` (chúng không còn chunk
trong Qdrant, cần Xử lý lại) rồi dựng lại enum đúng như revision 014: PostgreSQL
không xóa được một giá trị enum, nên phải đổi kiểu cột sang enum mới. SQLite lưu
enum dạng chuỗi, chỉ cần bước đổi dữ liệu.

Revision ID: 015_document_superseded
Revises: 014_drop_knowledge_flow
"""

from alembic import op

revision = "015_document_superseded"
down_revision = "014_drop_knowledge_flow"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.execute("ALTER TYPE ingest_status ADD VALUE IF NOT EXISTS 'superseded'")


def downgrade() -> None:
    op.execute(
        "UPDATE document SET ingest_status = 'pending', ingest_error = NULL "
        "WHERE ingest_status = 'superseded'"
    )
    if not _is_postgresql():
        return
    op.execute("ALTER TABLE document ALTER COLUMN ingest_status DROP DEFAULT")
    op.execute("ALTER TYPE ingest_status RENAME TO ingest_status_old")
    op.execute("CREATE TYPE ingest_status AS ENUM ('pending', 'processing', 'ready', 'error')")
    op.execute(
        "ALTER TABLE document ALTER COLUMN ingest_status TYPE ingest_status "
        "USING ingest_status::text::ingest_status"
    )
    op.execute("ALTER TABLE document ALTER COLUMN ingest_status SET DEFAULT 'pending'")
    op.execute("DROP TYPE ingest_status_old")
