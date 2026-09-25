"""T5: kiểm tra trích xuất dữ kiện theo luật (``knowledge.extract.run_rules``).

Nhóm A (12 QTKĐ sạch) là đường cơ sở: mỗi (tài liệu, fact_kind) phải khớp CHÍNH
XÁC tập khóa vàng — không chỉ đạt ngưỡng. Nhóm B (9 QTKĐ biên, mỗi file nhắm một
mã K) dùng lại đúng phép so khớp đó; cặp nào chạm mã K của tài liệu đó mang
``xfail(strict=True)``, các cặp còn lại PHẢI đạt để chứng minh lỗi chỉ cục bộ.
"""

from __future__ import annotations

import json
from collections import defaultdict

import pytest

from eval.extract_eval import golden_key, hit_key
from knowledge.extract import run_rules
from tests.unit.knowledge_corpus.conftest import CORPUS_ROOT, load_manifest, xfail_for

_MANIFEST = load_manifest()
_GOLD_FILE = CORPUS_ROOT / "gold" / "extract_golden.jsonl"


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
    _clean_stem(obj["file"]): mid for mid, obj in _MANIFEST.items() if obj["group"] in ("A", "B")
}

_GOLD_BY_ID: dict[str, list[dict]] = defaultdict(list)
for _row in _load_gold():
    _mid = _STEM_TO_ID.get(_row["doc"])
    if _mid:
        _GOLD_BY_ID[_mid].append(_row)


def _category(manifest_id: str, row: dict) -> str:
    return golden_key(manifest_id, row)[1]


def _doc_kind_pairs(group: str) -> list[tuple[str, str]]:
    pairs = []
    for manifest_id in sorted(_GOLD_BY_ID):
        if _MANIFEST[manifest_id]["group"] != group:
            continue
        kinds = sorted({_category(manifest_id, r) for r in _GOLD_BY_ID[manifest_id]})
        pairs.extend((manifest_id, kind) for kind in kinds)
    return pairs


def _predicted_keys(manifest_id: str, md_text: str, kind: str) -> set[tuple[str, str, str]]:
    hits = run_rules(md_text)
    return {hit_key(manifest_id, hit) for hit in hits if hit_key(manifest_id, hit)[1] == kind}


def _gold_keys(manifest_id: str, kind: str) -> set[tuple[str, str, str]]:
    rows = [row for row in _GOLD_BY_ID[manifest_id] if _category(manifest_id, row) == kind]
    return {golden_key(manifest_id, row) for row in rows}


# ── Nhóm A: khớp CHÍNH XÁC theo (tài liệu, fact_kind) ─────────────────────────

_GROUP_A_PAIRS = _doc_kind_pairs("A")


@pytest.mark.parametrize(
    "manifest_id,kind", _GROUP_A_PAIRS, ids=[f"{m}-{k}" for m, k in _GROUP_A_PAIRS]
)
def test_rules_group_a_exact_match(manifest_id, kind, corpus_markdown):
    """Nhóm A: tập khóa dự đoán bằng CHÍNH XÁC tập khóa vàng, theo từng fact_kind."""
    gold_keys = _gold_keys(manifest_id, kind)
    assert gold_keys, f"{manifest_id}/{kind}: gold rỗng — lỗi cấu hình test"

    md_text = corpus_markdown[manifest_id]
    pred_keys = _predicted_keys(manifest_id, md_text, kind)
    assert pred_keys == gold_keys, (
        f"{manifest_id}/{kind}: thiếu {gold_keys - pred_keys}, thừa {pred_keys - gold_keys}"
    )


def test_rules_group_a_aggregate_precision_recall(corpus_markdown):
    """Nhóm A gộp: precision >= 0,95 và recall >= 0,80 cho từng fact_kind (cổng spec)."""
    group_a_ids = [mid for mid in _GOLD_BY_ID if _MANIFEST[mid]["group"] == "A"]
    assert len(group_a_ids) == 12

    gold_keys: set[tuple[str, str, str]] = set()
    pred_keys: set[tuple[str, str, str]] = set()
    for manifest_id in group_a_ids:
        for row in _GOLD_BY_ID[manifest_id]:
            gold_keys.add(golden_key(manifest_id, row))
        for hit in run_rules(corpus_markdown[manifest_id]):
            pred_keys.add(hit_key(manifest_id, hit))

    categories = sorted({key[1] for key in gold_keys})
    assert categories == [
        "calibration_interval",
        "env_condition",
        "inspection_step",
        "standard",
        "term",
        "working_range",
    ]
    for category in categories:
        gold = {k for k in gold_keys if k[1] == category}
        pred = {k for k in pred_keys if k[1] == category}
        precision = len(gold & pred) / len(pred) if pred else 0.0
        recall = len(gold & pred) / len(gold) if gold else 1.0
        assert precision >= 0.95, f"{category}: precision {precision:.3f} < 0.95"
        assert recall >= 0.80, f"{category}: recall {recall:.3f} < 0.80"


# ── Nhóm B: mỗi file nhắm một mã K; cặp không chạm mã K phải đạt bình thường ──

# (manifest_id, fact_kind bị ảnh hưởng) -> mã K. Sau Đợt 1 (2026-09-25) cả ba mã
# ảnh hưởng trích xuất luật của nhóm B (K15/K10/K02) đã sửa nên bảng rỗng;
# giữ cơ chế tra mã để tái sử dụng nếu có ca biên mới. K12/K13 chạm phụ lục A/§6,
# không nằm trong ``extract_all``.
_GROUP_B_XFAIL: dict[tuple[str, str], str] = {}

_GROUP_B_PAIRS = _doc_kind_pairs("B")


def _group_b_params():
    params = []
    for manifest_id, kind in _GROUP_B_PAIRS:
        code = _GROUP_B_XFAIL.get((manifest_id, kind))
        marks = [xfail_for(_MANIFEST, code, manifest_id=manifest_id)] if code else []
        params.append(pytest.param(manifest_id, kind, marks=marks, id=f"{manifest_id}-{kind}"))
    return params


@pytest.mark.parametrize("manifest_id,kind", _group_b_params())
def test_rules_group_b_matches_or_xfails(manifest_id, kind, corpus_markdown):
    """Nhóm B: so với gold theo (tài liệu, fact_kind); cặp chạm mã K của chính
    tài liệu đó mang xfail strict, các cặp còn lại phải đạt (chứng minh lỗi cục bộ).

    B07 (Bảng 2 tách "Bảng 2 (kết thúc)"): số chuẩn đo lường bằng tổng hai bảng —
    không có mã K, phải khớp gold bình thường (gold đã tính gộp cả hai bảng).
    B08 (số kiểu Việt hợp lệ "0,500"/"1 000"): cũng không có mã K, phải khớp
    ``value_text`` và giá trị số đúng như gold.
    """
    gold_keys = _gold_keys(manifest_id, kind)
    assert gold_keys, f"{manifest_id}/{kind}: gold rỗng — lỗi cấu hình test"

    md_text = corpus_markdown[manifest_id]
    pred_keys = _predicted_keys(manifest_id, md_text, kind)
    assert pred_keys == gold_keys, (
        f"{manifest_id}/{kind}: thiếu {gold_keys - pred_keys}, thừa {pred_keys - gold_keys}"
    )
