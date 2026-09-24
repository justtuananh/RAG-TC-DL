from ingestion.classify import classify_document


def test_classifies_qtkd_from_filename():
    result = classify_document("QTKD 1.061 2021 ND.docx")
    assert result.doc_type == "qtkd"
    assert result.confidence >= 0.95


def test_classifies_calibration_record_from_content():
    result = classify_document("record.docx", "Biên bản kiểm định phương tiện đo")
    assert result.doc_type == "ho_so_kiem_dinh"


def test_unknown_documents_are_not_guessed():
    result = classify_document("notes.docx", "Nội dung không theo mẫu")
    assert result.doc_type == "khac"
    assert result.confidence < 0.5
