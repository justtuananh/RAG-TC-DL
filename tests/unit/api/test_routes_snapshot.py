"""Tách api_server.py thành router không được đổi đường dẫn, method hay thứ tự khớp route."""

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from api.main import app

_SNAPSHOT = Path(__file__).with_name("routes_snapshot.json")


def _route_table(routes: Iterable[Any]) -> Iterator[list]:
    """Bảng (path, methods) theo thứ tự khớp.

    FastAPI >= 0.121 bọc mỗi lần include_router trong một node lười (``_IncludedRouter``),
    nên ``app.routes`` không còn phẳng; bung ``original_router`` để so với snapshot.
    """
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _route_table(included.routes)
        else:
            yield [route.path, sorted(route.methods or [])]


def test_routes_match_snapshot():
    actual = list(_route_table(app.routes))
    assert actual == json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
