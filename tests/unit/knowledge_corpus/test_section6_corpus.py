"""T6: kiểm tra trích xuất §6 bằng LLM (``knowledge.llm_extract``), client kịch bản.

Dùng lại ``eval.extract_section6_eval.build_scripted_payload``/``ScriptedClient``
(không tái cài đặt logic chấm điểm). Client kịch bản chèn hai dòng bịa số theo
mặc định — hàng rào xác minh (``knowledge.llm_extract.verify_fact``) phải loại
cả hai, chứng minh hàng rào hoạt động chứ không phải gold "vừa khít tình cờ".
"""

from __future__ import annotations

import json
from collections import defaultdict

import pytest

from eval.extract_section6_eval import ScriptedClient, build_scripted_payload, golden_key
from knowledge import llm_extract
from tests.unit.knowledge_corpus.conftest import CORPUS_ROOT, load_manifest

_MANIFEST = load_manifest()
_GOLD_FILE = CORPUS_ROOT / "gold" / "extract_golden_section6.jsonl"

# Bốn QTKĐ có hai mức sai số (R4: vùng lưu lượng/tải/tốc độ) — phải cho đúng hai
# dữ kiện §6, không phải một.
_TWO_LEVEL_DOCS = {"A04", "A06", "A08", "A10"}


def _clean_stem(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem.replace(" ", "_")


def _load_gold() -> list[dict]:
    rows = []
    with open(_GOLD_FILE, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


_STEM_TO_ID = {
    _clean_stem(obj["file"]): mid for mid, obj in _MANIFEST.items() if obj["group"] == "A"
}

_GOLD_BY_ID: dict[str, list[dict]] = defaultdict(list)
for _row in _load_gold():
    _mid = _STEM_TO_ID.get(_row["doc"])
    if _mid:
        _GOLD_BY_ID[_mid].append(_row)


@pytest.mark.parametrize("manifest_id", sorted(_GOLD_BY_ID))
def test_section6_group_a_matches_gold(manifest_id, corpus_markdown):
    """Nhóm A: dữ kiện §6 đã xác minh khớp gold theo quote chuẩn hóa; 0 bịa số."""
    gold_items = _GOLD_BY_ID[manifest_id]
    assert gold_items, f"{manifest_id}: gold §6 rỗng — lỗi cấu hình test"
    if manifest_id in _TWO_LEVEL_DOCS:
        assert len(gold_items) == 2, f"{manifest_id}: kỳ vọng đúng 2 mức sai số"

    md_text = corpus_markdown[manifest_id]
    payload = build_scripted_payload(gold_items, inject_hallucinations=True)
    client = ScriptedClient(payload)
    result = llm_extract.extract_section6(md_text, client)

    hallucinations = llm_extract.numeric_hallucinations(result, md_text)
    assert hallucinations == 0, f"{manifest_id}: {hallucinations} con số bịa lọt qua"

    verified_keys = {
        golden_key(
            {
                "doc": manifest_id,
                "fact_kind": verified.fact.fact_kind,
                "quote": verified.fact.quote,
            }
        )
        for verified in result.facts
    }
    gold_keys = {golden_key({**item, "doc": manifest_id}) for item in gold_items}
    assert verified_keys == gold_keys, (
        f"{manifest_id}: thiếu {gold_keys - verified_keys}, thừa {verified_keys - gold_keys}"
    )


@pytest.mark.parametrize("manifest_id", sorted(_TWO_LEVEL_DOCS))
def test_section6_two_level_docs_have_two_facts(manifest_id, corpus_markdown):
    """9.004/9.006/9.008/9.010: chấp nhận đúng hai dữ kiện §6 (không phải một)."""
    gold_items = _GOLD_BY_ID[manifest_id]
    md_text = corpus_markdown[manifest_id]
    payload = build_scripted_payload(gold_items, inject_hallucinations=True)
    result = llm_extract.extract_section6(md_text, ScriptedClient(payload))
    assert len(result.facts) == 2


def test_section6_b06_localized_heading_found(corpus_markdown):
    """K13: B06 dùng hai style heading bản địa hoá (``TieuDeMuc1`` theo ``w:name``,
    ``MucCon2`` theo ``basedOn``) nên ``find_section6`` phải tìm thấy mục
    "Tiến hành kiểm định" và thân mục chứa dữ kiện §6."""
    md_text = corpus_markdown["B06"]
    found = llm_extract.find_section6(md_text)
    assert found is not None, "find_section6 trả None (K13 chưa sửa)"
    body, _offset, path = found
    assert "tiến hành" in path.lower()
    assert "không nhỏ hơn ± 0,15 bar" in body
