"""Sprint 6: index cho hàng đợi duyệt.

`extraction.extractor` là "luật" sinh ra dòng; hàng đợi duyệt lọc theo nó và
duyệt hàng loạt cho các dòng cùng luật. `extraction.confidence` là khóa sắp xếp
mặc định (tăng dần — người duyệt gặp dòng khó trước). Hai index này phục vụ cả
hai thao tác trên.

Revision ID: 005_review_indexes
Revises: 004_create_extraction
"""

from alembic import op

revision = "005_review_indexes"
down_revision = "004_create_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_extraction_extractor", "extraction", ["extractor"])
    op.create_index("ix_extraction_confidence", "extraction", ["confidence"])


def downgrade() -> None:
    op.drop_index("ix_extraction_confidence", table_name="extraction")
    op.drop_index("ix_extraction_extractor", table_name="extraction")
