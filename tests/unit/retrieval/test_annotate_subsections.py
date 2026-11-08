"""retriever.annotate_subsections gắn cited_section_path, không đổi payload."""

from retrieval import retriever


def _hit():
    return {
        "payload": {"section_path": "6 A > 6.3 B", "text": "nội dung hai", "file_stem": "f"},
        "parent_payload": {"text": "## 6.3 B\n\n6.3.1 Một\n\nnội dung một\n\n6.3.2 Hai\n\nnội dung hai\n"},
        "anchor_texts": ["nội dung hai"],
    }


def test_annotate_adds_cited_path_only(monkeypatch):
    hits = [_hit()]
    retriever.annotate_subsections(hits)
    assert hits[0]["cited_section_path"] == "6 A > 6.3 B > 6.3.2 Hai"
    assert hits[0]["payload"]["section_path"] == "6 A > 6.3 B"


def test_annotate_disabled_by_config(settings_override):
    settings_override({"retrieval.locate_subsection": False})
    hits = [_hit()]
    retriever.annotate_subsections(hits)
    assert "cited_section_path" not in hits[0]
