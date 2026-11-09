from ingestion.pdf_math_scan import split_runs


def test_split_runs_keeps_short_runs_unchanged():
    runs = [(False, 0, 2), (True, 3, 3)]

    assert split_runs(runs, 10) == runs


def test_split_runs_cuts_long_run_into_ordered_chunks_with_same_ocr_flag():
    result = split_runs([(False, 0, 24), (True, 25, 26)], 10)

    assert result == [
        (False, 0, 9),
        (False, 10, 19),
        (False, 20, 24),
        (True, 25, 26),
    ]


def test_split_runs_covers_every_page_exactly_once():
    result = split_runs([(False, 0, 118)], 10)

    pages = [p for _, start, end in result for p in range(start, end + 1)]
    assert pages == list(range(119))
