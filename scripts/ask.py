"""Hỏi đáp trên terminal + đo hiệu năng từng bước, không cần giao diện.

Gọi đúng `api.services.chat_stream.chat_stream_events` mà `/api/chat/stream` dùng,
nên số đo là của pipeline production (không có bản sao để lệch).

Chạy (trên host, cần Docker stack đang chạy):
    python scripts/ask.py "phạm vi van an toàn 1400 bar"       # 1 câu
    python scripts/ask.py -n 3 "câu hỏi"                       # lặp 3 lần (lần 1 là cold)
    python scripts/ask.py -f questions.txt --no-answer         # lô câu hỏi, chỉ in số đo
    python scripts/ask.py                                      # vòng lặp tương tác, có nhớ hội thoại

Số đo mỗi câu: retrieve (tới khi có nguồn), TTFT (tới token đầu), sinh, tổng, token/s.
Một "token" ở đây là một delta SSE của Ollama (xấp xỉ 1 token).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.schemas import ChatMessage, ChatRequest  # noqa: E402
from api.services.chat_stream import chat_stream_events  # noqa: E402
from core.startup import startup  # noqa: E402
from db import SessionLocal  # noqa: E402


@dataclass
class Run:
    question: str
    answer: str
    sources: list[dict]
    retrieve_s: float | None
    ttft_s: float | None
    total_s: float
    deltas: int
    error: str | None

    @property
    def gen_s(self) -> float | None:
        if self.ttft_s is None:
            return None
        return self.total_s - self.ttft_s

    @property
    def tokens_per_s(self) -> float | None:
        gen = self.gen_s
        if not gen or self.deltas < 2:
            return None
        return (self.deltas - 1) / gen


def ask(question: str, history: list[ChatMessage], *, stream_to=None) -> Run:
    """Chạy một câu hỏi qua pipeline, đo mốc thời gian theo từng loại sự kiện SSE."""
    db = SessionLocal()
    start = time.perf_counter()
    retrieve_s = ttft_s = None
    deltas = 0
    answer = ""
    sources: list[dict] = []
    error = None
    try:
        for raw in chat_stream_events(ChatRequest(message=question, history=history), db):
            now = time.perf_counter() - start
            event = json.loads(raw.removeprefix("data: ").strip())
            kind = event["type"]
            if kind == "sources":
                retrieve_s = now
                sources = event["sources"]
            elif kind == "delta":
                if ttft_s is None:
                    ttft_s = now
                deltas += 1
                if stream_to:
                    stream_to.write(event["text"])
                    stream_to.flush()
            elif kind == "done":
                answer = event["answer"]
                sources = event["sources"] or sources
            elif kind == "error":
                error = event["text"]
    finally:
        db.close()
    return Run(
        question, answer, sources, retrieve_s, ttft_s, time.perf_counter() - start, deltas, error
    )


def _fmt(value: float | None, unit: str = "s") -> str:
    return "-" if value is None else f"{value:.2f}{unit}"


def print_metrics(run: Run) -> None:
    print(
        f"\n[retrieve {_fmt(run.retrieve_s)} | TTFT {_fmt(run.ttft_s)} | sinh {_fmt(run.gen_s)}"
        f" | tổng {_fmt(run.total_s)} | {run.deltas} token | {_fmt(run.tokens_per_s, ' tok/s')}]",
        file=sys.stderr,
    )
    if run.error:
        print(f"LỖI: {run.error}", file=sys.stderr)


def print_sources(run: Run) -> None:
    for s in run.sources:
        print(f"  [{s['index']}] {s['file_stem']} - {s['section_path']} ({s['rerank_score']})")


def print_summary(runs: list[Run]) -> None:
    ok = [r for r in runs if not r.error]
    print(f"\n=== Tổng kết {len(ok)}/{len(runs)} câu thành công ===", file=sys.stderr)
    for label, getter in (
        ("retrieve", lambda r: r.retrieve_s),
        ("TTFT", lambda r: r.ttft_s),
        ("tổng", lambda r: r.total_s),
        ("tok/s", lambda r: r.tokens_per_s),
    ):
        values = sorted(v for r in ok if (v := getter(r)) is not None)
        if not values:
            continue
        p95 = values[min(len(values) - 1, round(0.95 * (len(values) - 1)))]
        print(
            f"{label:>9}: min {values[0]:.2f}  median {statistics.median(values):.2f}"
            f"  p95 {p95:.2f}  max {values[-1]:.2f}",
            file=sys.stderr,
        )


def run_batch(questions: list[str], args: argparse.Namespace) -> list[Run]:
    runs: list[Run] = []
    for question in questions:
        for i in range(args.repeat):
            print(f"\n>>> {question}" + (f"  (lần {i + 1}/{args.repeat})" if args.repeat > 1 else ""))
            run = ask(question, [], stream_to=None if args.no_answer else sys.stdout)
            if not args.no_answer and not run.deltas:
                print(run.answer)  # trả lời cố định (tính toán / không tìm thấy), không stream
            print_metrics(run)
            if args.sources:
                print_sources(run)
            runs.append(run)
    if len(runs) > 1:
        print_summary(runs)
    return runs


def repl(args: argparse.Namespace) -> None:
    history: list[ChatMessage] = []
    print("Gõ câu hỏi (Ctrl-D hoặc 'exit' để thoát, '/reset' xoá hội thoại).", file=sys.stderr)
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            return
        if question in ("exit", "quit"):
            return
        if question == "/reset":
            history = []
            continue
        if not question:
            continue
        run = ask(question, history, stream_to=sys.stdout)
        if not run.deltas:
            print(run.answer)
        print_metrics(run)
        if args.sources:
            print_sources(run)
        if not run.error:
            history += [
                ChatMessage(role="user", content=question),
                ChatMessage(role="assistant", content=run.answer),
            ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Hỏi đáp QTKĐ trên terminal + đo hiệu năng")
    parser.add_argument("question", nargs="*", help="Câu hỏi; bỏ trống để vào chế độ tương tác.")
    parser.add_argument("-f", "--file", help="Tệp câu hỏi, mỗi dòng một câu.")
    parser.add_argument("-n", "--repeat", type=int, default=1, help="Lặp mỗi câu N lần.")
    parser.add_argument("--no-answer", action="store_true", help="Không in câu trả lời, chỉ số đo.")
    parser.add_argument("--sources", action="store_true", help="In danh sách nguồn.")
    args = parser.parse_args()

    startup()
    questions = list(args.question)
    if args.file:
        lines = Path(args.file).read_text(encoding="utf-8").splitlines()
        questions += [ln.strip() for ln in lines if ln.strip()]
    if not questions:
        repl(args)
        return 0
    runs = run_batch(questions, args)
    return 1 if any(r.error for r in runs) else 0


if __name__ == "__main__":
    sys.exit(main())
