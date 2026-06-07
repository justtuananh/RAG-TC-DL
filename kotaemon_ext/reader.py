"""QTKDDocxReader — kotaemon reader adapter for QTKĐ .docx files.

Wraps ingestion.spike_a (formula extraction: MathType OLE → MTEF → LaTeX) and
index.chunker (parent-document chunking) so that every child chunk, including
formula blocks with $LaTeX$, is returned as a kotaemon Document.

Registered in flowsettings.py via:
    FILE_INDEX_PIPELINE_FILE_EXTRACTORS = {".docx": "kotaemon_ext.reader.QTKDDocxReader"}
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from kotaemon.base import Document
from kotaemon.loaders.base import BaseReader


class QTKDDocxReader(BaseReader):
    """Extract .docx → Markdown (with $LaTeX$ formulas) → child Chunks → Documents."""

    def load_data(
        self,
        file: Path,
        extra_info: Optional[dict] = None,
        **kwargs,
    ) -> List[Document]:
        # Lazy imports so the reader only requires these when actually called
        from ingestion.spike_a import _safe, run as spike_run
        from index.chunker import parse_file

        file = Path(file)
        extra_info = extra_info or {}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_dir = tmp_path / "src"
            out_dir = tmp_path / "out"
            src_dir.mkdir()
            out_dir.mkdir()

            # Copy the uploaded .docx into the temp source dir
            shutil.copy2(file, src_dir / file.name)

            # Stage 1: extract structure + MathType OLE formulas → Markdown
            spike_run(str(src_dir), str(out_dir))

            md_path = out_dir / f"{_safe(file.stem)}.md"
            if not md_path.exists():
                # Extraction produced nothing (e.g. legacy .doc skipped)
                return []

            # Stage 2: parse Markdown → parent + child Chunks
            chunks = parse_file(md_path)

        documents: List[Document] = []
        for chunk in chunks:
            if chunk.is_parent:
                # Skip parents; children are the search units
                continue
            metadata = {
                **extra_info,
                "file_name": file.name,
                "section_path": chunk.section_path,
                "kind": chunk.kind,
                "chunk_id": chunk.chunk_id,
            }
            documents.append(Document(text=chunk.text, metadata=metadata))

        return documents

    def run(self, file: Path, **kwargs) -> List[Document]:
        return self.load_data(file=file, **kwargs)
