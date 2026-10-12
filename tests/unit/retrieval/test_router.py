"""QTKĐ file-stem router - retrieval.router.route + _NUMBER_RE.

ĐÚNG 1 tín hiệu phân biệt (số QTKĐ hoặc alias thiết bị) → ghim file; 0 hoặc ≥2
(câu so sánh nhiều thiết bị / số mâu thuẫn alias) → None = tìm toàn kho.
Mapping number→stem được set thẳng (bỏ qua bước scroll Qdrant).
"""

import pytest

import retrieval.router as router_mod
from retrieval.router import _NUMBER_RE, route, route_files


@pytest.fixture
def mapping(monkeypatch):
    m = {
        "1.061": "QTKD_1.061_2021_ND_V2",
        "1.063": "QTKD_1.063_2021_BPL",
        "1.159": "QTKD_1.159_2021_ND_FINAL",
        "1.160": "QTKD_1.160_2021_ND_FINAL",
        "1.190": "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24",
    }
    monkeypatch.setattr(router_mod, "_number_to_stem", m)
    return m


def test_explicit_number(mapping):
    assert route("phạm vi của 1.061 là gì") == mapping["1.061"]
    assert route("1.160 quy định gì") == mapping["1.160"]


def test_device_alias(mapping):
    assert route("kiểm định van an toàn") == mapping["1.061"]
    assert route("akkđ là gì") == mapping["1.160"]
    assert route("dpi 610") == mapping["1.190"]
    assert route("dpi610") == mapping["1.190"]


def test_alias_spelling_variants(mapping):
    # "píttông" (có dấu í) và đảo trật tự "pittông áp kế" đều phải bắt được 1.159.
    assert route("áp kế píttông tiêu chuẩn") == mapping["1.159"]
    assert route("thời gian quay tự do pittông áp kế") == mapping["1.159"]


def test_number_with_matching_alias_stays_pinned(mapping):
    # Số + alias CÙNG file → vẫn 1 tín hiệu phân biệt → ghim.
    assert route("điều kiện kiểm định bình phân ly QTKĐ 1.063") == mapping["1.063"]


def test_conflicting_number_and_alias_returns_none(mapping):
    # Alias "van an toàn"(1.061) mâu thuẫn số 1.063 → mơ hồ → toàn kho.
    assert route("van an toàn theo 1.063") is None


def test_multi_device_comparison_returns_none(mapping):
    # Câu so sánh 2 thiết bị: ghim 1 file làm nửa kia không bao giờ retrieve được.
    assert route("so sánh nhiệt độ khi kiểm định van an toàn (1.061) và 1.159") is None
    assert route("độ ẩm của van an toàn so với áp kế píttông tiêu chuẩn") is None


def test_no_signal_returns_none(mapping):
    assert route("1400 bar") is None
    assert route("sai số 0.05") is None
    assert route("câu hỏi chung không có mã hay tên thiết bị") is None


def test_number_present_but_not_in_mapping(mapping):
    # 9.999 khớp regex nhưng không có trong mapping → None (không alias) .
    assert route("tiêu chuẩn 9.999") is None


def test_number_re_pattern():
    assert _NUMBER_RE.search("1.061").group(1) == "1.061"
    assert _NUMBER_RE.search("mã 1.160 đây").group(1) == "1.160"
    assert _NUMBER_RE.search("6.3") is None  # chỉ 1 chữ số sau dấu chấm
    assert _NUMBER_RE.search("0.05") is None  # chỉ 2 chữ số
    assert _NUMBER_RE.search("1400") is None  # không có dấu chấm


def test_route_files_returns_all_distinct_stems(mapping):
    stems = route_files("so sánh van an toàn (1.061) và áp kế píttông tiêu chuẩn")
    assert stems == frozenset({mapping["1.061"], mapping["1.159"]})
    assert route_files("không có gì") == frozenset()
    assert route_files("kiểm định bình phân ly") == frozenset({mapping["1.063"]})


class _FakePoint:
    def __init__(self, stem):
        self.payload = {"file_stem": stem}


class _FakeClient:
    def __init__(self, stems):
        self._points = [_FakePoint(s) for s in stems]

    def scroll(self, **_kwargs):
        return self._points, None


def test_number_map_accepts_uploaded_stem_with_d_stroke(monkeypatch):
    """Tệp tải lên giữ chữ "Đ" trong tên ("QTKĐ 9.001 ...docx" → stem
    "QTKĐ_9.001_..."): số QTKĐ vẫn phải map được về stem đó."""
    stems = ["QTKD_1.061_2021_ND_V2", "QTKĐ_9.001_2026_Van_an_toan"]
    monkeypatch.setattr(router_mod, "_load_db_number_map", lambda: None)
    monkeypatch.setattr(router_mod.qdrant, "get_client", lambda: _FakeClient(stems))
    monkeypatch.setattr(router_mod.qdrant, "collection_name", lambda: "c")

    assert router_mod._build_number_to_stem() == {
        "1.061": "QTKD_1.061_2021_ND_V2",
        "9.001": "QTKĐ_9.001_2026_Van_an_toan",
    }


def test_invalidate_drops_cached_maps(mapping, monkeypatch):
    """Sau khi nhúng/xóa tài liệu, router phải dựng lại map số và alias thiết bị
    thay vì giữ bản cũ tới khi khởi động lại API."""
    monkeypatch.setattr(router_mod, "_device_aliases", {"x": ("1.061",)})

    router_mod.invalidate()

    assert router_mod._number_to_stem is None
    assert router_mod._device_aliases is None


def test_number_map_fallback_is_deterministic_and_prefers_newest(monkeypatch):
    """Không đọc được DB: hai phiên bản cùng số QTKĐ trong Qdrant phải luôn map
    về cùng một file (bản mới hơn), không phụ thuộc thứ tự duyệt ``set``."""
    old, new = "QTKD_1.061_2016_ND", "QTKD_1.061_2021_ND_V2"
    monkeypatch.setattr(router_mod, "_load_db_number_map", lambda: None)
    monkeypatch.setattr(router_mod.qdrant, "collection_name", lambda: "c")
    for order in ([old, new], [new, old]):
        monkeypatch.setattr(router_mod.qdrant, "get_client", lambda o=order: _FakeClient(o))
        assert router_mod._build_number_to_stem() == {"1.061": new}


@pytest.fixture
def procedure_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import db as db_pkg
    from db.models import Base, Document, DocumentType, Procedure

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db_pkg, "SessionLocal", factory)

    def add(stem: str, number: str | None) -> None:
        session = factory()
        session.add(
            Document(
                id=stem,
                file_stem=stem,
                display_name=f"{stem}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256=stem.ljust(64, "0")[:64],
                size_bytes=1,
            )
        )
        if number is not None:
            session.add(Procedure(number=number, document_id=stem))
        session.commit()
        session.close()

    yield add
    engine.dispose()


def test_number_map_reads_procedure_table(procedure_db, monkeypatch):
    """Bảng ``procedure`` là nguồn sự thật: số lấy từ đầu mục văn bản nên tệp tên
    không theo mẫu "QTKD_x.xxx" vẫn được ghim, và bản cũ (không còn là chủ dòng
    procedure) không bao giờ được chọn."""
    procedure_db("Quy_trinh_ap_ke_lo_xo", "1.088")
    procedure_db("QTKD_1.061_2026_ND", "1.061")
    procedure_db("QTKD_1.061_2016_ND", None)  # phiên bản cũ
    monkeypatch.setattr(
        router_mod.qdrant, "get_client", lambda: pytest.fail("không được quét Qdrant")
    )

    assert router_mod._build_number_to_stem() == {
        "1.088": "Quy_trinh_ap_ke_lo_xo",
        "1.061": "QTKD_1.061_2026_ND",
    }
