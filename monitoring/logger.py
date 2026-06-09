"""Structured JSON logger for RAG performance metrics.

Writes NDJSON to $LOG_DIR/rag_app.jsonl (default: ./logs/).
Uses only stdlib — works in any virtualenv.

Log record fields:
  @timestamp    ISO-8601 UTC
  service       "rag-qtkd"
  event         "query"
  level         "info" | "error"
  question      first 300 chars of user query
  model         Ollama model name
  top_k         candidates requested from retriever
  top_n         final results after reranking
  doc_count     actual results returned
  retrieval_ms  wall-clock time for retrieve() call
  llm_ms        wall-clock time for LLM streaming
  total_ms      end-to-end for one turn
  tokens        approximate LLM output tokens (delta chunk count)
  error         present only on failures
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

_LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
_LOG_FILE = _LOG_DIR / "rag_app.jsonl"


def _build_handler() -> logging.FileHandler | None:
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        h = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        return h
    except OSError:
        return None


_logger = logging.getLogger("rag.metrics")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False
_h = _build_handler()
if _h:
    _logger.addHandler(_h)


def _emit(record: dict[str, Any]) -> None:
    record.setdefault(
        "@timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    _logger.info(json.dumps(record, ensure_ascii=False))


def log_query(
    *,
    question: str,
    model: str,
    top_k: int,
    top_n: int,
    doc_count: int,
    retrieval_ms: float,
    llm_ms: float,
    total_ms: float,
    tokens: int = 0,
    error: str | None = None,
) -> None:
    """Emit one query->answer lifecycle record."""
    record: dict[str, Any] = {
        "service": "rag-qtkd",
        "event": "query",
        "level": "error" if error else "info",
        "question": question[:300],
        "model": model,
        "top_k": top_k,
        "top_n": top_n,
        "doc_count": doc_count,
        "retrieval_ms": round(retrieval_ms, 1),
        "llm_ms": round(llm_ms, 1),
        "total_ms": round(total_ms, 1),
        "tokens": tokens,
    }
    if error:
        record["error"] = error
    _emit(record)


@contextmanager
def timed() -> Generator[dict[str, float], None, None]:
    """Measure elapsed wall-clock time in milliseconds.

    Usage::
        with timed() as t:
            do_something()
        print(t["ms"])   # elapsed ms
    """
    rec: dict[str, float] = {"ms": 0.0}
    start = time.perf_counter()
    try:
        yield rec
    finally:
        rec["ms"] = (time.perf_counter() - start) * 1000.0
