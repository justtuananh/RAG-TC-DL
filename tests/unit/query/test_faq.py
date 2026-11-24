"""Bộ câu hỏi - đáp án: câu hỏi khớp một câu trong bộ thì trả đúng đáp án, không qua LLM."""

from types import SimpleNamespace

import pytest

from query import faq

FAQ_MD = """BỘ CÂU HỎI VÀ ĐÁP ÁN


| STT | Câu hỏi | Đáp án |
| --- | --- | --- |
| 1 | Liên kết chuẩn đo lường là gì? | Theo TCVN 6165:2009, liên kết chuẩn đo lường là tính chất của kết quả đo. |
| 2 | Hệ SI gồm những đơn vị cơ bản nào? | Gồm 7 đơn vị cơ bản: / Độ dài: mét (m) / Khối lượng: kilôgam (kg) |
"""

OTHER_MD = "# 1 Phạm vi áp dụng\n\n| Cấp | bar |\n| --- | --- |\n| 1 | 2 |\n"


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    (tmp_path / "hoi_dap.md").write_text(FAQ_MD, encoding="utf-8")
    (tmp_path / "qtkd.md").write_text(OTHER_MD, encoding="utf-8")
    settings = SimpleNamespace(
        paths=SimpleNamespace(markdown_dir=str(tmp_path)),
        faq=SimpleNamespace(
            enabled=True,
            min_score=0.8,
            max_candidates=30,
            show_sources=True,
            answer_delay_s=0.0,
            stream_chunk_words=3,
            stream_interval_s=0.0,
            question_header_pattern=r"\bcau hoi\b",
            answer_header_pattern=r"\bdap an\b",
        ),
    )
    monkeypatch.setattr(faq, "get_settings", lambda: settings)
    monkeypatch.setattr(faq.router, "known_files", lambda: frozenset({"hoi_dap", "qtkd"}))
    faq._cached_pairs.cache_clear()
    return settings


def _scores(mapping):
    def score(query, docs):
        return [mapping.get(doc, 0.0) for doc in docs]

    return score


def test_parse_pairs_reads_question_answer_columns():
    pairs = faq.parse_pairs(FAQ_MD, r"\bcau hoi\b", r"\bdap an\b")
    assert [(p.number, p.question) for p in pairs] == [
        ("1", "Liên kết chuẩn đo lường là gì?"),
        ("2", "Hệ SI gồm những đơn vị cơ bản nào?"),
    ]


def test_parse_pairs_ignores_tables_without_question_answer_header():
    assert faq.parse_pairs(OTHER_MD, r"\bcau hoi\b", r"\bdap an\b") == []


def test_matching_question_returns_its_answer_not_a_table(corpus, monkeypatch):
    monkeypatch.setattr(
        faq.reranker, "score_documents", _scores({"Liên kết chuẩn đo lường là gì?": 0.97})
    )
    result = faq.try_faq_answer("liên kết chuẩn đo lường được hiểu là gì")
    assert result is not None
    assert result.text.startswith("Theo TCVN 6165:2009, liên kết chuẩn đo lường là tính chất")
    assert "|" not in result.text
    assert [h["payload"]["file_stem"] for h in result.hits] == ["hoi_dap"]
    assert "Câu 1" in result.hits[0]["payload"]["section_path"]


def test_slash_separated_answer_parts_become_lines(corpus, monkeypatch):
    monkeypatch.setattr(
        faq.reranker, "score_documents", _scores({"Hệ SI gồm những đơn vị cơ bản nào?": 0.95})
    )
    text = faq.try_faq_answer("Hệ SI gồm những đơn vị cơ bản nào?").text
    assert "Gồm 7 đơn vị cơ bản:\n- Độ dài: mét (m)\n- Khối lượng: kilôgam (kg)" in text


def test_weak_match_falls_back_to_rag(corpus, monkeypatch):
    monkeypatch.setattr(
        faq.reranker, "score_documents", _scores({"Liên kết chuẩn đo lường là gì?": 0.3})
    )
    assert faq.try_faq_answer("Điều kiện kiểm định bàn tạo áp?") is None


def test_disabled_or_reranker_error_falls_back(corpus, monkeypatch):
    def boom(query, docs):
        raise RuntimeError("reranker down")

    monkeypatch.setattr(faq.reranker, "score_documents", boom)
    assert faq.try_faq_answer("Liên kết chuẩn đo lường là gì?") is None
    corpus.faq.enabled = False
    assert faq.try_faq_answer("Liên kết chuẩn đo lường là gì?") is None
