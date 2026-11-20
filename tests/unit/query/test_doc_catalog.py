"""Liệt kê QTKĐ theo chủ đề từ hồ sơ tài liệu - query.doc_catalog."""

import pytest

from query import doc_catalog
from retrieval.doc_profile import DocCode, DocProfile


def _profile(stem, number, title, scope, subject):
    return DocProfile(stem, DocCode("QTKĐ", number, 2021), title, "1 Phạm vi áp dụng", scope, (), (), subject)


PROFILES = {
    "BTA": _profile("BTA", "1.062", "BÀN TẠO ÁP CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar", "Quy trình cho bàn tạo áp.", "ban tao ap"),
    "VAT": _profile("VAT", "1.061", "VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar", "Quy trình cho van an toàn.", "van an toan"),
    "LO": _profile("LO", "1.197", "LÒ NHIỆT ĐỘ CHUẨN KIỂU TCH-1200", "Quy trình cho lò.", "lo nhiet do chuan"),
    "NK": _profile("NK", "1.106", "Nhiệt kế thủy tinh chất lỏng", "Quy trình cho nhiệt kế.", "nhiet ke thuy tinh chat long"),
    "DT": _profile("DT", "1.085", "Phương tiện đo dung tích", "Quy trình cho dụng cụ đo dung tích. Dùng ở nhiệt độ 20 oC.", "phuong tien do dung tich"),
}


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.setattr(doc_catalog.router, "known_files", lambda: frozenset(PROFILES))
    monkeypatch.setattr(doc_catalog.doc_profile, "profile_for", PROFILES.get)


def test_topic_extraction():
    assert doc_catalog.topic_of("Những QTKĐ nào liên quan đến đo nhiệt độ?") == "nhiet do"
    assert doc_catalog.topic_of("Có những quy trình nào áp dụng cho thiết bị có phạm vi làm việc đến 1 400 bar?") == (
        "pham vi lam viec den 1 400 bar"
    )
    assert doc_catalog.topic_of("QTKĐ 1.061 dùng để làm gì?") is None


def test_lists_every_document_whose_title_matches(catalog):
    answer = doc_catalog.try_catalog_answer("Những QTKĐ nào liên quan đến thiết bị có phạm vi làm việc đến 1 400 bar?")
    assert answer.text.splitlines()[2:] == [
        "- **QTKĐ 1.061:2021** - VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar [1]",
        "- **QTKĐ 1.062:2021** - BÀN TẠO ÁP CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar [2]",
    ]
    assert [h["payload"]["file_stem"] for h in answer.hits] == ["VAT", "BTA"]


def test_short_topic_matches_the_head_noun_of_the_subject_only(catalog):
    answer = doc_catalog.try_catalog_answer("Những QTKĐ nào liên quan đến đo nhiệt độ?")
    # "nhiệt độ" trong tên lò; "nhiệt" là từ trong tên nhiệt kế; dung tích nhắc 20 oC ở câu sau: không tính.
    assert [h["payload"]["file_stem"] for h in answer.hits] == ["NK", "LO"]


def test_no_match_or_disabled_goes_to_rag(catalog, settings_override):
    assert doc_catalog.try_catalog_answer("Những QTKĐ nào liên quan đến khối lượng?") is None
    settings_override({"doc_catalog.enabled": False})
    assert doc_catalog.try_catalog_answer("Những QTKĐ nào liên quan đến đo nhiệt độ?") is None
