"""Setup Kibana data views and RAG performance dashboard.

Run once after Kibana is up:
    python elastic/setup_kibana.py [--kibana http://localhost:5601] --password changeme

Uses only stdlib. Creates:
  Data views:
    logs-rag.*         - custom RAG logs from rag_app.jsonl
    metrics-system.*   - system CPU/RAM from system_metrics.jsonl
  Dashboard:
    "QTKD RAG Performance"
      - Query Latency (ms)          total_ms avg over time
      - Retrieval vs LLM Time (ms)  retrieval_ms / llm_ms avg over time
      - Error Rate                  count of level:error over time
      - System CPU %                cpu_pct avg over time
      - System RAM Used (MB)        ram_used_mb avg over time
      - System RAM %                ram_pct avg over time
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

_HEADERS: dict[str, str] = {"Content-Type": "application/json", "kbn-xsrf": "true"}


def _set_auth(user: str, password: str) -> None:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    _HEADERS["Authorization"] = f"Basic {token}"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _req(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=_HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {method} {url}: {e.read().decode()}") from e


def _wait(kibana: str, retries: int = 24, delay: float = 5.0) -> None:
    print("Waiting for Kibana", end="", flush=True)
    for _ in range(retries):
        try:
            status = _req("GET", f"{kibana}/api/status")
            if status.get("status", {}).get("overall", {}).get("level") != "degraded":
                print(" ready.")
                return
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(delay)
    print()
    raise SystemExit("Kibana not reachable. Is it running?")


# ── Data views ────────────────────────────────────────────────────────────────

def _upsert_data_view(kibana: str, name: str, pattern: str) -> str:
    # Xóa data view cũ cùng tên để tránh pattern stale
    try:
        all_dv = _req("GET", f"{kibana}/api/data_views")
        for dv in all_dv.get("data_view", []):
            if dv.get("name") == name or dv.get("title") == pattern:
                _req("DELETE", f"{kibana}/api/data_views/data_view/{dv['id']}")
                print(f"  [-] removed old data view '{name}'  id={dv['id']}")
    except Exception:
        pass

    result = _req("POST", f"{kibana}/api/data_views/data_view", {"data_view": {
        "title": pattern,
        "name": name,
        "timeFieldName": "@timestamp",
    }})
    dv_id: str = result["data_view"]["id"]
    print(f"  [+] data view '{name}'  ({pattern})  id={dv_id}")

    # Refresh field list — cần thiết nếu data view tạo trước khi index có data
    try:
        _req("POST", f"{kibana}/api/data_views/data_view/{dv_id}/fields", {})
        print(f"  [~] refreshed fields for '{name}'")
    except Exception:
        pass

    return dv_id


# ── Dashboard ─────────────────────────────────────────────────────────────────

# Lens 8.x operationType map — Kibana dùng tên đầy đủ, không dùng "avg"
_OP_MAP = {
    "avg": "average",
    "last_value": "last_value",
    "count": "count",
    "sum": "sum",
    "min": "min",
    "max": "max",
}


def _line_panel(
    pid: str,
    title: str,
    x: int, y: int, w: int, h: int,
    dv_id: str,
    field: str,
    agg: str = "last_value",
    filter_query: str = "",
) -> dict[str, Any]:
    op = _OP_MAP.get(agg, agg)

    # Dùng interval 1m để mỗi bucket ≈ 1 query, tránh gộp nhiều điểm
    col_x: dict[str, Any] = {
        "label": "@timestamp",
        "dataType": "date",
        "operationType": "date_histogram",
        "sourceField": "@timestamp",
        "isBucketed": True,
        "scale": "interval",
        "params": {"interval": "0.5m", "includeEmptyRows": False},
    }

    if op == "count":
        col_y: dict[str, Any] = {
            "label": "Count",
            "dataType": "number",
            "operationType": "count",
            "isBucketed": False,
            "scale": "ratio",
            "sourceField": "___records___",
        }
    elif op == "last_value":
        # last_value: lấy giá trị thực của từng bản ghi, không tính trung bình
        col_y = {
            "label": field,
            "dataType": "number",
            "operationType": "last_value",
            "sourceField": field,
            "isBucketed": False,
            "scale": "ratio",
            "params": {
                "sortField": "@timestamp",
                "showArrayValues": False,
            },
        }
    else:
        col_y = {
            "label": f"{op}({field})",
            "dataType": "number",
            "operationType": op,
            "sourceField": field,
            "isBucketed": False,
            "scale": "ratio",
        }

    state: dict[str, Any] = {
        "datasourceStates": {
            "formBased": {
                "layers": {
                    "l1": {
                        "columns": {"col_x": col_x, "col_y": col_y},
                        "columnOrder": ["col_x", "col_y"],
                        "incompleteColumns": {},
                        "indexPatternId": dv_id,
                    }
                }
            }
        },
        "visualization": {
            "preferredSeriesType": "line",
            "legend": {"isVisible": True, "position": "right"},
            "valueLabels": "hide",
            "layers": [{
                "layerId": "l1",
                "accessors": ["col_y"],
                "xAccessor": "col_x",
                "seriesType": "line",
                "layerType": "data",
            }],
        },
        "query": {"query": filter_query, "language": "kuery"},
        "filters": [],
    }
    return {
        "type": "lens",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": pid},
        "panelIndex": pid,
        "embeddableConfig": {
            "title": title,
            "hidePanelTitles": False,
            "attributes": {
                "title": title,
                "type": "lens",
                "visualizationType": "lnsXY",
                "state": state,
                "references": [{
                    "type": "index-pattern",
                    "id": dv_id,
                    "name": "indexpattern-datasource-layer-l1",
                }],
            },
        },
    }


def _create_dashboard(kibana: str, rag_id: str, system_id: str) -> None:
    panels = [
        _line_panel("p1", "Query Latency (ms)",
                    0, 0, 24, 15, rag_id, "total_ms"),
        _line_panel("p2", "Retrieval Time (ms)",
                    24, 0, 24, 15, rag_id, "retrieval_ms"),
        _line_panel("p3", "LLM Time (ms)",
                    0, 15, 24, 15, rag_id, "llm_ms"),
        _line_panel("p4", "Errors (count per minute)",
                    24, 15, 24, 15, rag_id, "_id", "count", 'level: "error"'),
        _line_panel("p5", "System CPU %",
                    0, 30, 24, 15, system_id, "cpu_pct"),
        _line_panel("p6", "System RAM Used (MB)",
                    24, 30, 24, 15, system_id, "ram_used_mb"),
        _line_panel("p7", "System RAM %",
                    0, 45, 24, 15, system_id, "ram_pct"),
    ]
    saved_obj = {
        "attributes": {
            "title": "QTKD RAG Performance",
            "description": "Query latency, retrieval/LLM breakdown, errors, system CPU/RAM",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False}),
            # Từ bản ghi đầu tiên đến bản ghi cuối cùng của cả 2 nguồn
            "timeFrom": "2026-06-09T03:48:12.000Z",
            "timeTo": "2026-06-09T09:26:46.000Z",
            "timeRestore": True,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                })
            },
        },
        "references": [],
    }

    # Xóa dashboard cũ nếu tồn tại (tránh dùng bản stale)
    list_url = f"{kibana}/api/saved_objects/_find?type=dashboard&search_fields=title&search=QTKD+RAG+Performance"
    try:
        existing = _req("GET", list_url)
        for obj in existing.get("saved_objects", []):
            if obj.get("attributes", {}).get("title") == "QTKD RAG Performance":
                _req("DELETE", f"{kibana}/api/saved_objects/dashboard/{obj['id']}")
                print(f"  [-] deleted old dashboard  id={obj['id']}")
    except Exception:
        pass

    result = _req("POST", f"{kibana}/api/saved_objects/dashboard", saved_obj)
    print(f"  [+] dashboard 'QTKD RAG Performance'  id={result['id']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kibana", default="http://localhost:5601")
    parser.add_argument("--user", default="elastic", help="Kibana username")
    parser.add_argument("--password", default="", help="Kibana password")
    args = parser.parse_args()
    kibana = args.kibana.rstrip("/")

    if args.password:
        _set_auth(args.user, args.password)

    _wait(kibana)

    print("\nCreating data views...")
    rag_id    = _upsert_data_view(kibana, "RAG App Logs",   "logs-rag-*")
    system_id = _upsert_data_view(kibana, "System Metrics", "metrics-system-*")

    print("\nCreating dashboard...")
    _create_dashboard(kibana, rag_id, system_id)

    print(f"\nDone. Open: {kibana}/app/dashboards")
    print("Search: 'QTKD RAG Performance'")


if __name__ == "__main__":
    main()
