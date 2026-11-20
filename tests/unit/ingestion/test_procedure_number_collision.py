"""Hai tài liệu cùng số QTKĐ nhưng khác thiết bị là hai quy trình, không phải hai phiên bản.

Trước đây QTKĐ 1.062:2021 (bàn tạo áp) bị coi là bản mới của QTKĐ 1.062:2016 (cột đo xăng dầu):
bản 2016 chuyển ``superseded`` và biến mất khỏi tìm kiếm. Chỉ khi cùng đối tượng thì năm lớn hơn mới thắng.
"""

import hashlib

from db.models import Document, DocumentType, Procedure
from knowledge.procedure import (
    ensure_procedure,
    newer_version_document_id,
    parse_procedure_header,
    same_subject,
)

BAN_TAO_AP_2021 = (
    "QTKĐ 1.062 : 2021\nBÀN TẠO ÁP CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar\nQUY TRÌNH KIỂM ĐỊNH\n"
)
BAN_TAO_AP_2015 = (
    "QTKĐ 1.062 : 2015\nBÀN TẠO ÁP CÓ PHẠM VI LÀM VIỆC ĐẾN 1 000 bar\nQUY TRÌNH KIỂM ĐỊNH\n"
)
COT_DO_XANG_DAU_2016 = (
    "QTKĐ 1.062 : 2016\nCột đo xăng dầu có lưu lượng đo đến 200 L/min,\nCấp chính xác đến 0,5\n"
    "Quy trình kiểm định\n"
)


def _add(session, stem: str) -> Document:
    document = Document(
        id=stem,
        file_stem=stem,
        display_name=stem + ".docx",
        ext="DOCX",
        doc_type=DocumentType.QTKD,
        sha256=hashlib.sha256(stem.encode()).hexdigest(),
        size_bytes=1,
    )
    session.add(document)
    session.flush()
    return document


def test_same_subject_tolerates_a_revised_title_but_not_another_device():
    assert same_subject(
        "ÁP KẾ PÍTTÔNG CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar, CẤP CHÍNH XÁC ĐẾN 0,01",
        "Áp kế pít tông có phạm vi đo (-1 đến 4 000) bar, cấp chính xác đến 0,02",
    )
    assert not same_subject(
        "BÀN TẠO ÁP CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar",
        "Cột đo xăng dầu có lưu lượng đo đến 200 L/min, Cấp chính xác đến 0,5",
    )


def test_missing_title_counts_as_same_subject_to_keep_old_behaviour():
    assert same_subject("", "Bất kỳ")
    assert same_subject(None, "Bất kỳ")


def test_older_year_of_another_device_is_not_a_superseded_version(session):
    owner = _add(session, "ban_2021")
    ensure_procedure(session, owner, BAN_TAO_AP_2021)
    session.commit()
    other = _add(session, "cot_2016")
    header = parse_procedure_header(COT_DO_XANG_DAU_2016)
    assert newer_version_document_id(session, other, header) is None


def test_older_year_of_the_same_device_is_still_superseded(session):
    owner = _add(session, "ban_2021")
    ensure_procedure(session, owner, BAN_TAO_AP_2021)
    session.commit()
    old = _add(session, "ban_2015")
    header = parse_procedure_header(BAN_TAO_AP_2015)
    assert newer_version_document_id(session, old, header) == "ban_2021"


def test_colliding_document_does_not_take_over_the_procedure_row(session):
    owner = _add(session, "ban_2021")
    ensure_procedure(session, owner, BAN_TAO_AP_2021)
    session.commit()
    other = _add(session, "cot_2016")
    assert ensure_procedure(session, other, COT_DO_XANG_DAU_2016) is None
    session.commit()
    row = session.query(Procedure).filter(Procedure.number == "1.062").one()
    assert row.document_id == "ban_2021"


def test_newer_year_of_another_device_does_not_take_over_either(session):
    owner = _add(session, "cot_2016")
    ensure_procedure(session, owner, COT_DO_XANG_DAU_2016)
    session.commit()
    other = _add(session, "ban_2021")
    assert ensure_procedure(session, other, BAN_TAO_AP_2021) is None
    session.commit()
    row = session.query(Procedure).filter(Procedure.number == "1.062").one()
    assert row.document_id == "cot_2016"
