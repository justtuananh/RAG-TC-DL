"""Tải model embedding/reranker vào HF_HOME trong lần cài đầu.

Chạy bằng Python của bản cài, sau khi đã pip install:

    python -m windows.models [--offline]

``--offline`` chỉ nạp lại từ cache đã chép sẵn; thiếu model thì báo lỗi rõ ràng
thay vì lặng lẽ gọi mạng (máy đích có thể không có Internet).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.settings_loader import get_settings  # noqa: E402


def download(offline: bool = False) -> None:
    from sentence_transformers import CrossEncoder, SentenceTransformer

    settings = get_settings()
    embedding = settings.models.embedding.name
    reranker = settings.models.reranker
    print(f"  embedding: {embedding}")
    SentenceTransformer(embedding)
    print(f"  reranker: {reranker.name} (max_length={reranker.max_length})")
    CrossEncoder(reranker.name, max_length=reranker.max_length)
    print("  model sẵn sàng" + (" (offline)" if offline else ""))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    download(offline="--offline" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
