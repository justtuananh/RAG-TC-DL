"""Liệt kê QTKĐ theo chủ đề từ hồ sơ tài liệu - query.doc_catalog."""

import pytest

from query import doc_catalog
from retrieval.doc_profile import DocCode, DocProfile


def _profile(stem, number, title, scope, subject):
    return DocProfile(
        stem, DocCode("QTKĐ", number, 2021), title, "1 Phạm vi áp dụng", scope, (), (), subject
    )


PROFILES = {
    "BTA": _profile(
        "BTA",
        "1.062",
        "BÀN TẠO ÁP CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar",
        "Quy trình cho bàn tạo áp.",
        "ban tao ap",
    ),
    "VAT": _profile(
        "VAT",
        "1.061",
        "VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar",
        "Quy trình cho van an toàn.",
        "van an toan",
    ),
    "LO": _profile(
        "LO", "1.197", "LÒ NHIỆT ĐỘ CHUẨN KIỂU TCH-1200", "Quy trình cho lò.", "lo nhiet do chuan"
    ),
    "NK": _profile(
        "NK",
        "1.106",
        "Nhiệt kế thủy tinh chất lỏng",
        "Quy trình cho nhiệt kế.",
        "nhiet ke thuy tinh chat long",
    ),
    "DT": _profile(
        "DT",
        "1.085",
        "Phương tiện đo dung tích",
        "Quy trình cho dụng cụ đo dung tích. Dùng ở nhiệt độ 20 oC.",
        "phuong tien do dung tich",
    ),
}


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.setattr(doc_catalog.router, "known_files", lambda: frozenset(PROFILES))
    monkeypatch.setattr(doc_catalog.doc_profile, "profile_for", PROFILES.get)


def test_topic_extraction():
    assert doc_catalog.topic_of("Những QTKĐ nào liên quan đến đo nhiệt độ?") == "nhiet do"
    assert doc_catalog.topic_of(
        "Có những quy trình nào áp dụng cho thiết bị có phạm vi làm việc đến 1 400 bar?"
    ) == ("pham vi lam viec den 1 400 bar")
    assert doc_catalog.topic_of("QTKĐ 1.061 dùng để làm gì?") is None


def test_lists_every_document_whose_title_matches(catalog):
    answer = doc_catalog.try_catalog_answer(
        "Những QTKĐ nào liên quan đến thiết bị có phạm vi làm việc đến 1 400 bar?"
    )
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


SCOPE_PROFILES = {
    "A_01": DocProfile(
        "A_01", None, "ÁP KẾ PITTÔNG CHUẨN FLUKE 7302 (SỐ HIỆU: 1274)", "", "", (), (), ""
    ),
    "A_06": DocProfile(
        "A_06", None, "ÁP KẾ PÍTTÔNG CHUẨN МП-600 (SỐ HIỆU: 994)", "", "", (), (), ""
    ),
    **PROFILES,
}


@pytest.fixture
def scoped(monkeypatch, settings_override):
    from retrieval import doc_scope

    settings_override(
        {
            "doc_scopes.scopes": [
                {
                    "name": "chuan_mau",
                    "label": "Thiết bị chuẩn mẫu",
                    "question_pattern": r"\bthiet bi chuan mau\b",
                    "stem_pattern": "^A_",
                    "priority": True,
                }
            ]
        }
    )
    monkeypatch.setattr(doc_catalog.router, "known_files", lambda: frozenset(SCOPE_PROFILES))
    monkeypatch.setattr(doc_catalog.router, "route_files", lambda q: frozenset())
    monkeypatch.setattr(doc_catalog.doc_profile, "profile_for", SCOPE_PROFILES.get)
    doc_scope.invalidate()
    yield
    doc_scope.invalidate()


@pytest.mark.parametrize(
    "question",
    [
        "Những thiết bị chuẩn mẫu nào có trong kho tài liệu?",
        "Liệt kê các thiết bị chuẩn mẫu",
        "Có bao nhiêu thiết bị chuẩn mẫu?",
    ],
)
def test_scope_listing_names_every_document_of_the_category(scoped, question):
    answer = doc_catalog.try_scope_listing(question)
    assert answer.text.splitlines() == [
        "Kho tài liệu có 2 tài liệu thuộc nhóm **Thiết bị chuẩn mẫu**:",
        "",
        "- ÁP KẾ PITTÔNG CHUẨN FLUKE 7302 (SỐ HIỆU: 1274) [1]",
        "- ÁP KẾ PÍTTÔNG CHUẨN МП-600 (SỐ HIỆU: 994) [2]",
    ]
    assert [h["payload"]["file_stem"] for h in answer.hits] == ["A_01", "A_06"]


@pytest.mark.parametrize(
    "question",
    [
        "Thiết bị chuẩn mẫu nào đo được áp suất tuyệt đối?",  # có điều kiện lọc: để RAG trả lời
        "Những thiết bị chuẩn mẫu nào có cấp chính xác 0,01?",
        "Những QTKĐ nào có trong kho?",  # không thuộc loại câu hỏi nào
    ],
)
def test_scope_listing_leaves_filtered_or_unscoped_questions_to_rag(scoped, question):
    assert doc_catalog.try_scope_listing(question) is None
