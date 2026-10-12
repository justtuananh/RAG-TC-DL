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
