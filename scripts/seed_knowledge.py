#!/usr/bin/env python
"""Seed/upsert khung khái niệm đo lường: quantity, unit, device_type (spec §5.1).

Idempotent: chạy lại chỉ cập nhật theo ``code``/``name_vi``, không tạo trùng.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal
from knowledge.seed_data import seed_reference_data


def main() -> int:
    db = SessionLocal()
    try:
        counts = seed_reference_data(db)
        db.commit()
        print(
            "Đã seed: {quantity} đại lượng, {unit} đơn vị, {device_type} loại thiết bị.".format(
                **counts
            )
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
