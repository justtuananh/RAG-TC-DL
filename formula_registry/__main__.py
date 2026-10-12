"""Backfill pending drafts for existing DOCX sources; never approves them."""

import argparse
import json
from pathlib import Path

from ingestion.spike_a import _safe

from .drafts import generate_from_docx
from .store import Registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path, help='Existing DOCX source paths')
    parser.add_argument('--report', type=Path, help='Optional JSON summary, without approvals')
    args = parser.parse_args()
    registry = Registry()
    rows = []
    for source in args.files:
        result = generate_from_docx(source, _safe(source.stem), registry)
        records = registry.list(_safe(source.stem))
        row = dict(
            file=source.name,
            **result,
            statuses={
                status: sum(r['status'] == status for r in records)
                for status in ('pending_review', 'approved', 'rejected', 'stale')
            },
        )
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
