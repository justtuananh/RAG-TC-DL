"""Nạp tài liệu QTKĐ qua terminal: đọc tệp ở máy này, đẩy lên API (local hoặc host qua SSH).

Dùng đúng đường của giao diện: login → POST /api/documents/upload → POST .../process → poll
GET /api/documents tới khi xong. Chỉ dùng thư viện chuẩn nên chạy được trên máy không có venv dự án.

    # API đang chạy ngay trên máy này
    python scripts/ingest_cli.py TC_DL/ --user admin --password-file ~/.qtkd_pw

    # API ở host: mở tunnel SSH -L, mật khẩu SSH đọc từ tệp (không hỏi, không cần sshpass)
    python scripts/ingest_cli.py ~/qtkd/*.docx --ssh hii@host --ssh-pass-file ~/.host_pw \\
        --user admin --password-file ~/.qtkd_pw

Mật khẩu tài khoản ứng dụng: nhập khi được hỏi (không hiện trên màn hình), hoặc --password-file / biến môi trường QTKD_PASSWORD.
Tài khoản cần vai trò technician/admin. Thư mục được duyệt đệ quy lấy .docx/.doc/.pdf.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shlex
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from urllib import error, request
from urllib.parse import quote

UPLOAD_EXTS = (".docx", ".doc", ".pdf")
DONE_STATUSES = {"ready", "superseded", "error"}
POLL_S = 2.0


class CliError(RuntimeError):
    pass


def collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in UPLOAD_EXTS)
        elif p.is_file():
            files.append(p)
        else:
            raise CliError(f"Không thấy: {p}")
    return files


def read_secret(path: str | None, env: str) -> str | None:
    if path:
        return Path(path).expanduser().read_text(encoding="utf-8").rstrip("\r\n")
    return os.environ.get(env)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_port(port: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


@contextmanager
def ssh_tunnel(target: str, pass_file: str, remote_port: int):
    """Tunnel `-L` tới API trên host; mật khẩu SSH đưa qua SSH_ASKPASS (đọc từ tệp)."""
    pw_path = Path(pass_file).expanduser()
    if not pw_path.is_file():
        raise CliError(f"Không thấy tệp mật khẩu SSH: {pw_path}")
    with tempfile.TemporaryDirectory() as tmp:
        askpass = Path(tmp) / "askpass.sh"
        askpass.write_bytes(os.fsencode(f"#!/bin/sh\ncat {shlex.quote(str(pw_path))}\n"))
        askpass.chmod(stat.S_IRWXU)
        local_port = _free_port()
        env = {**os.environ, "SSH_ASKPASS": str(askpass), "SSH_ASKPASS_REQUIRE": "force"}
        proc = subprocess.Popen(
            [
                "ssh", "-N", "-L", f"{local_port}:127.0.0.1:{remote_port}",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "PreferredAuthentications=password,keyboard-interactive",
                "-o", "NumberOfPasswordPrompts=1",
                target,
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            if not _wait_port(local_port, 20) or proc.poll() is not None:
                proc.terminate()
                detail = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
                raise CliError(f"Không mở được tunnel SSH tới {target}: {detail}")
            yield f"http://127.0.0.1:{local_port}"
        finally:
            proc.terminate()
            proc.wait(timeout=5)


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token: str | None = None

    def _call(self, method: str, path: str, body: bytes | None, content_type: str) -> dict:
        headers = {"Content-Type": content_type}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = request.Request(self.base + path, data=body, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read() or b"{}")
        except error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except json.JSONDecodeError:
                pass
            raise CliError(f"HTTP {e.code} {path}: {detail}") from None
        except error.URLError as e:
            raise CliError(f"Không gọi được {self.base}{path}: {e.reason}") from None

    def login(self, username: str, password: str) -> None:
        body = json.dumps({"username": username, "password": password}).encode()
        self.token = self._call("POST", "/api/auth/login", body, "application/json")["access_token"]

    def upload(self, path: Path) -> dict:
        boundary = uuid.uuid4().hex
        head = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8", "surrogateescape")  # locale ASCII: tên tệp mang byte UTF-8 gốc, gửi nguyên byte
        body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self._call("POST", "/api/documents/upload", body, f"multipart/form-data; boundary={boundary}")

    def process(self, doc_id: str) -> None:
        self._call("POST", f"/api/documents/{quote(doc_id)}/process", b"", "application/json")

    def documents(self) -> list[dict]:
        return self._call("GET", "/api/documents", None, "application/json")["documents"]

    def document(self, doc_id: str) -> dict | None:
        return next((d for d in self.documents() if d["id"] == doc_id), None)


def ingest_one(api: Api, path: Path) -> tuple[str, float]:
    """Upload + xử lý một tệp, chờ xong. Trả (trạng thái, giây)."""
    start = time.monotonic()
    doc = api.upload(path)
    return process_and_wait(api, doc["id"], start)


def process_and_wait(api: Api, doc_id: str, start: float | None = None) -> tuple[str, float]:
    """Bấm "Xử lý" cho tài liệu đã có trong kho, chờ xong. Trả (trạng thái, giây)."""
    start = time.monotonic() if start is None else start
    api.process(doc_id)
    last = ""
    while True:
        time.sleep(POLL_S)
        current = api.document(doc_id)
        if current is None:
            return "error: tài liệu biến mất", time.monotonic() - start
        stage = f"{current['status']} {current['progress']}%"
        if stage != last:
            print(f"    {stage}", flush=True)
            last = stage
        if current["status"] in DONE_STATUSES:
            suffix = f": {current['error']}" if current.get("error") else ""
            return current["status"] + suffix, time.monotonic() - start


Job = tuple[str, Callable[[], tuple[str, float]]]


def run_jobs(jobs: list[Job]) -> int:
    failed = 0
    for i, (label, work) in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {label}", flush=True)
        try:
            status, secs = work()
        except CliError as e:
            print(f"    BỎ QUA/LỖI: {e}")
            failed += 1
            continue
        print(f"    -> {status} ({secs:.1f}s)")
        failed += status.startswith("error")
    print(f"\nXong: {len(jobs) - failed}/{len(jobs)} tệp", file=sys.stderr)
    return 1 if failed else 0


def run(api: Api, files: list[Path], process_pending: bool) -> int:
    jobs: list[Job] = [(f.name, lambda f=f: ingest_one(api, f)) for f in files]
    if process_pending:
        # Tài liệu đã upload nhưng chưa xử lý xong (lần nạp trước dở dang) bị chặn "trùng nội dung"
        # nếu nạp lại; xử lý thẳng bản ghi đã có.
        jobs += [
            (f"{d['name']} (đã có trong kho)", lambda d=d: process_and_wait(api, d["id"]))
            for d in api.documents()
            if d["status"] == "pending"
        ]
    return run_jobs(jobs)


def main() -> int:
    # Console Windows / SSH hay mặc định ASCII hoặc cp1252: tiếng Việt sẽ làm print() văng UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Nạp tài liệu QTKĐ qua terminal")
    parser.add_argument("paths", nargs="*", help="Tệp hoặc thư mục (.docx/.doc/.pdf).")
    parser.add_argument("--api", default="http://localhost:8080", help="URL API khi không dùng --ssh.")
    parser.add_argument("--ssh", metavar="USER@HOST", help="Mở tunnel SSH tới API trên host.")
    parser.add_argument("--ssh-pass-file", help="Tệp chứa mật khẩu SSH (bắt buộc với --ssh).")
    parser.add_argument("--remote-port", type=int, default=8080, help="Cổng API trên host.")
    parser.add_argument("--user", default=os.environ.get("QTKD_USER"), help="Tài khoản ứng dụng.")
    parser.add_argument("--password-file", help="Tệp mật khẩu tài khoản ứng dụng.")
    parser.add_argument(
        "--process-pending", action="store_true",
        help="Xử lý luôn các tài liệu đã upload nhưng đang chờ (pending) trong kho.",
    )
    args = parser.parse_args()

    try:
        password = read_secret(args.password_file, "QTKD_PASSWORD")
        if not password and args.user and sys.stdin.isatty():
            password = getpass.getpass(f"Mật khẩu của {args.user}: ")
        if not args.user or not password:
            raise CliError("Thiếu tài khoản: dùng --user (mật khẩu sẽ được hỏi, hoặc --password-file / QTKD_PASSWORD).")
        files = collect_files(args.paths)
        if not files and not args.process_pending:
            raise CliError("Không có tệp .docx/.doc/.pdf nào (hoặc dùng --process-pending).")
        if args.ssh:
            if not args.ssh_pass_file:
                raise CliError("--ssh cần --ssh-pass-file.")
            with ssh_tunnel(args.ssh, args.ssh_pass_file, args.remote_port) as base:
                api = Api(base)
                api.login(args.user, password)
                return run(api, files, args.process_pending)
        api = Api(args.api)
        api.login(args.user, password)
        return run(api, files, args.process_pending)
    except CliError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
