"""Nhúng chunk theo lô cho bước index; lô lỗi HTTP 500 thì thử lại từng chunk."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence

import requests

from core.schema import Chunk
from core.settings_loader import get_settings
from embedding import embedder

logger = logging.getLogger(__name__)


# Richer contextual blurb: QTKĐ number + equipment name (Phase 2 Contextual Retrieval).
# Extracted from §1 "Phạm vi áp dụng" of each source document.
_QTKD_TITLES: dict[str, str] = {
    "QTKD_1.061": "Van an toàn",
    "QTKD_1.062": "Bàn tạo áp",
    "QTKD_1.063": "Bình phân ly",
    "QTKD_1.071": "Áp kế pittông H3000",
    "QTKD_1.159": "Áp kế pittông tiêu chuẩn",
    "QTKD_1.160": "Thiết bị đo áp suất số AKKĐ",
    "QTKD_1.190": "DPI 610",
}


_QTKD_NUMBER_RE = re.compile(r'QTKD_(\d+\.\d+)')


def _qtkd_prefix(file_stem: str) -> str:
    """Return 'QTKĐ X.XXX TênThiếtBị: ' from any file_stem containing QTKD_X.XXX."""
    m = _QTKD_NUMBER_RE.search(file_stem)
    if m:
        number = m.group(1)
        title = _QTKD_TITLES.get(f"QTKD_{number}", "")
        suffix = f" {title}" if title else ""
        return f"QTKĐ {number}{suffix}: "
    return ""


def embed_chunks_batched(chunks: Sequence[Chunk]) -> list[list[float]]:
    """Embed chunks in batches; child chunks get QTKĐ-number context prefix (Phase 2).

    Only the embedding input changes — payload text stays original so BM25
    and the UI still use the clean source text.
    """
    settings = get_settings().embedding
    vector_size = get_settings().models.embedding.vector_size
    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks), settings.batch_size):
        batch = chunks[i: i + settings.batch_size]
        texts = [
            # Phase 2 prefix DISABLED (A/B test 2026-06-07): recall@5 identical (0.709) with/without;
            # prefix gives +1.8pp recall@10 (0.836 vs 0.818). To restore: re-enable line below + --force.
            # (_qtkd_prefix(c.file_stem) + c.text) if not c.is_parent else c.text
            c.text
            for c in batch
        ]
        try:
            vecs = embedder.embed_texts(texts)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 500:
                # GPU OOM or transient service error — retry one chunk at a time
                logger.warning("batch %d HTTP 500, retrying 1-by-1 …", i // settings.batch_size)
                time.sleep(2)
                vecs = []
                for j, text in enumerate(texts):
                    try:
                        vecs.extend(embedder.embed_texts([text]))
                    except Exception as inner:
                        logger.warning("chunk %d failed solo (%s), using zero vector", i + j, inner)
                        vecs.append([0.0] * vector_size)
            else:
                raise
        all_vectors.extend(vecs)
        logger.info("embedded %d/%d", min(i + settings.batch_size, len(chunks)), len(chunks))
    return all_vectors
