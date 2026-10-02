import pytest

from ingestion.classify import classify_document


def test_classifies_qtkd_from_filename():
    result = classify_document("QTKD 1.061 2021 ND.docx")
    assert result.doc_type == "qtkd"
    assert result.confidence >= 0.95


def test_classifies_calibration_record_from_content():
    result = classify_document("record.docx", "Biên bản kiểm định phương tiện đo")
    assert result.doc_type == "ho_so_kiem_dinh"


def test_unknown_documents_are_not_guessed():
    result = classify_document("notes.docx", "Nội dung không theo mẫu")
    assert result.doc_type == "khac"
    assert result.confidence < 0.5


@pytest.mark.parametrize(
    "name",
    [
        "AP KE PITTONG-P2-BBKD-QTKD 1.159 2021.xlsx",
        "Biên bản kiểm định áp kế pittông SN 1045 2024-06-25.xlsx",
    ],
)
def test_spreadsheet_records_are_calibration_records(name):
    """Bảng tính theo mẫu biên bản (kể cả viết tắt BBKD) là hồ sơ kiểm định,
    không phải quy trình dù tên có kèm mã QTKĐ."""
    assert classify_document(name).doc_type == "ho_so_kiem_dinh"


def test_spreadsheet_measurement_sheet_is_phieu_do():
    result = classify_document("Phiếu đo Van an toàn SN-2026-111 E01.xlsx")
    assert result.doc_type == "phieu_do"


def test_qtkd_docx_still_classifies_as_procedure():
    assert classify_document("QTKD 1.061 2021 ND.docx").doc_type == "qtkd"


def test_qtkd_code_in_spreadsheet_is_not_a_procedure():
    """Bảng tính không bao giờ là quy trình: mã QTKĐ chỉ là tham chiếu."""
    assert classify_document("QTKD_1.159_bang_tinh.xlsx").doc_type != "qtkd"


@pytest.mark.parametrize(
    "name",
    [
        "BBKD-CT-026.docx",
        "BBKĐ_ghi_chu.docx",
        "bien-ban-BBKD-2026.xlsx",
    ],
)
def test_bbkd_abbreviation_is_a_record(name):
    """BBKĐ/BBKD đứng như một từ riêng là biên bản kiểm định, xét trước QTKĐ."""
    assert classify_document(name).doc_type == "ho_so_kiem_dinh"


def test_bbkd_requires_word_boundary():
    """'abbkdx' chỉ là chuỗi con, không phải viết tắt BBKD đứng riêng."""
    assert classify_document("abbkdx.docx").doc_type != "ho_so_kiem_dinh"


@pytest.mark.parametrize(
    "name",
    [
        "4. Bieu 1 Kiem dinh-Hieu chuan 2022 NAS 12.2022.doc",
        "7. Biểu 4 Danh mục QT 2022 NAS.doc",
        "10. Bieu 7 Danh sách KĐV (NAS).doc",
        "6. Bieu 3 Danh muc chuan mau 2022 NAS.xls",
        "Danh mục quy trình kiểm định 2024.xlsx",
        "Biểu 4/CN danh mục thiết bị.docx",
    ],
)
def test_nas_catalogs_are_danh_muc(name):
    """Biểu/danh mục/chuẩn mẫu/KĐV là danh mục, xét TRƯỚC quy trình."""
    assert classify_document(name).doc_type == "danh_muc"


def test_catalog_name_carrying_qtkd_abbrev_stays_procedure():
    """Tên mang chính viết tắt QTKĐ/QTKD vẫn là quy trình (F01 trùng nội dung)."""
    assert classify_document("Danh muc QTKD 9.001 sao luu.docx").doc_type == "qtkd"


def test_underscored_on_disk_names_classify_like_spaced_names():
    """Tên tệp trên đĩa dùng "_" thay dấu cách vẫn phải phân loại đúng."""
    assert (
        classify_document("Biên_bản_kiểm_định_áp_kế_pittông_SN_0391_2024-11-19.xlsx").doc_type
        == "ho_so_kiem_dinh"
    )
    assert classify_document("QTKĐ_9.001_2026_Van_an_toan.docx").doc_type == "qtkd"
