"""T1: kiểm tra tính toàn vẹn của corpus tổng hợp (số file, định dạng, tham chiếu gold).

Đây là lớp bảo vệ dưới cùng: nếu corpus/gold tự nó sai, mọi test phía trên vô
nghĩa. Không có test "không crash" — mỗi test so với một con số hoặc tập hợp cụ
thể lấy từ ``docs/superpowers/research/2026-09-25-knowledge-input-contract.md``.
"""

from __future__ import annotations

import json
import zipfile

import pytest

from tests.unit.knowledge_corpus.conftest import KNOWN_BEHAVIORS_FILE, xfail_for

# Mọi mã K hợp lệ theo bảng mục 6 của input-contract (K14 tùy chọn, không bắt buộc
# xuất hiện, nhưng nếu xuất hiện vẫn phải hợp lệ).
_VALID_CODES = {f"K{i:02d}" for i in range(1, 16)}
# Bắt buộc xuất hiện ở ít nhất một file (K08 có thể chỉ ở F02; K09 là hành vi toàn
# cục ghi trong `purpose` của D12 thay vì `known_behaviors` — xem conftest).
_REQUIRED_CODES = _VALID_CODES - {"K14"}


def _clean_stem(filename: str) -> str:
    """Làm sạch tên file giống ``scripts/knowledge_corpus/specs_io.py``: bỏ phần mở
    rộng, thay khoảng trắng bằng ``_`` (đủ cho corpus này — ký tự khác chỉ có chữ,
    số, dấu tiếng Việt và ``.``/``-`` vốn đã hợp lệ)."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem.replace(" ", "_")


def test_files_match_manifest(corpus_manifest, corpus_file_paths):
    """Tập tên file trong ``files/`` bằng đúng tập ``file`` trong manifest."""
    manifest_files = {obj["file"] for obj in corpus_manifest.values()}
    actual_files = set(corpus_file_paths.keys())
    assert actual_files == manifest_files, (
        f"Chỉ trong manifest: {manifest_files - actual_files}\n"
        f"Chỉ trong files/: {actual_files - manifest_files}"
    )


def test_group_counts(corpus_manifest):
    """Số file theo nhóm: A=12, B>=8, C=3, D=14, E=8, F=3, G=2; tổng 48..55."""
    by_group: dict[str, int] = {}
    for obj in corpus_manifest.values():
        by_group[obj["group"]] = by_group.get(obj["group"], 0) + 1

    assert by_group.get("A") == 12
    assert by_group.get("B", 0) >= 8
    assert by_group.get("C") == 3
    assert by_group.get("D") == 14
    assert by_group.get("E") == 8
    assert by_group.get("F") == 3
    assert by_group.get("G") == 2
    assert 48 <= sum(by_group.values()) <= 55


@pytest.fixture(scope="module")
def _manifest_ids(corpus_manifest) -> list[str]:
    return sorted(corpus_manifest)


def _file_format_cases(corpus_manifest) -> list[str]:
    return sorted(obj["id"] for obj in corpus_manifest.values())


@pytest.mark.parametrize(
    "manifest_id",
    [
        "A01",
        "A05",
        "A12",
        "B01",
        "B09",
        "C01",
        "C03",
        "D01",
        "D14",
        "E01",
        "E08",
        "F01",
        "F03",
        "G01",
        "G02",
    ],
)
def test_file_format_valid(manifest_id, corpus_manifest, corpus_file_paths):
    """Mọi .docx/.xlsx là zip hợp lệ có phần lõi OOXML; .pdf bắt đầu bằng %PDF.

    .doc/.xls (nhóm G) không phải zip — chỉ cần tồn tại, không kiểm cấu trúc.
    """
    obj = corpus_manifest[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    suffix = file_path.suffix.lower()

    if suffix in (".docx", ".xlsx"):
        assert zipfile.is_zipfile(file_path), f"{file_path.name} không phải zip hợp lệ"
        with zipfile.ZipFile(file_path) as zf:
            names = zf.namelist()
            required = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
            assert any(required in n for n in names), f"{file_path.name} thiếu {required}"
    elif suffix == ".pdf":
        assert file_path.read_bytes()[:5] == b"%PDF-", f"{file_path.name} không phải PDF hợp lệ"
    else:
        assert suffix in (".doc", ".xls"), f"{file_path.name}: đuôi lạ {suffix}"
        assert file_path.stat().st_size > 0


def test_gold_extract_docs_match_manifest(corpus_manifest, corpus_gold_extract):
    """Mọi ``doc`` trong hai file gold extract khớp stem đã làm sạch của một file
    nhóm A/B trong manifest."""
    manifest_stems = {
        _clean_stem(obj["file"]) for obj in corpus_manifest.values() if obj["group"] in ("A", "B")
    }
    gold_docs = {row["doc"] for row in corpus_gold_extract}
    missing = gold_docs - manifest_stems
    assert not missing, f"Gold doc không khớp manifest nhóm A/B: {sorted(missing)}"


def test_gold_section6_docs_match_manifest(corpus_manifest, corpus_gold_section6):
    """Mọi ``doc`` trong gold §6 cũng khớp stem đã làm sạch của một file nhóm A/B."""
    manifest_stems = {
        _clean_stem(obj["file"]) for obj in corpus_manifest.values() if obj["group"] in ("A", "B")
    }
    gold_docs = {row["doc"] for row in corpus_gold_section6}
    missing = gold_docs - manifest_stems
    assert not missing, f"Gold doc §6 không khớp manifest nhóm A/B: {sorted(missing)}"


def test_gold_records_files_match_manifest(corpus_manifest, corpus_gold_records):
    """Mọi ``file`` trong ``records_golden`` có trong manifest nhóm D/E."""
    manifest_d_e = {obj["file"] for obj in corpus_manifest.values() if obj["group"] in ("D", "E")}
    gold_files = {row["file"] for row in corpus_gold_records}
    missing = gold_files - manifest_d_e
    assert not missing, f"Gold file records không có trong manifest nhóm D/E: {sorted(missing)}"


@pytest.mark.parametrize(
    "manifest_id",
    [
        "A01",
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B09",
        "D01",
        "D02",
        "D03",
        "D04",
        "D06",
        "D13",
        "D14",
        "E01",
        "E06",
        "E07",
        "F01",
        "F02",
        "G01",
    ],
)
def test_known_behaviors_codes_valid(manifest_id, corpus_manifest):
    """Mọi mã K gắn vào một file trong manifest phải nằm trong bảng mục 6 hợp lệ."""
    obj = corpus_manifest[manifest_id]
    for behavior in obj.get("known_behaviors", []):
        assert behavior["code"] in _VALID_CODES, f"{manifest_id}: mã lạ {behavior['code']}"
        assert behavior.get("current"), f"{manifest_id}/{behavior['code']}: thiếu 'current'"
        assert behavior.get("expected"), f"{manifest_id}/{behavior['code']}: thiếu 'expected'"


def test_manifest_known_behaviors_match_static_source(corpus_manifest):
    """Manifest phải khớp nguồn TĨNH ``known_behaviors.json``.

    Builder đọc thẳng file này thay vì chạy code sản phẩm để đo, nên rebuild sau
    khi sửa lỗi không còn ghi đè ``current`` hay xoá cờ ``fixed``.
    """
    static = json.loads(KNOWN_BEHAVIORS_FILE.read_text(encoding="utf-8"))
    for manifest_id, obj in corpus_manifest.items():
        expected = static.get(manifest_id, [])
        assert obj.get("known_behaviors", []) == expected, (
            f"{manifest_id}: manifest khác known_behaviors.json"
        )
    extra_ids = set(static) - set(corpus_manifest)
    assert not extra_ids, f"known_behaviors.json có id lạ: {sorted(extra_ids)}"


def test_xfail_for_rejects_fixed_code(corpus_manifest):
    """Guard: ``xfail_for`` ném lỗi nếu mã đã có ``fixed`` (chặn xfail cũ sót lại)."""
    with pytest.raises(AssertionError, match="K12"):
        xfail_for(corpus_manifest, "K12", manifest_id="B02")


def test_k_codes_coverage(corpus_manifest):
    """Mỗi mã K01..K13, K15 xuất hiện ở ít nhất một file trong manifest.

    K09 là hành vi toàn cục (áp dụng mọi hồ sơ D/E, không riêng một file) nên
    không nằm trong ``known_behaviors`` của bất kỳ file nào — nó được ghi trong
    trường ``purpose`` của D12 thay vào đó (xem input-contract §6); coi việc đó là
    "xuất hiện trong manifest" theo đúng tinh thần của yêu cầu nghiệm thu.
    """
    codes_in_known_behaviors: set[str] = set()
    codes_in_purpose: set[str] = set()
    for obj in corpus_manifest.values():
        for behavior in obj.get("known_behaviors", []):
            codes_in_known_behaviors.add(behavior["code"])
        for code in _VALID_CODES:
            if code in obj.get("purpose", ""):
                codes_in_purpose.add(code)

    seen = codes_in_known_behaviors | codes_in_purpose
    missing = _REQUIRED_CODES - seen
    assert not missing, f"Mã K không xuất hiện ở manifest (known_behaviors lẫn purpose): {missing}"
    # K09 cụ thể phải tới từ purpose (không có trong known_behaviors) — khẳng định
    # rõ ràng để một thay đổi vô tình thêm K09 vào known_behaviors không bị bỏ sót.
    assert "K09" in codes_in_purpose
    assert "K09" not in codes_in_known_behaviors
