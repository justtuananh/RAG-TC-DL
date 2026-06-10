"""Chờ các service Docker sẵn sàng (wait-for-services) với exponential backoff.

Lấp khoảng trống mà code đang thiếu: retriever/embed_store gọi `requests.post` trần
không retry. Script này (chỉ thư viện chuẩn) poll /health của 4 service và backoff
1→2→4→…→8s cho tới khi đủ hoặc hết --timeout.

Chạy:
    python scripts/healthcheck.py [--timeout 120] [--require qdrant,embedding]

Honor env override: EMBED_URL / RERANK_URL / QDRANT_URL / OLLAMA_URL.
Exit 0 nếu mọi service yêu cầu sẵn sàng; exit 1 nếu không.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

SERVICES = ("embedding", "reranker", "qdrant", "ollama")


def _base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def health_urls() -> dict[str, str]:
    """URL liveness cho từng service (suy ra từ env URL của code, có default)."""
    return {
        "embedding": _base(os.getenv("EMBED_URL", "http://localhost:8010/v1/embeddings"))
        + "/health",
        "reranker": _base(os.getenv("RERANK_URL", "http://localhost:8011/v1/rerank")) + "/health",
        # Qdrant trả 200 ở root "/" (kèm version) — liveness đơn giản, ổn định.
        "qdrant": _base(os.getenv("QDRANT_URL", "http://localhost:6333")),
        "ollama": _base(os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions"))
        + "/api/tags",
    }


def ping(url: str, timeout: float = 1.0) -> bool:
    """True nếu GET url trả mã < 500 (service sống), False nếu không kết nối được."""
    try:
        with urlopen(url, timeout=timeout) as r:  # noqa: S310 (localhost, có chủ đích)
            return getattr(r, "status", 200) < 500
    except URLError:
        return False
    except (OSError, ValueError):
        return False


def wait_for(names: list[str], timeout: float = 120.0, verbose: bool = True) -> dict[str, bool]:
    urls = health_urls()
    status: dict[str, bool] = {}
    for name in names:
        url = urls[name]
        start = time.monotonic()
        delay = 1.0
        ok = ping(url)
        while not ok:
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0:
                break
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, 8.0)
            ok = ping(url)
        status[name] = ok
        if verbose:
            mark = "✓" if ok else "✗"
            tail = "sẵn sàng" if ok else f"KHÔNG phản hồi ({url})"
            print(f"  {mark} {name}: {tail}")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chờ service Docker sẵn sàng")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Tổng thời gian chờ mỗi service (giây)"
    )
    parser.add_argument(
        "--require",
        default=",".join(SERVICES),
        help="Danh sách service cần (vd: qdrant,embedding). Mặc định cả 4.",
    )
    args = parser.parse_args(argv)

    names = [s.strip() for s in args.require.split(",") if s.strip()]
    unknown = [n for n in names if n not in SERVICES]
    if unknown:
        print(
            f"Service không hợp lệ: {', '.join(unknown)}. Hợp lệ: {', '.join(SERVICES)}",
            file=sys.stderr,
        )
        return 2

    print(f"Chờ service (timeout {args.timeout:.0f}s): {', '.join(names)}")
    status = wait_for(names, timeout=args.timeout)
    if all(status.values()):
        print("✅ Tất cả service yêu cầu đã sẵn sàng.")
        return 0
    down = [n for n, ok in status.items() if not ok]
    print(
        f"❌ Service chưa sẵn sàng: {', '.join(down)}. Chạy `make up` rồi thử lại.", file=sys.stderr
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
