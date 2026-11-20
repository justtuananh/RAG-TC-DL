"""Phạm vi tài liệu theo loại câu hỏi - retrieval.doc_scope + nối vào router / retriever."""

import pytest

import retrieval.retriever as R
import retrieval.router as router_mod
from retrieval import doc_profile, doc_scope
from retrieval.doc_profile import DocProfile, Section

KNOWN = frozenset(
    {
        "A_04_Ap_ke_pittong_MP_6_5393_2",
        "A_06_Ap_ke_pittong_MP_600_994_2",
        "QTKD_1.159_2021_ND_FINAL_2",
        "QTKĐ_1.106_2018_2",
        "TCVN6165_1996_905114_2",
    }
)
TITLES = {
    "A_04_Ap_ke_pittong_MP_6_5393_2": ("ÁP KẾ PÍTTÔNG CHUẨN МП-6 (SỐ HIỆU: 5393)", ()),
    "A_06_Ap_ke_pittong_MP_600_994_2": ("ÁP KẾ PÍTTÔNG CHUẨN МП-600 (SỐ HIỆU: 994)", ()),
    "QTKD_1.159_2021_ND_FINAL_2": ("ÁP KẾ PÍTTÔNG CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar", ()),
    "QTKĐ_1.106_2018_2": (
        "Nhiệt kế thủy tinh chất lỏng",
        (Section("2", "Thuật ngữ và định nghĩa", 1),),
    ),
    "TCVN6165_1996_905114_2": ("ĐO LƯỜNG HỌC – THUẬT NGỮ CHUNG VÀ CƠ BẢN", ()),
}
SCOPES = [
    {
        "name": "chuan_mau",
        "question_pattern": r"\bthiet bi chuan mau\b",
        "stem_pattern": "^A_",
        "priority": True,
    },
    {"name": "ap_suat", "question_pattern": r"\bap ke\b", "title_pattern": r"\bap ke\b"},
    {"name": "nhiet_do", "question_pattern": r"\bnhiet ke\b", "title_pattern": r"\bnhiet\b"},
    {
        "name": "thuat_ngu",
        "question_pattern": r"\bthuat ngu\b",
        "title_pattern": r"\bthuat ngu\b",
        "section_pattern": r"\bthuat ngu\b",
    },
]


@pytest.fixture(autouse=True)
def scopes(monkeypatch, settings_override):
    settings_override({"doc_scopes.scopes": SCOPES, "doc_scopes.fallback_min_score": 0.1})

    def profile(stem):
        title, sections = TITLES[stem]
        return DocProfile(stem, None, title, "", "", sections, ())

    monkeypatch.setattr(doc_profile, "profile_for", profile)
    doc_scope.invalidate()
    yield
    doc_scope.invalidate()


def test_chuan_mau_question_selects_only_a_documents():
    scope = doc_scope.match("Thiết bị chuẩn mẫu nào đo được áp suất tuyệt đối?", KNOWN)
    assert scope.stems == {"A_04_Ap_ke_pittong_MP_6_5393_2", "A_06_Ap_ke_pittong_MP_600_994_2"}
    assert scope.priority


def test_priority_scope_is_not_widened_by_other_matching_scopes():
    # "áp kế" cũng khớp loại áp suất (kéo QTKĐ 1.159), nhưng "thiết bị chuẩn mẫu" thắng.
    scope = doc_scope.match("Thiết bị chuẩn mẫu áp kế píttông có dải đo bao nhiêu", KNOWN)
    assert scope.names == ("chuan_mau",)
    assert all(stem.startswith("A_") for stem in scope.stems)


def test_ordinary_scopes_select_by_title_and_section_and_union():
    assert doc_scope.match("áp kế có cấp chính xác nào", KNOWN).stems == {
        "A_04_Ap_ke_pittong_MP_6_5393_2",
        "A_06_Ap_ke_pittong_MP_600_994_2",
        "QTKD_1.159_2021_ND_FINAL_2",
    }
    # Thuật ngữ: TCVN 6165 (theo tên) và QTKĐ có mục "Thuật ngữ và định nghĩa".
    assert doc_scope.match("thuật ngữ độ không đảm bảo đo", KNOWN).stems == {
        "TCVN6165_1996_905114_2",
        "QTKĐ_1.106_2018_2",
    }
    both = doc_scope.match("so sánh áp kế và nhiệt kế", KNOWN)
    assert both.names == ("ap_suat", "nhiet_do") and "QTKĐ_1.106_2018_2" in both.stems


def test_no_scope_for_unrelated_question_or_when_disabled(settings_override):
    assert doc_scope.match("chu kỳ kiểm định là bao lâu", KNOWN) is None
    settings_override({"doc_scopes.enabled": False})
    assert doc_scope.match("thiết bị chuẩn mẫu", KNOWN) is None


def test_restrict_named_keeps_only_documents_in_the_priority_group():
    named = frozenset({"QTKD_1.159_2021_ND_FINAL_2", "A_06_Ap_ke_pittong_MP_600_994_2"})
    assert doc_scope.restrict_named("thiết bị chuẩn mẫu MP-600", named, KNOWN) == {
        "A_06_Ap_ke_pittong_MP_600_994_2"
    }
    assert (
        doc_scope.restrict_named("áp kế MP-600", named, KNOWN) == named
    )  # loại thường: router quyết định


@pytest.fixture
def routed(monkeypatch):
    monkeypatch.setattr(router_mod, "_number_to_stem", {"1.159": "QTKD_1.159_2021_ND_FINAL_2"})
    monkeypatch.setattr(router_mod, "_extra_stems", KNOWN - {"QTKD_1.159_2021_ND_FINAL_2"})
    monkeypatch.setattr(router_mod, "_device_aliases", {"áp kế píttông": ("1.159",)})
    monkeypatch.setattr(router_mod, "_profile_index", ())


def test_router_drops_generic_device_name_outside_the_chuan_mau_group(routed):
    assert router_mod.route_files("áp kế píttông dùng để làm gì") == {"QTKD_1.159_2021_ND_FINAL_2"}
    assert router_mod.route_files("thiết bị chuẩn mẫu áp kế píttông dùng để làm gì") == frozenset()


def test_explicit_qtkd_number_beats_the_priority_scope(routed):
    assert router_mod.route_files("thiết bị chuẩn mẫu theo QTKĐ 1.159") == {
        "QTKD_1.159_2021_ND_FINAL_2"
    }


def _hit(stem, score):
    return {"payload": {"file_stem": stem, "chunk_id": stem, "text": "t"}, "rerank_score": score}


def test_retriever_searches_only_the_scope_files(monkeypatch):
    monkeypatch.setattr(R.router, "known_files", lambda: KNOWN)
    seen = []

    def coverage(query, vec, expanded, *, top_k, files):
        seen.append(sorted(files))
        return [_hit(f, 0.9) for f in sorted(files)]

    monkeypatch.setattr(R, "_retrieve_coverage", coverage)
    hits = R._retrieve_scoped("thiết bị chuẩn mẫu đo áp suất", "q", [], "q", top_k=50, top_n=5)
    assert seen == [["A_04_Ap_ke_pittong_MP_6_5393_2", "A_06_Ap_ke_pittong_MP_600_994_2"]]
    assert {h["payload"]["file_stem"] for h in hits} == set(seen[0])


def test_retriever_falls_back_to_whole_corpus_when_scope_has_no_confident_source(monkeypatch):
    monkeypatch.setattr(R.router, "known_files", lambda: KNOWN)
    monkeypatch.setattr(
        R, "_retrieve_coverage", lambda *a, **k: [_hit("A_04_Ap_ke_pittong_MP_6_5393_2", 0.02)]
    )
    assert R._retrieve_scoped("thiết bị chuẩn mẫu", "q", [], "q", top_k=50, top_n=5) == []


def test_single_document_scope_uses_the_pinned_search(monkeypatch):
    monkeypatch.setattr(R.router, "known_files", lambda: KNOWN)
    pinned = []
    monkeypatch.setattr(
        R, "_retrieve_single", lambda q, v, e, stem, **k: pinned.append(stem) or [_hit(stem, 0.8)]
    )
    R._retrieve_scoped("nhiệt kế thủy tinh", "q", [], "q", top_k=50, top_n=5)
    assert pinned == ["QTKĐ_1.106_2018_2"]
