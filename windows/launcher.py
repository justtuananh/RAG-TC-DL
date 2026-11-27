"""Khởi động/dừng toàn bộ QTKĐ RAG bản native trên Windows.

Thứ tự nạp quan trọng vì GPU 8 GB: Ollama (LLM) trước, rồi reranker, rồi embedding,
cuối cùng là API. Mỗi dịch vụ chỉ lên GPU khi còn đủ VRAM; server suy luận tự về CPU
nếu thiếu (xem docker/inference/server.py).

Lệnh:
  python -m windows.launcher start     # chạy full, mở trình duyệt (mặc định)
  python -m windows.launcher setup     # migrate + đăng ký tài liệu + index (bộ cài gọi)
  python -m windows.launcher index     # index lại build/ vào Qdrant
  python -m windows.launcher migrate   # chỉ chạy Alembic
  python -m windows.launcher status    # kiểm tra dịch vụ đang trả lời
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in (None, ""):
    # Cho phép chạy trực tiếp: python app/windows/launcher.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from windows.common import (  # noqa: E402
    IS_WINDOWS,
    Layout,
    http_json,
    http_ok,
    port_available,
    read_env,
    run,
    wait_for,
)


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _port(url: str) -> int:
    parts = urlsplit(url)
    if parts.port:
        return parts.port
    return 443 if parts.scheme == "https" else 80


def _root(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


@dataclass
class Service:
    name: str
    proc: subprocess.Popen | None = None
    log: Any = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None


@dataclass
class Stack:
    layout: Layout
    settings: object
    env: dict[str, str]
    services: list[Service] = field(default_factory=list)
    postgres_started: bool = False

    # ── tiến trình con ──────────────────────────────────────────────────────

    def start_process(self, name: str, cmd: list[str], *, cwd: Path | None = None) -> Service:
        handle = (self.layout.logs / f"{name}.log").open("ab", buffering=0)
        flags = 0
        if IS_WINDOWS:
            flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        proc = subprocess.Popen(
            [str(part) for part in cmd],
            cwd=str(cwd or self.layout.app),
            env=self.env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        assign_to_job(proc)
        service = Service(name=name, proc=proc, log=handle)
        self.services.append(service)
        print(f"  [{name}] pid {proc.pid}, log {handle.name}")
        return service

    def stop_process(self, service: Service, timeout_s: float = 15) -> None:
        proc = service.proc
        if proc is None or proc.poll() is not None:
            self._close_log(service)
            return
        print(f"  dừng {service.name} (pid {proc.pid})")
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        else:
            proc.terminate()
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout_s)
        self._close_log(service)

    @staticmethod
    def _close_log(service: Service) -> None:
        if service.log is not None:
            service.log.close()
            service.log = None

    # ── từng dịch vụ ────────────────────────────────────────────────────────

    def postgres(self) -> None:
        s = self.settings
        pg_ctl = self.layout.pg_bin / ("pg_ctl.exe" if IS_WINDOWS else "pg_ctl")
        pg_isready = self.layout.pg_bin / ("pg_isready.exe" if IS_WINDOWS else "pg_isready")
        if not (self.layout.postgres_data / "PG_VERSION").is_file():
            raise SystemExit("Chưa có cơ sở dữ liệu Postgres. Chạy lại bộ cài (CaiDat.bat).")

        def ready() -> bool:
            result = subprocess.run(
                [
                    str(pg_isready),
                    "-h",
                    s.database.host,
                    "-p",
                    str(s.database.port),
                    "-q",
                ],
                capture_output=True,
            )
            return result.returncode == 0

        if ready():
            if self._database_reachable():
                print("  [postgres] đã chạy sẵn")
                return
            raise SystemExit(
                f"Cổng {s.database.port} có Postgres khác đang chạy nhưng không mở được "
                f"cơ sở dữ liệu {s.database.name}. Đổi POSTGRES_PORT trong app/.env "
                "hoặc đóng Postgres đó rồi chạy lại."
            )

        self.layout.logs.mkdir(parents=True, exist_ok=True)
        run(
            [
                str(pg_ctl),
                "-D",
                str(self.layout.postgres_data),
                "-l",
                str(self.layout.logs / "postgres.log"),
                "-o",
                f"-p {s.database.port} -h {s.database.host}",
                "-w",
                "start",
            ],
            env=self.env,
        )
        self.postgres_started = True
        wait_for(ready, what="Postgres", timeout_s=90)

    def _database_reachable(self) -> bool:
        s = self.settings
        psql = self.layout.pg_bin / ("psql.exe" if IS_WINDOWS else "psql")
        result = subprocess.run(
            [
                str(psql),
                "-h",
                s.database.host,
                "-p",
                str(s.database.port),
                "-U",
                s.database.user,
                "-d",
                s.database.name,
                "-tAc",
                "select 1",
            ],
            env={**self.env, "PGPASSWORD": s.database.password.get_secret_value()},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0 and result.stdout.strip() == "1"

    def _qdrant_headers(self) -> dict[str, str]:
        key = self.settings.services.qdrant_api_key
        return {"api-key": key.get_secret_value()} if key is not None else {}

    def _qdrant_ok(self) -> bool:
        return http_ok(
            _root(self.settings.services.qdrant_url) + "/collections",
            headers=self._qdrant_headers(),
        )

    def qdrant(self) -> None:
        s = self.settings
        if self._qdrant_ok():
            print("  [qdrant] đã chạy sẵn")
            return
        port = _port(s.services.qdrant_url)
        if not port_available(port):
            raise SystemExit(
                f"Cổng {port} đang bị chương trình khác chiếm (không phải Qdrant của QTKĐ-RAG)."
            )
        if not self.layout.qdrant_exe.is_file():
            raise SystemExit(f"Thiếu {self.layout.qdrant_exe}; chạy lại bộ cài.")
        self.start_process("qdrant", [self.layout.qdrant_exe], cwd=self.layout.qdrant_exe.parent)
        wait_for(self._qdrant_ok, what="Qdrant", timeout_s=120)

    def ollama(self, *, preload: bool = True, allow_pull: bool = True) -> None:
        s = self.settings
        root = _root(s.services.ollama_url)
        if http_ok(root + "/api/tags"):
            print("  [ollama] đã chạy sẵn (không dừng khi thoát)")
        else:
            if not self.layout.ollama_exe.is_file():
                raise SystemExit(f"Thiếu {self.layout.ollama_exe}; chạy lại bộ cài.")
            self.start_process("ollama", [self.layout.ollama_exe, "serve"])
            wait_for(lambda: http_ok(root + "/api/tags"), what="Ollama", timeout_s=120)

        model = self.settings.llm_model("chat")
        if not self._ollama_has_model(root, model):
            if not allow_pull:
                raise SystemExit(
                    f"Thiếu model Ollama {model} và đang cài offline. "
                    "Chép thư mục models/ từ gói cài có model vào data/models/ollama."
                )
            print(f"  [ollama] tải model {model} (lần đầu, có thể vài GB)...")
            run([self.layout.ollama_exe, "pull", model], env=self.env)
        if preload:
            self._preload_llm(root, model)

    @staticmethod
    def _ollama_has_model(root: str, model: str) -> bool:
        try:
            tags = http_json(root + "/api/tags")
        except (OSError, ValueError):
            return False
        names = set()
        for entry in tags.get("models", []):
            names.add(entry.get("name", ""))
            names.add(entry.get("model", ""))
        wanted = {model, model if ":" in model else f"{model}:latest"}
        return bool(wanted & names)

    def _preload_llm(self, root: str, model: str) -> None:
        """Nạp LLM lên GPU trước reranker/embedding để nó có trọn VRAM."""
        chat = self.settings.llm.chat
        payload = json.dumps(
            {
                "model": model,
                "prompt": "",
                "keep_alive": chat.keep_alive,
                "options": {"num_ctx": chat.num_ctx},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            root + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                response.read()
        except OSError as exc:
            print(f"  [ollama] không nạp trước được model ({exc}); lần chat đầu sẽ nạp")

    def inference(self, mode: str, port: int) -> None:
        s = self.settings
        vm = s.models.embedding if mode == "embedding" else s.models.reranker
        env_extra = {
            "MODE": mode,
            "PORT": str(port),
            "HOST": "127.0.0.1",
            "HF_HOME": str(self.layout.hf_home),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
        if mode == "embedding":
            env_extra["EMBEDDING_MODEL"] = vm.name
        else:
            env_extra["RERANKER_MODEL"] = vm.name
            env_extra["RERANKER_MAX_LENGTH"] = str(vm.max_length)
        old = self.env
        self.env = {**old, **env_extra}
        try:
            self.start_process(
                mode,
                [
                    self.layout.python_exe,
                    str(self.layout.app / "docker" / "inference" / "server.py"),
                ],
            )
        finally:
            self.env = old
        wait_for(
            lambda: http_ok(f"http://127.0.0.1:{port}/health"),
            what=f"{mode} (nạp model)",
            timeout_s=900,
        )

    def api(self) -> None:
        s = self.settings
        self.start_process("api", [self.layout.python_exe, "-m", "api.main"])
        wait_for(
            lambda: http_ok(f"http://{s.api.host}:{s.api.port}/api/health"),
            what="API",
            timeout_s=180,
        )

    # ── vòng đời ────────────────────────────────────────────────────────────

    def start_all(self, *, open_browser: bool = True) -> None:
        self.layout.logs.mkdir(parents=True, exist_ok=True)
        print("Khởi động QTKĐ RAG...")
        self.postgres()
        self.qdrant()
        self.ollama()
        self.inference("reranker", _port(self.settings.services.rerank_url))
        self.inference("embedding", _port(self.settings.services.embedding_url))
        self.api()
        url = f"http://{self.settings.api.host}:{self.settings.api.port}"
        print(f"\nSẵn sàng: {url}   (Ctrl+C để dừng)")
        if open_browser and IS_WINDOWS:
            webbrowser.open(url)

    def stop_all(self) -> None:
        print("\nĐang dừng...")
        for service in reversed(self.services):
            self.stop_process(service)
        if self.postgres_started:
            self.stop_postgres()

    def stop_postgres(self) -> None:
        pg_ctl = self.layout.pg_bin / ("pg_ctl.exe" if IS_WINDOWS else "pg_ctl")
        subprocess.run(
            [str(pg_ctl), "-D", str(self.layout.postgres_data), "-m", "fast", "-w", "stop"],
            capture_output=True,
            text=True,
        )
        print("  dừng postgres")

    # ── lệnh cài đặt ────────────────────────────────────────────────────────

    def migrate(self) -> None:
        print("Chạy migration cơ sở dữ liệu...")
        run(
            [self.layout.python_exe, "-m", "scripts.migrate", "upgrade", "head"],
            cwd=self.layout.app,
            env=self.env,
        )

    def register_documents(self) -> None:
        print("Đăng ký tài liệu có sẵn vào sổ...")
        run(
            [
                self.layout.python_exe,
                "-m",
                "scripts.migrate_documents",
                "--apply",
                "--source",
                str(self.layout.source_dir),
                "--out",
                str(self.layout.markdown_dir),
            ],
            cwd=self.layout.app,
            env=self.env,
        )

    def create_admin_if_requested(self) -> None:
        username = self.env.get("QTKD_ADMIN_USERNAME")
        password = self.env.get("QTKD_ADMIN_PASSWORD")
        if not username or not password:
            return
        print(f"Tạo tài khoản quản trị {username} (nếu chưa có)...")
        child_env = {key: value for key, value in self.env.items() if key != "QTKD_ADMIN_PASSWORD"}
        result = subprocess.run(
            [
                str(self.layout.python_exe),
                "scripts/create_admin.py",
                "--username",
                username,
                "--password-stdin",
                "--if-missing",
            ],
            cwd=str(self.layout.app),
            env=child_env,
            input=password + "\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.stdout:
            print(result.stdout.rstrip())
        if result.returncode != 0:
            raise SystemExit(f"Không tạo được tài khoản quản trị: {result.stderr.strip()}")
        # Không để mật khẩu quản trị nằm trong môi trường của các dịch vụ chạy tiếp.
        self.env.pop("QTKD_ADMIN_PASSWORD", None)

    def index(self) -> None:
        print("Index tài liệu vào Qdrant...")
        run(
            [self.layout.python_exe, "-m", "vectorstore.index"],
            cwd=self.layout.app,
            env=self.env,
        )

    def setup(self, *, index: bool = True) -> None:
        """Cài đặt một lần: DB, sổ tài liệu, tài khoản, chỉ mục. Idempotent."""
        print("Hoàn tất cài đặt QTKĐ RAG...")
        started: list[Service] = []
        was_postgres = self.postgres_started
        try:
            self.postgres()
            self.migrate()
            self.register_documents()
            self.create_admin_if_requested()
            if not index:
                print("  bỏ qua index (--skip-index).")
                return

            if self._qdrant_ok():
                print("  [qdrant] đã chạy sẵn")
            else:
                started.append(self._start_qdrant_for_setup())
            if http_ok(f"http://127.0.0.1:{_port(self.settings.services.embedding_url)}/health"):
                print("  [embedding] đã chạy sẵn")
            else:
                started.append(self._start_inference_for_setup("embedding"))
            self.index()
        finally:
            for service in reversed(started):
                self.stop_process(service)
            if self.postgres_started and not was_postgres:
                self.stop_postgres()

    def _start_qdrant_for_setup(self) -> Service:
        self.qdrant()
        return self.services[-1]

    def _start_inference_for_setup(self, mode: str) -> Service:
        port = _port(
            self.settings.services.embedding_url
            if mode == "embedding"
            else self.settings.services.rerank_url
        )
        self.inference(mode, port)
        return self.services[-1]


# ── Job Object: đóng cửa sổ là con chết theo, không bỏ lại tiến trình mồ côi ──

_JOB_HANDLE = None


def assign_to_job(proc: subprocess.Popen) -> None:
    if not IS_WINDOWS:
        return
    global _JOB_HANDLE
    if _JOB_HANDLE is None:
        _JOB_HANDLE = _create_kill_on_close_job()
    if not _JOB_HANDLE:
        return
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.AssignProcessToJobObject(_JOB_HANDLE, int(proc._handle))  # type: ignore[attr-defined]
    except (OSError, AttributeError, ValueError):
        pass


def _create_kill_on_close_job():
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            job,
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),  # JobObjectExtendedLimitInformation
        )
        return job if ok else None
    except (OSError, AttributeError):
        return None


# ── env ─────────────────────────────────────────────────────────────────────


def build_stack(root: str | None = None) -> Stack:
    layout = Layout.at(root) if root else Layout.current()
    layout.ensure_installed()

    env = {**os.environ.copy(), **read_env(layout.env_file)}
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "QTKD_DATA_DIR": str(layout.data),
            "QTKD_SOURCE_DIR": str(layout.source_dir),
            "QTKD_MARKDOWN_DIR": str(layout.markdown_dir),
            "FORMULA_REGISTRY_DB": str(layout.data / "registry" / "registry.sqlite3"),
            "QTKD_APPROVAL_DIR": str(layout.data / "approval_copies"),
            "QTKD_REGISTRY_DIR": str(layout.data / "registry_sources"),
            "QTKD_LOGGING_FILE": str(layout.logs / "app.log"),
            "HF_HOME": str(layout.hf_home),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "OLLAMA_MODELS": str(layout.ollama_models),
            "OLLAMA_CONTEXT_LENGTH": str(8192),
            "OLLAMA_KEEP_ALIVE": "-1",
            "OLLAMA_MAX_LOADED_MODELS": "1",
            "QDRANT__STORAGE__STORAGE_PATH": str(layout.qdrant_storage),
            "QDRANT__SERVICE__HOST": "127.0.0.1",
            "QDRANT__TELEMETRY_DISABLED": "true",
        }
    )
    if layout.ruby_exe.is_file():
        env["RUBY_BIN"] = str(layout.ruby_exe)
        env["GEM_HOME"] = str(layout.ruby_dir / "gems")
    else:
        # Không có Ruby portable: để nguyên ruby trên PATH (nếu người dùng đã cài),
        # tránh trỏ RUBY_BIN vào file không tồn tại.
        env.pop("RUBY_BIN", None)
        env.pop("GEM_HOME", None)
    env["PATH"] = os.pathsep.join(
        [str(layout.python_dir), str(layout.ruby_dir / "bin"), env.get("PATH", "")]
    )

    from core.settings_loader import load_settings

    settings = load_settings(env=env)
    env.update(
        {
            "QDRANT__SERVICE__HTTP_PORT": str(_port(settings.services.qdrant_url)),
            "QDRANT__SERVICE__GRPC_PORT": str(_port(settings.services.qdrant_url) + 1),
            "OLLAMA_HOST": urlsplit(settings.services.ollama_url).netloc,
        }
    )
    if settings.services.qdrant_api_key is not None:
        env["QDRANT__SERVICE__API_KEY"] = settings.services.qdrant_api_key.get_secret_value()

    for path in (
        layout.data / "registry",
        layout.hf_home,
        layout.ollama_models,
        layout.qdrant_storage,
        layout.logs,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return Stack(layout=layout, settings=settings, env=env)


def check_ports(stack: Stack) -> None:
    # Chỉ kiểm cổng của ba dịch vụ mình sở hữu. Postgres/Ollama/Qdrant có thể đã
    # chạy sẵn (người dùng cài riêng) và được dùng lại một cách có kiểm tra.
    ports = {
        "API": stack.settings.api.port,
        "embedding": _port(stack.settings.services.embedding_url),
        "reranker": _port(stack.settings.services.rerank_url),
    }
    busy = {name: port for name, port in ports.items() if not port_available(port)}
    if busy:
        detail = ", ".join(f"{name}:{port}" for name, port in busy.items())
        raise SystemExit(
            f"Cổng đang bị chiếm: {detail}. Có thể QTKĐ-RAG đang chạy sẵn; "
            "đóng cửa sổ QTKĐ-RAG cũ rồi chạy lại."
        )


def status(stack: Stack) -> int:
    checks = {
        "API": f"http://{stack.settings.api.host}:{stack.settings.api.port}/api/health",
        "embedding": f"{_root(stack.settings.services.embedding_url)}/health",
        "reranker": f"{_root(stack.settings.services.rerank_url)}/health",
        "qdrant": f"{_root(stack.settings.services.qdrant_url)}/healthz",
        "ollama": f"{_root(stack.settings.services.ollama_url)}/api/tags",
    }
    for name, url in checks.items():
        print(f"  {name:10} {'OK' if http_ok(url) else 'KHÔNG trả lời'}  {url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else "start"
    if command in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    root = None
    if "--root" in argv:
        index = argv.index("--root")
        root = argv[index + 1]
    stack = build_stack(root)

    if command == "status":
        return status(stack)
    if command == "setup":
        stack.setup(index="--skip-index" not in argv)
        return 0
    if command == "models":
        offline = "--offline" in argv
        if not offline:
            env = {**stack.env, "HF_HUB_OFFLINE": "0", "TRANSFORMERS_OFFLINE": "0"}
            run(
                [stack.layout.python_exe, "-m", "windows.models"],
                cwd=stack.layout.app,
                env=env,
            )
        else:
            run(
                [stack.layout.python_exe, "-m", "windows.models", "--offline"],
                cwd=stack.layout.app,
                env=stack.env,
            )
        stack.ollama(preload=False, allow_pull=not offline)
        stack.stop_all()
        return 0
    if command == "migrate":
        stack.postgres()
        try:
            stack.migrate()
        finally:
            if stack.postgres_started:
                stack.stop_postgres()
        return 0
    if command == "index":
        started: list[Service] = []
        try:
            if not stack._qdrant_ok():
                stack.qdrant()
                started.append(stack.services[-1])
            embed_port = _port(stack.settings.services.embedding_url)
            if not http_ok(f"http://127.0.0.1:{embed_port}/health"):
                stack.inference("embedding", embed_port)
                started.append(stack.services[-1])
            stack.index()
        finally:
            for service in reversed(started):
                stack.stop_process(service)
        return 0
    if command in ("start", ""):
        check_ports(stack)
        try:
            stack.start_all(open_browser=("--no-browser" not in argv))
        finally:
            stack.stop_all()
        return 0
    raise SystemExit(
        f"Lệnh không hợp lệ: {command} (start | setup | models | index | migrate | status)"
    )


def _handle_signal(signum, frame) -> None:
    raise KeyboardInterrupt


def run_foreground() -> int:
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), _handle_signal)
            except (OSError, ValueError):
                pass
    try:
        return main()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(run_foreground())
