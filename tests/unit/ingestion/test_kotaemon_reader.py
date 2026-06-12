"""Mode B adapter — kotaemon_ext.reader.QTKDDocxReader (ƯU TIÊN THẤP).

kotaemon nằm NGOÀI phạm vi harness (repo anh em), nên test này tự SKIP khi không có
package kotaemon. Khi có, kiểm: chỉ child→Document, parent bị bỏ, metadata đầy đủ.
"""

import pytest

pytest.importorskip("kotaemon.base")  # noqa: E402

from pathlib import Path  # noqa: E402

from index.chunker import Chunk  # noqa: E402
from kotaemon_ext.reader import QTKDDocxReader  # noqa: E402


def test_maps_children_to_documents_drops_parents(monkeypatch, tmp_path):
    fake_chunks = [
        Chunk(
            chunk_id="p",
            parent_id=None,
            is_parent=True,
            kind="section",
            text="parent",
            section_path="6",
            file_stem="QTKD_1.061",
        ),
        Chunk(
            chunk_id="c1",
            parent_id="p",
            is_parent=False,
            kind="paragraph",
            text="child text",
            section_path="6 > 6.1",
            file_stem="QTKD_1.061",
        ),
    ]

    def fake_spike_run(src, out):
        from ingestion.spike_a import _safe

        (Path(out) / f"{_safe('doc')}.md").write_text("# x", encoding="utf-8")
        return {}

    monkeypatch.setattr("ingestion.spike_a.run", fake_spike_run)
    monkeypatch.setattr("index.chunker.parse_file", lambda p: fake_chunks)

    docx = tmp_path / "doc.docx"
    docx.write_bytes(b"PK")

    docs = QTKDDocxReader().load_data(docx)

    assert len(docs) == 1  # parent bị bỏ, chỉ còn 1 child
    assert docs[0].text == "child text"
    assert docs[0].metadata["section_path"] == "6 > 6.1"
    assert docs[0].metadata["kind"] == "paragraph"
    assert docs[0].metadata["file_name"] == "doc.docx"
