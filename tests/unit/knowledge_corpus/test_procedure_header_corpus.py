"""T4: kiểm tra trích xuất đầu mục QTKĐ (``knowledge.procedure.parse_procedure_header``)."""

from __future__ import annotations

import pytest

from knowledge.procedure import parse_procedure_header
from tests.unit.knowledge_corpus.conftest import load_manifest

_MANIFEST = load_manifest()


def _abf_ids() -> list[str]:
    return sorted(mid for mid, obj in _MANIFEST.items() if obj["group"] in ("A", "B", "F"))


def _params():
    return [pytest.param(manifest_id, id=manifest_id) for manifest_id in _abf_ids()]


@pytest.mark.parametrize("manifest_id", _params())
def test_procedure_header_matches_manifest(manifest_id, corpus_markdown):
    """Với mọi file nhóm A/B/F: ``number`` khớp ``procedure_number`` và tiêu đề
    không rỗng."""
    assert manifest_id in corpus_markdown, f"{manifest_id}: chưa có Markdown (spike_a lỗi?)"
    md_text = corpus_markdown[manifest_id]
    expected_number = _MANIFEST[manifest_id]["procedure_number"]

    header = parse_procedure_header(md_text)
    assert header is not None, f"{manifest_id}: không tìm thấy header QTKĐ"
    assert header.number == expected_number
    assert header.title and header.title.strip()
