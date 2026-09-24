"""Guard P3: tầng ``query/`` chỉ được đọc view đã duyệt.

Sprint 6 mở ``query/`` thật (``query/approved.py``) làm bề mặt tra cứu đầu tiên,
nên guard từ Sprint 4 giờ bảo vệ code thật chứ không chỉ khung sẵn sàng. Bộ test
khoá ba việc: guard phát hiện bảng gốc, guard cho qua view, và module đã duyệt
thực sự không nhắc tới tên bảng gốc nào trong câu SQL.
"""

from __future__ import annotations

from db.views import RAW_TABLES, scan_query_source
from query import approved


def test_scanner_flags_raw_table_access(tmp_path):
    (tmp_path / "intents.py").write_text(
        "rows = conn.execute('SELECT * FROM procedure_fact')\n", encoding="utf-8"
    )
    violations = scan_query_source(tmp_path)
    assert len(violations) == 1
    assert "procedure_fact" in violations[0]


def test_scanner_flags_raw_table_in_join(tmp_path):
    (tmp_path / "intents.py").write_text(
        "SELECT f.* FROM extraction e JOIN procedure_standard s ON 1=1\n",
        encoding="utf-8",
    )
    violations = scan_query_source(tmp_path)
    assert any("extraction" in violation for violation in violations)
    assert any("procedure_standard" in violation for violation in violations)


def test_scanner_allows_approved_views(tmp_path):
    (tmp_path / "intents.py").write_text(
        "SELECT * FROM v_procedure_fact\nSELECT * FROM v_term\n",
        encoding="utf-8",
    )
    assert scan_query_source(tmp_path) == []


def test_scanner_handles_missing_directory(tmp_path):
    assert scan_query_source(tmp_path / "khong_ton_tai") == []


def test_repo_query_layer_is_clean(repo_root):
    assert scan_query_source(repo_root / "query") == []


def test_approved_sql_only_touches_views():
    sql = " ".join(
        (
            approved.APPROVED_FACT_SQL,
            approved.APPROVED_STANDARD_SQL,
            approved.APPROVED_TERM_SQL,
        )
    )
    assert "v_procedure_fact" in sql and "v_procedure_standard" in sql and "v_term" in sql
    for table in RAW_TABLES:
        assert f"FROM {table}" not in sql
        assert f"JOIN {table}" not in sql
