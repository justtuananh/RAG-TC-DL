"""Cổng eval trích xuất: precision/recall trên tập vàng corpus hiện có."""

from __future__ import annotations

from eval.extract_eval import (
    CATEGORIES,
    DEFAULT_GOLDEN,
    DEFAULT_MD_DIR,
    evaluate,
    gate,
    golden_key,
    load_golden,
)


def test_golden_file_and_corpus_present():
    assert DEFAULT_GOLDEN.exists()
    assert DEFAULT_MD_DIR.is_dir()
    golden = load_golden(DEFAULT_GOLDEN)
    assert len(golden) > 100


def test_eval_passes_sprint_gate():
    report = evaluate()
    ok, failures = gate(report, 0.95, 0.80)
    assert ok, failures


def test_every_category_meets_thresholds():
    report = evaluate()
    for category in CATEGORIES:
        metrics = report["categories"][category]
        assert metrics["golden"] > 0, category
        assert metrics["precision"] >= 0.95, category
        assert metrics["recall"] >= 0.80, category


def test_golden_documents_exist_in_corpus():
    docs = {item["doc"] for item in load_golden(DEFAULT_GOLDEN)}
    for doc in docs:
        assert (DEFAULT_MD_DIR / f"{doc}.md").exists(), doc


def test_gate_flags_low_precision():
    report = {
        "categories": {
            "working_range": {
                "golden": 10,
                "precision": 0.5,
                "recall": 1.0,
            }
        }
    }
    ok, failures = gate(report, 0.95, 0.80)
    assert not ok
    assert any("precision" in failure for failure in failures)


def test_golden_key_is_document_scoped():
    item = {"kind": "fact", "fact_kind": "working_range", "value_text": "đến 1 400 bar"}
    assert golden_key("A", item) != golden_key("B", item)
