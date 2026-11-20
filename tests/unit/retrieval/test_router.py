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


def test_device_aliases_match_without_accents_or_unicode_composition(mapping, monkeypatch):
    import unicodedata

    monkeypatch.setattr(router_mod, '_device_aliases', {'bình phân ly': ('1.063',)})
    assert route('BINH PHAN LY cần điều kiện gì') == mapping['1.063']
    assert route(unicodedata.normalize('NFD', 'bình phân ly')) == mapping['1.063']


def test_device_alias_does_not_match_inside_another_word(mapping, monkeypatch):
    monkeypatch.setattr(router_mod, '_device_aliases', {'dpi': ('1.190',)})
    assert route('abcdpixyz') is None


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


@pytest.fixture
def collided(mapping, monkeypatch):
    """Hai tài liệu cùng số 1.062: bản 2021 giữ dòng procedure, bản 2016 (thiết bị khác) chỉ được nhúng."""
    mapping["1.062"] = "QTKD_1.062_2021_ND_2"
    extras = frozenset({"QTKĐ_1.062_2016_2", "TCVN_ISO_IEC17025_2017_2"})
    monkeypatch.setattr(router_mod, "_extra_stems", extras)
    return mapping


def test_known_files_include_indexed_documents_without_procedure(collided):
    # Câu hỏi không nêu thiết bị chạy phễu riêng cho từng file trong known_files: tài liệu thiếu dòng
    # procedure (TCVN, QTKĐ cùng số) trước đây không bao giờ được tìm.
    known = router_mod.known_files()
    assert {"QTKĐ_1.062_2016_2", "TCVN_ISO_IEC17025_2017_2"} <= known
    assert collided["1.061"] in known


def test_number_shared_by_two_documents_routes_to_both(collided):
    both = frozenset({"QTKD_1.062_2021_ND_2", "QTKĐ_1.062_2016_2"})
    assert route_files("QTKĐ 1.062 là quy trình gì") == both
    assert route("QTKĐ 1.062 là quy trình gì") is None  # mơ hồ: không ghim nhầm một file


def test_year_narrows_a_shared_number(collided):
    assert route("QTKĐ 1.062:2016 áp dụng cho thiết bị nào") == "QTKĐ_1.062_2016_2"
    assert route("QTKĐ 1.062 : 2021 áp dụng cho thiết bị nào") == "QTKD_1.062_2021_ND_2"
    # Năm không khớp tài liệu nào: giữ cả hai thay vì mất hết.
    assert len(route_files("QTKĐ 1.062:1999")) == 2


def test_number_unique_to_one_document_is_still_pinned(collided):
    assert route("phạm vi của 1.061 là gì") == collided["1.061"]


@pytest.fixture
def profiled(mapping, monkeypatch):
    monkeypatch.setattr(router_mod, "_extra_stems", frozenset())
    mapping["1.033"] = "QTKĐ_1.033_2021_2"
    mapping["1.062"] = "QTKD_1.062_2021_ND_2"
    index = (
        ("TCVN6165_1996_905114_2", "6165", (), "do luong hoc"),
        ("TCVN_ISO_IEC17025_2017_2", "17025", (), ""),
        ("QTKĐ_1.197_2024_2", None, ("tch1200",), "lo nhiet do chuan"),
        ("QTKD_1.071_2022_FINAL_2", None, ("h3000sp70700", "h3000"), "ap ke pit tong"),
        ("QTKĐ_1.213_2025_2", None, (), "luu luong ke chat long"),
        ("QTKĐ_1.033_2021_2", None, (), "ban tao ap"),
        ("QTKD_1.062_2021_ND_2", None, (), "ban tao ap"),
    )
    monkeypatch.setattr(router_mod, "_profile_index", index)
    return mapping


def test_tcvn_and_iso_codes_pin_their_document(profiled):
    assert route("TCVN 6165:1996 là tài liệu gì?") == "TCVN6165_1996_905114_2"
    assert route("TCVN ISO/IEC 17025:2017 nói về nội dung gì?") == "TCVN_ISO_IEC17025_2017_2"
    assert route("ISO 17025 yêu cầu gì") == "TCVN_ISO_IEC17025_2017_2"
    assert route("áp suất 6165 bar") is None  # số trần không kèm TCVN/ISO thì không ghim


def test_device_model_keyword_pins_its_document(profiled):
    assert route("Chu kỳ kiểm định lò TCH 1200?") == "QTKĐ_1.197_2024_2"
    assert route("áp kế pít tông H3000 dùng để làm gì") == "QTKD_1.071_2022_FINAL_2"


def test_subject_from_document_title_pins_its_document(profiled):
    # Tên đối tượng lấy từ tên tài liệu khi nạp: không cần khai báo alias thiết bị trong CSDL.
    stems = route_files("So sánh chu kỳ kiểm định của van an toàn và của lưu lượng kế chất lỏng.")
    assert stems == frozenset({"QTKD_1.061_2021_ND_V2", "QTKĐ_1.213_2025_2"})
    assert route("Chu kỳ kiểm định LƯU LƯỢNG KẾ CHẤT LỎNG") == "QTKĐ_1.213_2025_2"
    assert route("lưu lượng kế khí") is None  # phải khớp trọn tên, không khớp một phần


def test_name_shared_by_two_documents_confirms_the_explicit_number(profiled):
    # "bàn tạo áp" là cả 1.033 và 1.062: câu đã nêu 1.062:2021 thì không kéo thêm 1.033.
    assert (
        route("Điều kiện kiểm định bàn tạo áp theo QTKĐ 1.062:2021 là gì?")
        == "QTKD_1.062_2021_ND_2"
    )
    assert len(route_files("Điều kiện kiểm định bàn tạo áp")) == 2
    # Tên lấy từ tên tài liệu là tên loại thiết bị: số QTKĐ đã nêu quyết định ("áp kế pít tông theo 1.159").
    assert route("áp kế pít tông theo QTKĐ 1.061") == "QTKD_1.061_2021_ND_V2"


def test_model_keyword_does_not_match_a_longer_model_number(profiled, monkeypatch):
    # "mp6" (МП-6) là đầu của "mp600" (МП-600): khớp kiểu phải dừng ở ranh giới số.
    index = (
        ("A_04_Ap_ke_pittong_MP_6_5393_2", None, ("mp6",), ""),
        ("A_06_Ap_ke_pittong_MP_600_994_2", None, ("mp600",), ""),
    )
    monkeypatch.setattr(router_mod, "_profile_index", index)
    assert route("Cách vận hành MP-600") == "A_06_Ap_ke_pittong_MP_600_994_2"
    assert route("MP-6 đo được tới bao nhiêu kPa") == "A_04_Ap_ke_pittong_MP_6_5393_2"


def test_family_name_that_prefixes_other_subjects_does_not_pin(monkeypatch):
    # 1.139 "Áp kế kiểu lò xo ..." cho tên đối tượng chỉ còn "áp kế": tên họ thiết bị chung, là phần đầu
    # của tên tài liệu khác ("áp kế pittông ..."), nên không ghim 1.139 cho mọi câu có "áp kế".
    monkeypatch.setattr(router_mod, "_number_to_stem", {})
    monkeypatch.setattr(router_mod, "_extra_stems", frozenset())
    monkeypatch.setattr(router_mod, "_device_aliases", {})
    monkeypatch.setattr(
        router_mod.doc_profile,
        "profile_for",
        lambda stem: router_mod.doc_profile.DocProfile(
            stem, None, "", "", "", (), {"A_04": ("mp6",)}.get(stem, ()), SUBJECTS[stem]
        ),
    )
    monkeypatch.setattr(router_mod, "known_files", lambda: frozenset(SUBJECTS))
    monkeypatch.setattr(router_mod, "_profile_index", None)
    assert route_files("Áp kế MP-6 đo được tới bao nhiêu kPa?") == {"A_04"}
    assert route_files("chu kỳ kiểm định áp kế pittông") == {"QTKD_1.159"}


SUBJECTS = {"QTKĐ_1.139": "ap ke", "QTKD_1.159": "ap ke pittong", "A_04": "ap ke pittong chuan"}


def test_number_missing_from_procedure_table_falls_back_to_file_name(monkeypatch):
    # Dòng procedure của QTKĐ_1.141 từng mang số 1.137 (đọc nhầm từ danh sách viện dẫn).
    monkeypatch.setattr(router_mod, "_number_to_stem", {"1.137": "QTKĐ_1.141_2020_2"})
    monkeypatch.setattr(router_mod, "_extra_stems", frozenset())
    monkeypatch.setattr(router_mod, "_device_aliases", {})
    monkeypatch.setattr(router_mod, "_profile_index", ())
    assert route_files("QTKĐ 1.141 kiểm tra những gì") == {"QTKĐ_1.141_2020_2"}


def test_two_word_family_name_never_pins_alone(monkeypatch):
    # "áp kế" (1.139) mở đầu tên tài liệu khác: câu "áp kế chênh áp ПКУ-М" không được ghim sang 1.139.
    subjects = {
        "QTKĐ_1.139": "ap ke",
        "QTKD_1.159": "ap ke pittong",
        "QTKĐ_1.140": "ap ke do chenh lech ap suat",
    }
    monkeypatch.setattr(router_mod, "_number_to_stem", {})
    monkeypatch.setattr(router_mod, "_extra_stems", frozenset())
    monkeypatch.setattr(router_mod, "_device_aliases", {})
    monkeypatch.setattr(
        router_mod.doc_profile,
        "profile_for",
        lambda stem: router_mod.doc_profile.DocProfile(
            stem, None, "", "", "", (), (), subjects[stem]
        ),
    )
    monkeypatch.setattr(router_mod, "known_files", lambda: frozenset(subjects))
    monkeypatch.setattr(router_mod, "_profile_index", None)
    assert route_files("Kiểm tra độ kín của áp kế chênh áp ПКУ-М") == frozenset()
    assert route_files("chu kỳ kiểm định áp kế pittông") == {"QTKD_1.159"}


def test_device_name_picks_one_of_two_documents_sharing_a_number(collided, monkeypatch):
    # 1.062 là cả bàn tạo áp (2021) và cột đo xăng dầu (2016): tên thiết bị trong câu chọn đúng tài liệu.
    monkeypatch.setattr(router_mod, "_device_aliases", {"bàn tạo áp": ("1.062",)})
    both = route_files("QTKĐ 1.062 là quy trình gì")
    assert len(both) == 2
    picked = route_files("Điều kiện kiểm định bàn tạo áp QTKĐ 1.062?")
    assert len(picked) == 1 and picked < both
