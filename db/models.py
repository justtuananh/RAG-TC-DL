"""SQLAlchemy ORM models for QTKĐ RAG system."""
import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, enum.Enum):
    """User roles for access control."""
    VIEWER = "viewer"          # Read-only access
    TECHNICIAN = "technician"  # Upload, extract
    APPROVER = "approver"      # Review and approve extractions
    ADMIN = "admin"            # Full system management


class AppUser(Base):
    """Application user account."""
    __tablename__ = "app_user"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        SQLEnum(UserRole, values_callable=lambda roles: [role.value for role in roles]),
        default=UserRole.VIEWER,
        nullable=False,
    )
    is_active = Column(Integer, default=1, nullable=False)  # SQLite compat: use int for bool
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="actor")

    def __repr__(self):
        return f"<AppUser id={self.id} username={self.username} role={self.role}>"


class AuditLog(Base):
    """Audit log entry for all structural modifications."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("app_user.id"), nullable=False)
    action = Column(String(50), nullable=False)  # "upload", "delete", "approve", "reject", etc.
    entity_type = Column(String(50), nullable=False)  # "document", "extraction", etc.
    entity_id = Column(String(255), nullable=True)  # File ID, extraction ID, etc.
    before = Column(JSON, nullable=True)  # State before change (for modifications)
    after = Column(JSON, nullable=True)   # State after change (for modifications)
    at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    actor = relationship("AppUser", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog id={self.id} actor_id={self.actor_id} action={self.action} at={self.at}>"


class DocumentType(str, enum.Enum):
    QTKD = "qtkd"
    HO_SO_KIEM_DINH = "ho_so_kiem_dinh"
    PHIEU_DO = "phieu_do"
    DANH_MUC = "danh_muc"
    KHAC = "khac"


class IngestStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    # Phiên bản cũ của một QTKĐ đã có bản mới hơn: gỡ khỏi chỉ mục, giữ tệp gốc + Markdown.
    SUPERSEDED = "superseded"


class Document(Base):
    """Document ledger record; the database is the source of truth for uploads."""
    __tablename__ = "document"

    id = Column(String(128), primary_key=True)
    file_stem = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(512), nullable=False)
    ext = Column(String(16), nullable=False)
    doc_type = Column(
        SQLEnum(DocumentType, values_callable=lambda types: [item.value for item in types]),
        default=DocumentType.KHAC,
        nullable=False,
    )
    sha256 = Column(String(64), nullable=False, index=True)
    size_bytes = Column(BigInteger, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ingest_status = Column(
        SQLEnum(IngestStatus, values_callable=lambda statuses: [item.value for item in statuses]),
        default=IngestStatus.PENDING,
        nullable=False,
    )
    ingest_error = Column(Text, nullable=True)

    uploader = relationship("AppUser", foreign_keys=[uploaded_by])


class SummaryStatus(enum.StrEnum):
    """Vòng đời bản tóm tắt tài liệu: LLM viết nháp, người duyệt phê duyệt hoặc từ chối."""

    GENERATING = "generating"
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


class DocumentSummary(Base):
    """Bản tóm tắt một tài liệu do LLM viết lúc nạp; chat chỉ dùng bản đã được người duyệt phê duyệt.

    ``source_sha256`` là băm Markdown lúc sinh: tài liệu xử lý lại mà Markdown đổi thì bản tóm tắt
    (kể cả đã duyệt) được viết lại thành nháp mới. ``revision`` chặn hai người ghi đè lên nhau.
    """

    __tablename__ = "document_summary"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        String(128), ForeignKey("document.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    status = Column(String(16), nullable=False, default=SummaryStatus.GENERATING.value)
    text = Column(Text, nullable=True)
    generated_text = Column(Text, nullable=True)
    warnings = Column(JSON, nullable=False, default=list)
    source_sha256 = Column(String(64), nullable=True)
    model = Column(String(128), nullable=True)
    error = Column(Text, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    generated_at = Column(DateTime, nullable=True)
    edited_by = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    edited_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)

    document = relationship("Document")
    editor = relationship("AppUser", foreign_keys=[edited_by])
    reviewer = relationship("AppUser", foreign_keys=[reviewed_by])


# ── Sprint 3: measurement concept framework ───────────────────────────────────
# Bốn bảng nền, seed sẵn, người dùng không nhập (spec §5.1). Chúng là nền ngữ
# nghĩa để router văn bản nhận diện loại thiết bị: đại lượng → đơn vị → loại
# thiết bị → QTKĐ. `aliases` lưu JSON list để router đọc thay cho hardcode.


class Quantity(Base):
    """Đại lượng đo: áp suất, nhiệt độ, khối lượng, độ dài, độ ẩm, thời gian."""
    __tablename__ = "quantity"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name_vi = Column(String(255), nullable=False)
    si_unit_code = Column(String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<Quantity id={self.id} code={self.code}>"


class Unit(Base):
    """Đơn vị đo + hệ số quy đổi tuyến tính về SI: si = factor * x + offset."""
    __tablename__ = "unit"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name_vi = Column(String(255), nullable=False)
    quantity_id = Column(Integer, ForeignKey("quantity.id"), nullable=False, index=True)
    factor_to_si = Column(Float, nullable=False, default=1.0)
    offset_to_si = Column(Float, nullable=False, default=0.0)
    aliases = Column(JSON, nullable=False, default=list)

    quantity = relationship("Quantity")

    def alias_list(self) -> list[str]:
        return list(self.aliases or [])

    def __repr__(self) -> str:
        return f"<Unit id={self.id} code={self.code} quantity_id={self.quantity_id}>"


class DeviceType(Base):
    """Loại phương tiện đo. Thay hằng số `_DEVICE_ALIASES` trong retrieval/router."""
    __tablename__ = "device_type"

    id = Column(Integer, primary_key=True)
    name_vi = Column(String(255), unique=True, nullable=False)
    aliases = Column(JSON, nullable=False, default=list)
    quantity_id = Column(Integer, ForeignKey("quantity.id"), nullable=True, index=True)

    quantity = relationship("Quantity")

    def alias_list(self) -> list[str]:
        return list(self.aliases or [])

    def __repr__(self) -> str:
        return f"<DeviceType id={self.id} name_vi={self.name_vi!r}>"


class Procedure(Base):
    """Một QTKĐ. `number` ví dụ '1.061'; gắn về `document` để giữ xuất xứ (P1)."""
    __tablename__ = "procedure"

    id = Column(Integer, primary_key=True)
    document_id = Column(String(128), ForeignKey("document.id"), nullable=True, index=True)
    number = Column(String(32), unique=True, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    title = Column(Text, nullable=True)
    device_type_id = Column(Integer, ForeignKey("device_type.id"), nullable=True, index=True)
    edition = Column(String(64), nullable=True)

    document = relationship("Document")
    device_type = relationship("DeviceType")

    def __repr__(self) -> str:
        return f"<Procedure id={self.id} number={self.number} year={self.year}>"


# ── Sổ đăng ký danh mục 877 (migration 017) ───────────────────────────────────
# 4 file danh mục (quy trình, năng lực kiểm định, năng lực hiệu chuẩn, chuẩn mẫu) nạp thành bảng để
# trả lời câu hỏi chung tất định và chỉ ra đúng tài liệu cho câu hỏi sâu (docs/KIEN_TRUC_DANH_MUC_877.md).
# Mỗi lần nạp một file là một ``catalog_source`` (bản nháp); chat chỉ đọc dòng của bản ĐÃ DUYỆT mới nhất
# mỗi loại. Mọi dòng giữ nguyên văn + số dòng trong file để trích dẫn; cột số chỉ để lọc/so sánh.
# Liên kết tới tài liệu trong kho KHÔNG lưu cứng: tính lại theo mã mỗi khi kho đổi (retrieval/registry_match).


class CatalogSourceStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    REPLACED = "replaced"  # bản đã duyệt trước đó, đã có bản duyệt mới hơn cùng loại


class CatalogSource(Base):
    """Một lần nạp một file danh mục. ``revision`` chặn hai người duyệt ghi đè lên nhau."""

    __tablename__ = "catalog_source"

    id = Column(Integer, primary_key=True)
    kind = Column(String(16), nullable=False, index=True)  # procedure | capability_kd | capability_hc | standard
    file_name = Column(String(512), nullable=False)
    stored_path = Column(String(1024), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    title = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default=CatalogSourceStatus.DRAFT.value, index=True)
    row_count = Column(Integer, nullable=False, default=0)
    issues = Column(JSON, nullable=False, default=list)
    revision = Column(Integer, nullable=False, default=1)
    uploaded_by = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)

    uploader = relationship("AppUser", foreign_keys=[uploaded_by])
    reviewer = relationship("AppUser", foreign_keys=[reviewed_by])


class CatalogProcedure(Base):
    """Một dòng DANH MỤC QUY TRÌNH. Khoá nghiệp vụ là ``code_key`` = tiền tố + số + năm
    (QTKĐ 1.017:2008 và QTKĐ 1.017:2014 là hai quy trình khác nhau)."""

    __tablename__ = "catalog_procedure"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("catalog_source.id", ondelete="CASCADE"), nullable=False, index=True)
    row = Column(Integer, nullable=False)
    code_raw = Column(Text, nullable=False)
    code_key = Column(String(64), nullable=True, index=True)
    prefix = Column(String(16), nullable=True)
    number = Column(String(32), nullable=True)
    year = Column(Integer, nullable=True)
    title = Column(Text, nullable=False, default="")
    issuer = Column(Text, nullable=True)
    field = Column(Text, nullable=True)
    kind = Column(String(16), nullable=False, default="kiem_dinh")  # kiem_dinh | hieu_chuan


class Capability(Base):
    """Một dòng NĂNG LỰC KIỂM ĐỊNH / HIỆU CHUẨN: phương tiện đo phòng được phép kiểm định/hiệu chuẩn."""

    __tablename__ = "capability"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("catalog_source.id", ondelete="CASCADE"), nullable=False, index=True)
    row = Column(Integer, nullable=False)
    kind = Column(String(16), nullable=False)  # kiem_dinh | hieu_chuan
    name = Column(Text, nullable=False)
    field = Column(Text, nullable=True)
    params_raw = Column(Text, nullable=True)
    procedures_raw = Column(Text, nullable=True)

    ranges = relationship("CapabilityRange", cascade="all, delete-orphan", order_by="CapabilityRange.ord")
    procedures = relationship("CapabilityProcedure", cascade="all, delete-orphan", order_by="CapabilityProcedure.ord")


class CapabilityRange(Base):
    """Dải đo của một năng lực, đã quy về SI để so với con số trong câu hỏi; ``text`` là nguyên văn."""

    __tablename__ = "capability_range"

    id = Column(Integer, primary_key=True)
    capability_id = Column(Integer, ForeignKey("capability.id", ondelete="CASCADE"), nullable=False, index=True)
    ord = Column(Integer, nullable=False, default=0)
    label = Column(Text, nullable=True)
    quantity = Column(String(32), nullable=False)
    min_si = Column(Numeric(38, 12), nullable=True)
    max_si = Column(Numeric(38, 12), nullable=False)
    text = Column(Text, nullable=False)


class CapabilityProcedure(Base):
    """Quy trình một năng lực áp dụng, đúng như ghi trong ô. Khớp với danh mục quy trình theo ``code_key``
    lúc đọc (hai file danh mục được duyệt độc lập); mã không khớp được liệt kê trong báo cáo."""

    __tablename__ = "capability_procedure"

    id = Column(Integer, primary_key=True)
    capability_id = Column(Integer, ForeignKey("capability.id", ondelete="CASCADE"), nullable=False, index=True)
    ord = Column(Integer, nullable=False, default=0)
    code_raw = Column(Text, nullable=False)
    code_key = Column(String(64), nullable=False, index=True)


class ReferenceStandard(Base):
    """Một dòng DANH MỤC CHUẨN MẪU."""

    __tablename__ = "reference_standard"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("catalog_source.id", ondelete="CASCADE"), nullable=False, index=True)
    row = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    model = Column(String(255), nullable=True)
    serial = Column(String(255), nullable=True)
    characteristics_raw = Column(Text, nullable=True)
    interval_raw = Column(String(128), nullable=True)
    interval_months = Column(Integer, nullable=True)
    field = Column(Text, nullable=True)

    ranges = relationship("StandardRange", cascade="all, delete-orphan", order_by="StandardRange.ord")


class StandardRange(Base):
    """Dải đo / dải tạo của một chuẩn mẫu, quy về SI ("chuẩn nào tạo được 600 bar")."""

    __tablename__ = "standard_range"

    id = Column(Integer, primary_key=True)
    standard_id = Column(Integer, ForeignKey("reference_standard.id", ondelete="CASCADE"), nullable=False, index=True)
    ord = Column(Integer, nullable=False, default=0)
    label = Column(Text, nullable=True)
    quantity = Column(String(32), nullable=False)
    min_si = Column(Numeric(38, 12), nullable=True)
    max_si = Column(Numeric(38, 12), nullable=False)
    text = Column(Text, nullable=False)
