"""Cổng eval §6: tập vàng, precision ≥ 0,90, và 0 bịa số lọt qua (spec §9 S5)."""

from __future__ import annotations

from eval.extract_section6_eval import (
    DEFAULT_GOLDEN,
    DEFAULT_MD_DIR,
    ScriptedClient,
    build_scripted_payload,
    evaluate,
    gate,
    golden_key,
    load_golden,
)


def test_golden_file_and_corpus_present():
    assert DEFAULT_GOLDEN.exists()
    assert DEFAULT_MD_DIR.is_dir()
    golden = load_golden(DEFAULT_GOLDEN)
    assert len(golden) >= 10


def test_golden_documents_exist_in_corpus():
    docs = {item["doc"] for item in load_golden(DEFAULT_GOLDEN)}
    for doc in docs:
        assert (DEFAULT_MD_DIR / f"{doc}.md").exists(), doc


def test_eval_passes_sprint5_gate():
    report = evaluate()
    ok, failures = gate(report, 0.90)
    assert ok, failures


def test_every_section6_category_meets_threshold():
    report = evaluate()
    for metrics in report["categories"].values():
        assert metrics["golden"] > 0
        assert metrics["precision"] >= 0.90


def test_zero_numeric_hallucination_on_check_set():
    report = evaluate()
    assert report["numeric_hallucinations"] == 0
    assert report["unverified_accepted"] == 0


def test_scripted_payload_injects_hallucinations_that_are_rejected():
    golden = load_golden(DEFAULT_GOLDEN)
    items = [item for item in golden if item["doc"] == golden[0]["doc"]]
    payload = build_scripted_payload(items)
    assert len(payload["facts"]) == len(items) + 2  # 2 dòng bịa chèn thêm

    report = evaluate(client_factory=lambda doc, its: ScriptedClient(build_scripted_payload(its)))
    # Bịa bị loại nên precision vẫn đạt và không con số nào lọt.
    assert report["numeric_hallucinations"] == 0
    assert report["micro_precision"] == 1.0


def test_gate_flags_low_precision_and_hallucination():
    report = {
        "categories": {
            "max_permissible_error": {"golden": 10, "precision": 0.5},
        },
        "numeric_hallucinations": 1,
        "unverified_accepted": 0,
    }
    ok, failures = gate(report, 0.90)
    assert not ok
    assert any("precision" in failure for failure in failures)
    assert any("bịa số" in failure for failure in failures)


def test_golden_key_is_document_scoped():
    item = {
        "doc": "A",
        "fact_kind": "max_permissible_error",
        "quote": "± 3%",
    }
    other = dict(item, doc="B")
    assert golden_key(item) != golden_key(other)
