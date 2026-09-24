"""Cổng eval chat lai văn bản + số liệu (spec §8, §9 Sprint 9).

Mục tiêu cổng:

- độ chính xác chọn intent (nhánh + intent) ≥ 0,90;
- mọi tham số sai schema đều rơi về nhánh ``text`` (không có text-to-SQL tự do);
- không có ô số nào trong nhánh số liệu thiếu tham chiếu xuất xứ (P1);
- câu hỏi văn bản không bị định tuyến nhầm sang nhánh số liệu (không hồi quy RAG).

Vì CI không có GPU/Ollama, eval chạy một **bộ phân loại kịch bản** dựng từ tập
vàng (``ScriptedClassifier``), có chủ đích chèn các tham số sai để chứng minh cơ
chế rơi về text. Độ chính xác của model thật đo bằng ``--live`` khi có Ollama.

Usage:
  python -m eval.intent_eval [--golden PATH] [--live] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    CalibrationRecord,
    Device,
    DeviceType,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    MeasurementPoint,
    Procedure,
    ProcedureFact,
    ProcedureStandard,
    Quantity,
    Unit,
)
from db.views import create_all_approved_views
from query import intents, router

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "eval" / "intent_golden.jsonl"


class ScriptedClassifier:
    """Bộ phân loại tất định: trả payload dựng sẵn cho mỗi câu hỏi."""

    def __init__(self, payload):
        self.payload = payload

    def classify(self, question: str):
        return self.payload


def load_golden(path: Path = DEFAULT_GOLDEN) -> list[dict]:
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _raw_for(entry: dict) -> dict:
    """Payload mà bộ phân loại kịch bản trả về cho một dòng vàng."""
    raw = {"branch": entry.get("branch", "text")}
    if entry.get("intent"):
        raw["intent"] = entry["intent"]
    if entry.get("params") is not None:
        raw["params"] = entry["params"]
    raw["confidence"] = entry.get("confidence", 0.95)
    return raw


def expected_branch(entry: dict) -> str:
    """Nhánh mong đợi: ``expect_branch`` khi có (dòng tham số sai), mặc định branch."""
    return entry.get("expect_branch", entry.get("branch", "text"))


# ── CSDL SQLite nhỏ để kiểm "mọi ô số truy được nguồn" (P1) ────────────────────


def build_session():
    """Dựng CSDL in-memory đã có view đã duyệt + dữ liệu nhỏ để chạy resolver."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

    quantity = Quantity(code="pressure", name_vi="Áp suất", si_unit_code="Pa")
    session.add(quantity)
    session.flush()
    unit_bar = Unit(code="bar", name_vi="Bar", quantity_id=quantity.id, factor_to_si=100000.0)
    unit_pa = Unit(code="Pa", name_vi="Pascal", quantity_id=quantity.id, factor_to_si=1.0)
    device_type = DeviceType(name_vi="Van an toàn", quantity_id=quantity.id)
    session.add_all([unit_bar, unit_pa, device_type])
    session.flush()

    session.add_all(
        [
            Document(
                id="QTKD_1.061",
                file_stem="QTKD_1.061",
                display_name="QTKD_1.061.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="0" * 64,
                size_bytes=1,
            ),
            Document(
                id="BB_2024_001",
                file_stem="BB_2024_001",
                display_name="BB_2024_001.docx",
                ext="DOCX",
                doc_type=DocumentType.HO_SO_KIEM_DINH,
                sha256="1" * 64,
                size_bytes=1,
            ),
        ]
    )
    session.flush()
    procedure = Procedure(
        number="1.061",
        year=2021,
        title="Van an toàn",
        document_id="QTKD_1.061",
        device_type_id=device_type.id,
    )
    session.add(procedure)
    session.flush()

    def extraction(section: str, chunk: str, quote: str, extractor: str) -> Extraction:
        return Extraction(
            document_id="QTKD_1.061",
            section_path=section,
            chunk_id=chunk,
            quote=quote,
            extractor=extractor,
            extractor_version="v1",
            confidence=0.95,
            status=ExtractionStatus.APPROVED,
        )

    range_extraction = extraction(
        "1 Phạm vi áp dụng", "chunk-range", "Phạm vi đo (0 ÷ 1600) bar", "rule:phamvi.v1"
    )
    accuracy_extraction = extraction(
        "6 Tiến hành", "chunk-accuracy", "Sai số cho phép ± 0,5 %", "rule:bang2.v1"
    )
    standard_extraction = extraction(
        "4 Phương tiện", "chunk-standard", "Áp kế chuẩn (0 ÷ 1600) bar", "rule:bang2.v1"
    )
    session.add_all([range_extraction, accuracy_extraction, standard_extraction])
    session.flush()
    session.add_all(
        [
            ProcedureFact(
                extraction_id=range_extraction.id,
                procedure_id=procedure.id,
                fact_kind="working_range",
                label="Phạm vi",
                value_min=0.0,
                value_max=160000000.0,
                unit_id=unit_pa.id,
                value_text="(0 ÷ 1600) bar",
            ),
            ProcedureFact(
                extraction_id=accuracy_extraction.id,
                procedure_id=procedure.id,
                fact_kind="accuracy_class",
                label="Cấp chính xác",
                value_text="± 0,5 %",
            ),
            ProcedureStandard(
                extraction_id=standard_extraction.id,
                procedure_id=procedure.id,
                ord=1,
                name_vi="Áp kế píttông tiêu chuẩn",
                range_text="(0 ÷ 1600) bar",
                accuracy_text="0,05 %",
            ),
        ]
    )
    device = Device(
        device_type_id=device_type.id, serial_no="SN-1", serial_norm="sn-1", model_code="VA-1"
    )
    session.add(device)
    session.flush()

    record_extractions = [
        extraction("Phụ lục A", "chunk-record-a", "Số hiệu: SN-1\nKết luận: Đạt", "record:docx.v1"),
        extraction(
            "Phụ lục A", "chunk-record-b", "Số hiệu: SN-1\nKết luận: Không đạt", "record:docx.v1"
        ),
    ]
    session.add_all(record_extractions)
    session.flush()
    records = [
        CalibrationRecord(
            document_id="BB_2024_001",
            extraction_id=record_extractions[0].id,
            device_id=device.id,
            procedure_id=procedure.id,
            calibrated_at=datetime(2024, 1, 15),
            expires_at=datetime(2025, 1, 15),
            verdict="dat",
        ),
        CalibrationRecord(
            document_id="BB_2024_001",
            extraction_id=record_extractions[1].id,
            device_id=device.id,
            procedure_id=procedure.id,
            calibrated_at=datetime(2025, 1, 15),
            expires_at=datetime(2026, 1, 15),
            verdict="khong_dat",
        ),
    ]
    session.add_all(records)
    session.flush()
    session.add_all(
        [
            MeasurementPoint(
                record_id=records[0].id,
                ord=1,
                step_code="6.3.1",
                label="10 bar",
                nominal_value=10.0,
                measured_value=10.1,
                error_value=0.1,
                unit_id=unit_bar.id,
                limit_value=0.5,
                within_limit=1,
                quote="1 | 10 | 10,1 | 0,1 | 0,5",
                error_text="0,1",
                limit_text="0,5",
            ),
            MeasurementPoint(
                record_id=records[1].id,
                ord=1,
                step_code="6.3.1",
                label="10 bar",
                nominal_value=10.0,
                measured_value=10.8,
                error_value=0.8,
                unit_id=unit_bar.id,
                limit_value=0.5,
                within_limit=0,
                quote="1 | 10 | 10,8 | 0,8 | 0,5",
                error_text="0,8",
                limit_text="0,5",
            ),
        ]
    )
    session.commit()
    return session


# ── Chạy eval ─────────────────────────────────────────────────────────────────


def evaluate(
    golden_path: Path = DEFAULT_GOLDEN,
    *,
    live: bool = False,
    session=None,
) -> dict:
    """Chạy tập vàng; trả báo cáo độ chính xác intent + bất biến P1/fallback."""
    golden = load_golden(golden_path)
    session = session or build_session()

    classifier = None
    if live:
        classifier = intents.default_classifier()

    correct = 0
    routed: list[dict] = []
    text_entries = 0
    text_ok = 0
    data_entries = 0
    untraceable: list[str] = []
    resolver_errors: list[str] = []

    for entry in golden:
        question = entry["question"]
        raw = None if live else _raw_for(entry)
        active = classifier if live else ScriptedClassifier(raw)
        decision = router.plan_route(question, active)

        want_branch = expected_branch(entry)
        want_intent = entry.get("intent") if want_branch in ("data", "mixed") else None
        got_intent = decision.request.intent if decision.request else None
        ok = decision.branch == want_branch and got_intent == want_intent
        correct += 1 if ok else 0
        routed.append(
            {
                "question": question,
                "expected_branch": want_branch,
                "expected_intent": want_intent,
                "got_branch": decision.branch,
                "got_intent": got_intent,
                "reason": decision.reason,
                "ok": ok,
            }
        )

        if want_branch == "text":
            text_entries += 1
            if decision.branch == "text":
                text_ok += 1
            continue

        if decision.request is None:
            continue
        data_entries += 1
        try:
            payload = router.build_data_payload(session, decision.request)
        except Exception as exc:  # noqa: BLE001 - báo cáo thay vì vỡ eval
            resolver_errors.append(f"{question}: {exc}")
            continue
        problems = router.untraceable_cells(payload)
        untraceable.extend(f"{question}: {problem}" for problem in problems)

    total = len(golden) or 1
    return {
        "intent_accuracy": correct / total,
        "total": len(golden),
        "correct": correct,
        "text_entries": text_entries,
        "text_routed_text": text_ok,
        "data_entries": data_entries,
        "untraceable": untraceable,
        "resolver_errors": resolver_errors,
        "routed": routed,
        "live": live,
    }


def gate(report: dict, *, min_accuracy: float = 0.90) -> tuple[bool, list[str]]:
    """Cổng: intent ≥ ngưỡng, 0 ô số không nguồn, 0 lỗi resolver, text không lạc nhánh."""
    failures: list[str] = []
    if report["intent_accuracy"] < min_accuracy:
        failures.append(f"độ chính xác intent {report['intent_accuracy']:.3f} < {min_accuracy:.2f}")
    if report["untraceable"]:
        failures.append(f"ô số không truy được nguồn: {len(report['untraceable'])}")
    if report["resolver_errors"]:
        failures.append(f"lỗi truy vấn dữ liệu: {len(report['resolver_errors'])}")
    if report["text_routed_text"] != report["text_entries"]:
        failures.append(
            f"câu hỏi văn bản lạc sang nhánh số liệu: "
            f"{report['text_entries'] - report['text_routed_text']}"
        )
    return (not failures, failures)


def _print_report(report: dict, min_accuracy: float) -> None:
    mode = "Ollama thật" if report["live"] else "bộ phân loại kịch bản"
    print(f"Định tuyến chat lai ({mode})")
    print(
        f"  Độ chính xác intent: {report['intent_accuracy']:.3f} ({report['correct']}/{report['total']})"
    )
    print(
        f"  Câu hỏi văn bản đi đúng nhánh text: {report['text_routed_text']}/{report['text_entries']}"
    )
    print(f"  Câu hỏi số liệu chạy được resolver: {report['data_entries']}")
    print(f"  Ô số không truy được nguồn: {len(report['untraceable'])}")
    print(f"  Lỗi truy vấn dữ liệu: {len(report['resolver_errors'])}")
    for problem in report["routed"]:
        if not problem["ok"]:
            print(
                f"  ✗ {problem['question']}\n"
                f"      mong {problem['expected_branch']}/{problem['expected_intent']} "
                f"→ nhận {problem['got_branch']}/{problem['got_intent']} ({problem['reason']})"
            )
    ok, failures = gate(report, min_accuracy=min_accuracy)
    print(
        f"\nCổng: intent ≥ {min_accuracy:.2f}, 0 số không nguồn, text không lạc nhánh → {'ĐẠT' if ok else 'HỎNG'}"
    )
    for failure in failures:
        print(f"  - {failure}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval định tuyến chat lai văn bản + số liệu")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    parser.add_argument("--live", action="store_true", help="Dùng Ollama thật thay vì kịch bản")
    parser.add_argument("--json", action="store_true", help="In báo cáo dạng JSON")
    args = parser.parse_args(argv)

    report = evaluate(args.golden, live=args.live)
    ok, _ = gate(report, min_accuracy=args.min_accuracy)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report, args.min_accuracy)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
