"""Background system metrics collector (CPU / RAM / NVIDIA GPU).

Writes one JSON snapshot every METRICS_INTERVAL seconds to
$LOG_DIR/system_metrics.jsonl.

Two usage modes:
  1. Embedded in app (background thread):
       from monitoring.system_metrics import start_collector
       start_collector()

  2. Standalone on Windows host (sees the real GPU):
       python -m monitoring.system_metrics
       python -m monitoring.system_metrics --interval 5

Dependencies (add to requirements-app.txt or pip install on host):
  psutil>=5.9
  nvidia-ml-py>=12.0   (optional; silently skipped if unavailable)

Output schema per line:
  @timestamp    ISO-8601 UTC
  service       "rag-qtkd"
  event         "system_metrics"
  cpu_pct       overall CPU utilization %
  ram_used_mb   RAM used (MB)
  ram_total_mb  RAM total (MB)
  ram_pct       RAM utilization %
  gpus          list, empty if no NVIDIA GPU:
    index       GPU index
    name        e.g. "NVIDIA GeForce RTX 5060"
    gpu_pct     compute utilization %
    mem_used_mb VRAM used (MB)
    mem_total_mb VRAM total (MB)
    mem_pct     VRAM utilization %
    temp_c      temperature (Celsius)
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

try:
    import pynvml
    pynvml.nvmlInit()
    _GPU_COUNT = pynvml.nvmlDeviceGetCount()
    _NVML = True
except Exception:
    _NVML = False
    _GPU_COUNT = 0

_LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
_METRICS_FILE = _LOG_DIR / "system_metrics.jsonl"
_DEFAULT_INTERVAL = int(os.getenv("METRICS_INTERVAL", "10"))


# ── Collectors ────────────────────────────────────────────────────────────────

def _gpu_snapshots() -> list[dict]:
    if not _NVML:
        return []
    out = []
    for i in range(_GPU_COUNT):
        try:
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode()
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            out.append({
                "index": i,
                "name": name,
                "gpu_pct": util.gpu,
                "mem_used_mb": round(mem.used / 1024 / 1024),
                "mem_total_mb": round(mem.total / 1024 / 1024),
                "mem_pct": round(mem.used / mem.total * 100, 1),
                "temp_c": temp,
            })
        except Exception:
            pass
    return out


def _snapshot() -> dict:
    record: dict = {
        "@timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "service": "rag-qtkd",
        "event": "system_metrics",
    }
    if _PSUTIL:
        vm = psutil.virtual_memory()
        record["cpu_pct"] = psutil.cpu_percent(interval=None)
        record["ram_used_mb"] = round(vm.used / 1024 / 1024)
        record["ram_total_mb"] = round(vm.total / 1024 / 1024)
        record["ram_pct"] = round(vm.percent, 1)
    record["gpus"] = _gpu_snapshots()
    return record


# ── Background thread (embedded mode) ────────────────────────────────────────

_stop_event: threading.Event | None = None
_thread: threading.Thread | None = None


def _loop(stop: threading.Event, interval: int) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    if _PSUTIL:
        psutil.cpu_percent(interval=1)   # warm-up: first call always returns 0
    with open(_METRICS_FILE, "a", encoding="utf-8") as f:
        while not stop.is_set():
            try:
                f.write(json.dumps(_snapshot(), ensure_ascii=False) + "\n")
                f.flush()
            except Exception:
                pass
            stop.wait(interval)


def start_collector(interval: int = _DEFAULT_INTERVAL) -> None:
    """Start background metrics collection. Daemon thread — stops with process."""
    global _stop_event, _thread
    if _thread and _thread.is_alive():
        return
    _stop_event = threading.Event()
    _thread = threading.Thread(
        target=_loop, args=(_stop_event, interval), daemon=True, name="sys-metrics"
    )
    _thread.start()


def stop_collector() -> None:
    if _stop_event:
        _stop_event.set()


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import signal

    parser = argparse.ArgumentParser(description="System metrics: CPU/RAM/GPU → JSONL")
    parser.add_argument("--interval", type=int, default=_DEFAULT_INTERVAL)
    args = parser.parse_args()

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop.set())

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    if _PSUTIL:
        psutil.cpu_percent(interval=1)

    gpu_status = f"ok ({_GPU_COUNT} GPU)" if _NVML else "unavailable (pip install nvidia-ml-py)"
    cpu_status = "ok" if _PSUTIL else "unavailable (pip install psutil)"
    print(f"Writing to {_METRICS_FILE}  every {args.interval}s  (Ctrl+C to stop)")
    print(f"  psutil : {cpu_status}")
    print(f"  pynvml : {gpu_status}")

    with open(_METRICS_FILE, "a", encoding="utf-8") as f:
        while not stop.is_set():
            try:
                snap = _snapshot()
                line = json.dumps(snap, ensure_ascii=False)
                f.write(line + "\n")
                f.flush()
                print(line)
            except Exception as e:
                print(f"error: {e}")
            stop.wait(args.interval)

    print("stopped.")
