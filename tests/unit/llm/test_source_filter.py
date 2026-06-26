"""Regression cho generation.filter_by_confidence — cắt đuôi nguồn điểm thấp.

Reranker trả điểm sigmoid [0,1]; câu hẹp có đuôi điểm ~0 (nhiễu) cần bị loại khỏi
panel + ngữ cảnh LLM. Giữ nguồn top + nguồn ≥ max(ABS_FLOOR, REL_FLOOR×top).
Dữ liệu điểm lấy từ truy vấn thật (đo 2026-06-26).
"""

from generation import SOURCE_ABS_FLOOR, SOURCE_REL_FLOOR, filter_by_confidence


def _mk(scores):
    return [{"rerank_score": s, "payload": {"file_stem": f"f{i}"}} for i, s in enumerate(scores)]


def _scores(results):
    return [round(r["rerank_score"], 4) for r in results]


def test_rong_thi_tra_ve_rong():
    assert filter_by_confidence([]) == []


def test_luon_giu_it_nhat_nguon_top():
    # mọi điểm đều thấp → vẫn giữ nguồn mạnh nhất (1 nguồn)
    out = filter_by_confidence(_mk([0.04, 0.01, 0.0]))
    assert _scores(out) == [0.04]


def test_cau_hep_cat_duoi_nhieu():
    # Q "Phạm vi van an toàn": [0.77, 0.12, 0.09, 0.03, 0.009] → chỉ giữ nguồn top
    out = filter_by_confidence(_mk([0.7731, 0.1217, 0.0919, 0.0306, 0.0093]))
    assert _scores(out) == [0.7731]


def test_cau_trung_giu_vai_nguon():
    # Q "Sai số van an toàn": [0.63, 0.49, 0.22, 0.12, 0.06]
    # floor = max(0.08, 0.20*0.63=0.126)=0.126 → giữ 0.63, 0.49, 0.22
    out = filter_by_confidence(_mk([0.63, 0.4869, 0.2234, 0.1243, 0.0613]))
    assert _scores(out) == [0.63, 0.4869, 0.2234]


def test_cau_rong_giu_het():
    # Q "Điều kiện môi trường": tất cả 0.96–0.99 → giữ cả 5
    scores = [0.9962, 0.9952, 0.9853, 0.9844, 0.964]
    out = filter_by_confidence(_mk(scores))
    assert _scores(out) == [round(s, 4) for s in scores]


def test_giu_nguyen_trat_tu_va_payload():
    out = filter_by_confidence(_mk([0.9, 0.5, 0.3]))
    assert [r["payload"]["file_stem"] for r in out] == ["f0", "f1", "f2"]


def test_nguong_hop_le():
    assert 0.0 < SOURCE_ABS_FLOOR < 1.0
    assert 0.0 < SOURCE_REL_FLOOR < 1.0
