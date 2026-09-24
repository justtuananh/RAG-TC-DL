"""SQLAlchemy ORM models for QTKĐ RAG system."""
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

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
# nghĩa để dữ kiện trích xuất (Sprint 4) bám vào: đại lượng → đơn vị → loại
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


# ── Sprint 4: extraction + dữ kiện trích xuất từ QTKĐ ─────────────────────────
# `extraction` là nơi DUY NHẤT giữ xuất xứ (P1) và trạng thái duyệt. Mọi bảng dữ
# kiện (`procedure_fact`, `procedure_standard`, `term`) đều tham chiếu tới nó, nhờ
# đó hàng đợi duyệt, nhật ký và ràng buộc P3 chỉ phải cài đặt một lần (spec §5.3,
# §5.4). View đã duyệt nằm ở `db/views.py`.


class ExtractionStatus(str, enum.Enum):
    """Trạng thái duyệt của một extraction (spec §5.3)."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


# `fact_kind` hợp lệ cho procedure_fact (spec §5.4). Dùng hằng số thay vì enum DB
# để thêm loại mới không phải migration; dữ liệu vẫn được kiểm ở tầng ghi.
FACT_KINDS: tuple[str, ...] = (
    "working_range",
    "accuracy_class",
    "max_permissible_error",
    "calibration_interval",
    "env_condition",
    "inspection_step",
    "formula",
    # Sprint 7: trường của mẫu biên bản ở Phụ lục A, dùng để sinh cấu hình đọc
    # hồ sơ (spec §7). `label` là tên trường, `condition_text` là vai trò
    # ("header" | "table"), `value_text` giữ nguyên văn giá trị/cột.
    "appendix_field",
)


class Extraction(Base):
    """Một lần trích xuất, kèm xuất xứ nguyên văn và trạng thái duyệt."""
    __tablename__ = "extraction"

    id = Column(Integer, primary_key=True)
    document_id = Column(String(128), ForeignKey("document.id"), nullable=False, index=True)
    section_path = Column(String(512), nullable=True)
    chunk_id = Column(String(128), nullable=True)
    quote = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    # `extractor` là "luật" sinh ra dòng (rule:bang2.v1, llm:qwen2.5:7b). Hàng đợi
    # duyệt Sprint 6 lọc và duyệt hàng loạt theo cột này nên nó được đánh index;
    # `confidence` cũng vậy vì mặc định sắp xếp tăng dần để gặp dòng khó trước.
    extractor = Column(String(128), nullable=False, index=True)
    extractor_version = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0, index=True)
    status = Column(
        SQLEnum(
            ExtractionStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        default=ExtractionStatus.PENDING,
        nullable=False,
        index=True,
    )
    reviewed_by = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)
    supersedes_id = Column(Integer, ForeignKey("extraction.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", foreign_keys=[document_id])
    reviewer = relationship("AppUser", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<Extraction id={self.id} extractor={self.extractor} status={self.status}>"


class ProcedureFact(Base):
    """Dữ kiện vô hướng/khoảng trích từ QTKĐ (spec §5.4).

    `value_min`/`value_max` được chuẩn hóa về SI ngay lúc ghi; `value_text` giữ
    nguyên chuỗi gốc để hiển thị đúng như tài liệu. Đơn vị lạ → hai cột số để
    trống, hạ điểm tin cậy, không bao giờ đoán (spec §6).
    """
    __tablename__ = "procedure_fact"

    id = Column(Integer, primary_key=True)
    extraction_id = Column(Integer, ForeignKey("extraction.id"), nullable=False, index=True)
    procedure_id = Column(Integer, ForeignKey("procedure.id"), nullable=True, index=True)
    fact_kind = Column(String(32), nullable=False, index=True)
    label = Column(Text, nullable=True)
    rel_op = Column(String(16), nullable=True)
    value_min = Column(Float, nullable=True)
    value_max = Column(Float, nullable=True)
    unit_id = Column(Integer, ForeignKey("unit.id"), nullable=True)
    value_text = Column(Text, nullable=True)
    condition_text = Column(Text, nullable=True)

    extraction = relationship("Extraction")
    procedure = relationship("Procedure")
    unit = relationship("Unit")

    def __repr__(self) -> str:
        return f"<ProcedureFact id={self.id} kind={self.fact_kind}>"


class ProcedureStandard(Base):
    """Một dòng Bảng 2 Phương tiện kiểm định (spec §5.4). Giữ dạng text."""
    __tablename__ = "procedure_standard"

    id = Column(Integer, primary_key=True)
    extraction_id = Column(Integer, ForeignKey("extraction.id"), nullable=False, index=True)
    procedure_id = Column(Integer, ForeignKey("procedure.id"), nullable=True, index=True)
    ord = Column(Integer, nullable=True)
    name_vi = Column(Text, nullable=False)
    range_text = Column(Text, nullable=True)
    accuracy_text = Column(Text, nullable=True)
    note = Column(Text, nullable=True)

    extraction = relationship("Extraction")
    procedure = relationship("Procedure")

    def __repr__(self) -> str:
        return f"<ProcedureStandard id={self.id} name_vi={self.name_vi!r}>"


class Term(Base):
    """Mục §2 Thuật ngữ và định nghĩa (spec §5.4)."""
    __tablename__ = "term"

    id = Column(Integer, primary_key=True)
    extraction_id = Column(Integer, ForeignKey("extraction.id"), nullable=False, index=True)
    procedure_id = Column(Integer, ForeignKey("procedure.id"), nullable=True, index=True)
    term_vi = Column(Text, nullable=False)
    term_en = Column(Text, nullable=True)
    definition = Column(Text, nullable=True)

    extraction = relationship("Extraction")
    procedure = relationship("Procedure")

    def __repr__(self) -> str:
        return f"<Term id={self.id} term_vi={self.term_vi!r}>"


# ── Sprint 7: thiết bị, hồ sơ kiểm định và số liệu đo (spec §5.5) ──────────────
# `device` là phương tiện đo vật lý; khóa nhận dạng là (device_type_id, serial_no)
# sau khi chuẩn hóa hoa/thường. Khi hồ sơ thiếu serial, hệ thống tạo thiết bị tạm
# gắn cờ `needs_identification` thay vì gộp nhầm hai thiết bị khác nhau.
#
# `calibration_record` giữ xuất xứ P1 qua `extraction_id`: mỗi lần đọc hồ sơ sinh
# một extraction ``pending``, nhờ đó P3 áp dụng nguyên vẹn cho dữ liệu đo. Mọi số
# liệu đo đọc nguyên trạng từ tài liệu (P2), kể cả `error_value`.

# Giá trị hợp lệ cho `calibration_record.mode` / `.verdict` (spec §5.5). Dùng
# hằng số thay vì enum DB để thêm giá trị mới không phải migration; tầng ghi kiểm.
RECORD_MODES: tuple[str, ...] = ("ban_dau", "dinh_ky", "sau_sua_chua")
VERDICTS: tuple[str, ...] = ("dat", "khong_dat")


class Device(Base):
    """Một phương tiện đo vật lý (spec §5.5).

    `serial_no` giữ nguyên như tài liệu viết; `serial_norm` là dạng đã chuẩn hóa
    (bỏ khoảng trắng thừa, hạ hoa/thường) dùng cho đối sánh. Ràng buộc duy nhất
    trên ``(device_type_id, serial_norm)`` chặn tách đôi cùng một serial viết
    khác kiểu hoa/thường. Thiếu serial → `serial_norm` NULL, mỗi hồ sơ tạo một
    thiết bị tạm mới (NULL không xung đột duy nhất) và `needs_identification=1`.
    """

    __tablename__ = "device"
    __table_args__ = (
        UniqueConstraint(
            "device_type_id", "serial_norm", name="uq_device_type_serial_norm"
        ),
    )

    id = Column(Integer, primary_key=True)
    device_type_id = Column(
        Integer, ForeignKey("device_type.id"), nullable=True, index=True
    )
    serial_no = Column(String(128), nullable=True, index=True)
    serial_norm = Column(String(128), nullable=True, index=True)
    model_code = Column(String(255), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    owner_org = Column(String(255), nullable=True)
    attrs = Column(JSON, nullable=False, default=dict)
    needs_identification = Column(Integer, default=0, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    device_type = relationship("DeviceType")

    def __repr__(self) -> str:
        return f"<Device id={self.id} serial_no={self.serial_no!r} temp={bool(self.needs_identification)}>"


class CalibrationRecord(Base):
    """Một lần kiểm định (spec §5.5).

    `extraction_id` là cầu nối P1/P3: hồ sơ chỉ lộ ra qua ``v_calibration_record``
    khi extraction tương ứng đã duyệt. `expires_at` là giá trị dẫn xuất duy nhất
    được phép tính (ngoại lệ P2) và luôn đi kèm `expires_from_fact_id` trỏ về dữ
    kiện chu kỳ đã duyệt đã dùng.
    """

    __tablename__ = "calibration_record"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        String(128), ForeignKey("document.id"), nullable=True, index=True
    )
    extraction_id = Column(
        Integer, ForeignKey("extraction.id"), nullable=False, index=True
    )
    device_id = Column(Integer, ForeignKey("device.id"), nullable=True, index=True)
    procedure_id = Column(
        Integer, ForeignKey("procedure.id"), nullable=True, index=True
    )
    mode = Column(String(32), nullable=True)
    calibrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    expires_from_fact_id = Column(
        Integer, ForeignKey("procedure_fact.id"), nullable=True
    )
    verdict = Column(String(16), nullable=True)
    cert_no = Column(String(128), nullable=True)
    inspector_name = Column(String(255), nullable=True)
    reviewer_name = Column(String(255), nullable=True)
    lab_name = Column(String(255), nullable=True)
    env_temp_c = Column(Float, nullable=True)
    env_humidity_pct = Column(Float, nullable=True)
    # Nguyên văn toàn bộ hồ sơ đã đọc (P1), phòng khi quote cấp extraction bị cắt.
    source_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    extraction = relationship("Extraction")
    device = relationship("Device")
    procedure = relationship("Procedure")
    expires_from_fact = relationship("ProcedureFact", foreign_keys=[expires_from_fact_id])
    points = relationship(
        "MeasurementPoint", back_populates="record", order_by="MeasurementPoint.ord"
    )

    def __repr__(self) -> str:
        return f"<CalibrationRecord id={self.id} device_id={self.device_id} verdict={self.verdict}>"


class MeasurementPoint(Base):
    """Một dòng số liệu đo (spec §5.5).

    `quote` giữ nguyên văn dòng nguồn. `*_text` giữ nguyên chuỗi như tài liệu;
    các cột số chỉ là kết quả phân tích chuỗi đó. `error_value` LUÔN đọc từ tài
    liệu (P2), không bao giờ được tính lại từ `measured_value` và `nominal_value`.
    `within_limit` chỉ là cờ đối chiếu, điền khi cả `error_value` lẫn `limit_value`
    đều có nguồn, và luôn hiển thị kèm cả hai để người dùng tự kiểm.
    """

    __tablename__ = "measurement_point"

    id = Column(Integer, primary_key=True)
    record_id = Column(
        Integer, ForeignKey("calibration_record.id"), nullable=False, index=True
    )
    ord = Column(Integer, nullable=True)
    step_code = Column(String(32), nullable=True, index=True)
    label = Column(Text, nullable=True)
    nominal_value = Column(Float, nullable=True)
    measured_value = Column(Float, nullable=True)
    error_value = Column(Float, nullable=True)
    unit_id = Column(Integer, ForeignKey("unit.id"), nullable=True)
    limit_value = Column(Float, nullable=True)
    within_limit = Column(Integer, nullable=True)  # SQLite compat: int bool
    note = Column(Text, nullable=True)
    # P1: nguyên văn dòng và từng ô số gốc, để đối chiếu không cần mở tài liệu.
    quote = Column(Text, nullable=True)
    nominal_text = Column(Text, nullable=True)
    measured_text = Column(Text, nullable=True)
    error_text = Column(Text, nullable=True)
    limit_text = Column(Text, nullable=True)

    record = relationship("CalibrationRecord", back_populates="points")
    unit = relationship("Unit")

    def __repr__(self) -> str:
        return f"<MeasurementPoint id={self.id} record_id={self.record_id} ord={self.ord}>"
