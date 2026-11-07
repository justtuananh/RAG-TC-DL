"""Chạy hàng loạt câu hỏi trong file Excel qua pipeline chat, ghi câu trả lời vào cột bên cạnh.

Mỗi câu hỏi đi qua đúng `chat_stream_events` mà `/api/chat/stream` dùng (qua `scripts/ask.py`),
mỗi câu độc lập (không nhớ hội thoại). Câu hỏi ở cột A (mặc định), câu trả lời ghi vào cột B
của CHÍNH file đó. Lưu file sau mỗi câu, nên ngắt giữa chừng rồi chạy lại sẽ làm tiếp
(bỏ qua dòng đã có câu trả lời); dòng bị lỗi để trống để lần sau thử lại.

Chạy (trên host, cần Docker stack đang chạy):
    python scripts/ask_excel.py 500_cau_hoi_tai_lieu.xlsx
    python scripts/ask_excel.py file.xlsx --limit 5            # thử 5 câu đầu
    python scripts/ask_excel.py file.xlsx --column A --answer-column C --sheet "Sheet1"
    python scripts/ask_excel.py file.xlsx --redo               # hỏi lại cả những dòng đã có đáp án
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import column_index_from_string

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.startup import startup  # noqa: E402
from scripts.ask import ask  # noqa: E402

ANSWER_COLUMN_WIDTH = 100


def _pending_rows(ws, question_col: int, answer_col: int, redo: bool) -> list[int]:
    rows = []
    for row in range(1, ws.max_row + 1):
        question = ws.cell(row, question_col).value
        if not isinstance(question, str) or not question.strip():
            continue
        if not redo and ws.cell(row, answer_col).value:
            continue
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy câu hỏi trong Excel qua chatbot QTKĐ")
    parser.add_argument("xlsx", type=Path, help="File Excel; câu trả lời được ghi vào chính file này.")
    parser.add_argument("--sheet", help="Tên sheet (mặc định: sheet đầu tiên).")
    parser.add_argument("--column", default="A", help="Cột chứa câu hỏi (mặc định A).")
    parser.add_argument("--answer-column", default="B", help="Cột ghi câu trả lời (mặc định B).")
    parser.add_argument("--limit", type=int, help="Chỉ chạy N câu chưa có đáp án đầu tiên.")
    parser.add_argument("--redo", action="store_true", help="Hỏi lại cả dòng đã có đáp án.")
    args = parser.parse_args()

    question_col = column_index_from_string(args.column.upper())
    answer_col = column_index_from_string(args.answer_column.upper())
    if question_col == answer_col:
        parser.error("--column và --answer-column phải khác nhau")

    wb = load_workbook(args.xlsx)
    ws = wb[args.sheet] if args.sheet else wb.worksheets[0]
    rows = _pending_rows(ws, question_col, answer_col, args.redo)
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("Không có câu hỏi nào cần chạy.", file=sys.stderr)
        return 0

    ws.column_dimensions[args.answer_column.upper()].width = ANSWER_COLUMN_WIDTH
    startup()

    failed = 0
    for i, row in enumerate(rows, 1):
        question = ws.cell(row, question_col).value.strip()
        run = ask(question, [])
        if run.error or not run.answer.strip():
            failed += 1
            print(f"[{i}/{len(rows)}] dòng {row} LỖI: {run.error or 'trả lời rỗng'}", file=sys.stderr)
            continue
        cell = ws.cell(row, answer_col, run.answer)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        wb.save(args.xlsx)
        print(f"[{i}/{len(rows)}] dòng {row} ok ({run.total_s:.1f}s)", file=sys.stderr)

    print(f"Xong: {len(rows) - failed}/{len(rows)} câu, {failed} lỗi.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
