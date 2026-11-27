"""Cài QTKĐ RAG bản Windows native từ gói cài (không cần Docker, không cần admin).

Chạy bởi ``CaiDat.bat``:

    runtime\\python\\python.exe app\\windows\\install.py

Các bước: chép gói vào thư mục cài, cài Python deps offline từ wheels/, tạo .env,
khởi tạo Postgres, cài Ruby (nếu chưa có trong gói), tải model, migrate + index,
tạo shortcut và mục Uninstall trong Apps & features.

Chạy lại cùng lệnh là nâng cấp: giữ .env, data/, tài khoản và tài liệu đã nạp.
"""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from windows import components  # noqa: E402
from windows.common import (  # noqa: E402
    IS_WINDOWS,
    Layout,
    copy_missing,
    copy_tree,
    default_root,
    download,
    http_ok,
    load_json,
    port_available,
    random_secret,
    read_env,
    requirement_files,
    run,
    stop_postgres,
    write_env,
    write_json,
)

INSTALL_VERSION = "1.0"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cài QTKĐ RAG bản Windows native")
    parser.add_argument("--root", default=str(default_root()), help="thư mục cài")
    parser.add_argument(
        "--bundle", default=str(Path(__file__).resolve().parents[2]), help="gói cài"
    )
    parser.add_argument("--admin-user", help="tài khoản quản trị (bỏ trống để hỏi)")
    parser.add_argument("--admin-password", help="mật khẩu quản trị (bỏ trống để hỏi)")
    parser.add_argument("--offline", action="store_true", help="không tải gì từ Internet")
    parser.add_argument("--skip-models", action="store_true", help="không tải model")
    parser.add_argument("--skip-index", action="store_true", help="không index tài liệu")
    parser.add_argument(
        "--skip-ruby", action="store_true", help="không cài Ruby (mất trích công thức .docx)"
    )
    parser.add_argument("--force-deps", action="store_true", help="cài lại Python deps")
    parser.add_argument("--no-shortcuts", action="store_true", help="không tạo shortcut")
    parser.add_argument("--autostart", action="store_true", help="tự chạy khi đăng nhập Windows")
    parser.add_argument("--start", action="store_true", help="mở ứng dụng sau khi cài xong")
    return parser.parse_args(argv)


def _find_free(port: int, used: set[int], extra: int = 0) -> int:
    candidate = port
    for _ in range(200):
        ports = range(candidate, candidate + extra + 1)
        if all(p not in used and port_available(p) for p in ports):
            used.update(ports)
            return candidate
        candidate += 1
    raise SystemExit(f"Không tìm được cổng trống quanh {port}")


PORT_DEFAULTS = {
    "api": 8080,
    "embedding": 8010,
    "reranker": 8011,
    "qdrant": 6333,
    "ollama": 11434,
    "postgres": 55432,
}
PORT_KEYS = {
    "api": "API_PORT",
    "embedding": "EMBEDDING_PORT",
    "reranker": "RERANKER_PORT",
    "qdrant": "QDRANT_PORT",
    "ollama": "OLLAMA_PORT",
    "postgres": "POSTGRES_PORT",
}
# Ba cổng này là của riêng QTKĐ-RAG; đang bận nghĩa là ứng dụng cũ chưa đóng.
OUR_PORTS = ("api", "embedding", "reranker")


def choose_ports(existing: dict[str, str]) -> dict[str, int]:
    used: set[int] = set()
    ports: dict[str, int] = {}
    for name, default in PORT_DEFAULTS.items():
        extra = 1 if name == "qdrant" else 0
        if existing:
            value = int(existing.get(PORT_KEYS[name], default))
            if name in OUR_PORTS and not port_available(value):
                raise SystemExit(
                    f"Cổng {value} ({name}) đang bận. Có thể QTKĐ RAG đang chạy: "
                    "đóng cửa sổ QTKĐ RAG rồi chạy lại bộ cài."
                )
            ports[name] = value
            used.add(value)
        elif name == "ollama" and http_ok(f"http://127.0.0.1:{default}/api/tags"):
            # Ollama cài sẵn của người dùng: dùng lại, khỏi tải model lần nữa.
            ports[name] = default
            used.add(default)
        else:
            ports[name] = _find_free(default, used, extra)
    return ports


def build_env(layout: Layout, ports: dict[str, int], existing: dict[str, str]) -> dict[str, str]:
    host = "127.0.0.1"

    def keep(key: str, factory) -> str:
        return existing.get(key) or factory()

    values = {
        "APP_ENV": "production",
        "AUTH_ENABLED": "true",
        "JWT_SECRET_KEY": keep("JWT_SECRET_KEY", lambda: random_secret(48)),
        "JWT_EXPIRATION_HOURS": "24",
        "POSTGRES_HOST": host,
        "POSTGRES_PORT": str(ports["postgres"]),
        "POSTGRES_DB": "qtkd",
        "POSTGRES_USER": "qtkd_user",
        "POSTGRES_PASSWORD": keep("POSTGRES_PASSWORD", lambda: random_secret(24)),
        "QDRANT_API_KEY": keep("QDRANT_API_KEY", lambda: random_secret(32)),
        "QDRANT_URL": f"http://{host}:{ports['qdrant']}",
        "EMBED_URL": f"http://{host}:{ports['embedding']}/v1/embeddings",
        "RERANK_URL": f"http://{host}:{ports['reranker']}/v1/rerank",
        "OLLAMA_URL": f"http://{host}:{ports['ollama']}/api/chat",
        "API_HOST": host,
        "API_PORT": str(ports["api"]),
        "EMBEDDING_PORT": str(ports["embedding"]),
        "RERANKER_PORT": str(ports["reranker"]),
        "QDRANT_PORT": str(ports["qdrant"]),
        "OLLAMA_PORT": str(ports["ollama"]),
        "QTKD_DATA_DIR": layout.data.as_posix(),
        "QTKD_SOURCE_DIR": layout.source_dir.as_posix(),
        "QTKD_MARKDOWN_DIR": layout.markdown_dir.as_posix(),
        "FORMULA_REGISTRY_DB": (layout.data / "registry" / "registry.sqlite3").as_posix(),
        "QTKD_APPROVAL_DIR": (layout.data / "approval_copies").as_posix(),
        "QTKD_REGISTRY_DIR": (layout.data / "registry_sources").as_posix(),
        "QTKD_LOGGING_FILE": (layout.logs / "app.log").as_posix(),
    }
    if layout.ruby_exe.is_file():
        values["RUBY_BIN"] = layout.ruby_exe.as_posix()
        values["GEM_HOME"] = (layout.ruby_dir / "gems").as_posix()
    if (layout.tools / "pdf" / "python.exe").is_file():
        values["MARKER_PYTHON"] = (layout.tools / "pdf" / "python.exe").as_posix()
    soffice = _find_soffice(layout)
    if soffice:
        values["SOFFICE_BIN"] = soffice
    return values


def _find_soffice(layout: Layout) -> str | None:
    portable = layout.tools / "libreoffice" / "program" / "soffice.exe"
    if portable.is_file():
        return str(portable)
    found = shutil.which("soffice") or shutil.which("soffice.exe")
    if found:
        return found
    if IS_WINDOWS:
        try:
            import winreg

            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\LibreOffice\UNO\InstallPath") as key:
                        path, _ = winreg.QueryValueEx(key, "")
                except OSError:
                    continue
                candidate = Path(path) / "soffice.exe"
                if candidate.is_file():
                    return str(candidate)
        except OSError:
            pass
    return None


def requirements_hash(layout: Layout) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in requirement_files(layout.app):
        if path.is_file():
            digest.update(path.read_bytes())
    digest.update(components.PYTHON_VERSION.encode())
    for wheel in sorted(layout.wheels.glob("*.whl")):
        digest.update(wheel.name.encode())
    return digest.hexdigest()


def install_deps(layout: Layout, env: dict[str, str], force: bool) -> None:
    marker = layout.runtime / "deps.json"
    current = load_json(marker, {})
    wanted = requirements_hash(layout)
    if not force and current.get("hash") == wanted:
        print("  Python deps đã cài đúng phiên bản, bỏ qua.")
        return
    if not layout.wheels.is_dir():
        raise SystemExit(f"Thiếu thư mục wheels/ trong gói cài ({layout.wheels}).")

    run([layout.python_exe, "-m", "pip", "--version"], capture=True)
    print("  cài Python deps từ wheels/ (offline)...")
    run(
        [
            layout.python_exe,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(layout.wheels),
            "--only-binary=:all:",
            *[arg for path in requirement_files(layout.app) for arg in ("-r", str(path))],
        ],
        cwd=layout.app,
        env=env,
    )
    result = run(
        [
            layout.python_exe,
            "-c",
            "import torch; print(torch.__version__, torch.cuda.is_available())",
        ],
        cwd=layout.app,
        env=env,
        capture=True,
    )
    version, cuda = (result.stdout.strip().split() + ["", ""])[:2]
    print(f"  torch {version}, CUDA: {'có' if cuda == 'True' else 'KHÔNG (sẽ chạy CPU)'}")
    write_json(marker, {"hash": wanted, "torch": version, "cuda": cuda == "True"})


def _pg_tool(layout: Layout, name: str) -> Path:
    return layout.pg_bin / (f"{name}.exe" if IS_WINDOWS else name)


def _stop_postgres(layout: Layout) -> None:
    """Dừng Postgres cũ trước khi ghi đè tools/ (Windows khoá file đang chạy)."""
    stop_postgres(layout)


def _pg_ready(layout: Layout, host: str, port: int) -> bool:
    result = subprocess.run(
        [str(_pg_tool(layout, "pg_isready")), "-h", host, "-p", str(port), "-q"],
        capture_output=True,
    )
    return result.returncode == 0


def init_database(layout: Layout, env: dict[str, str]) -> None:
    if (layout.postgres_data / "PG_VERSION").is_file():
        print("  Postgres đã khởi tạo, bỏ qua.")
        return
    print("  khởi tạo Postgres...")
    layout.postgres_data.parent.mkdir(parents=True, exist_ok=True)
    password_file = layout.data / "pgpass.tmp"
    password_file.write_text(env["POSTGRES_PASSWORD"] + "\n", encoding="utf-8")
    try:
        run(
            [
                _pg_tool(layout, "initdb"),
                "-D",
                str(layout.postgres_data),
                "-U",
                env["POSTGRES_USER"],
                "--pwfile",
                str(password_file),
                "-E",
                "UTF8",
                "--locale=C",
                "--auth-host=scram-sha-256",
                "--auth-local=trust",
            ],
            env=env,
        )
    finally:
        password_file.unlink(missing_ok=True)

    logs = layout.logs
    logs.mkdir(parents=True, exist_ok=True)
    started = False
    try:
        run(
            [
                _pg_tool(layout, "pg_ctl"),
                "-D",
                str(layout.postgres_data),
                "-l",
                str(logs / "postgres.log"),
                "-o",
                f"-p {env['POSTGRES_PORT']} -h {env['POSTGRES_HOST']}",
                "-w",
                "start",
            ],
            env=env,
        )
        started = True
        run(
            [
                _pg_tool(layout, "createdb"),
                "-h",
                env["POSTGRES_HOST"],
                "-p",
                env["POSTGRES_PORT"],
                "-U",
                env["POSTGRES_USER"],
                env["POSTGRES_DB"],
            ],
            env={**env, "PGPASSWORD": env["POSTGRES_PASSWORD"]},
        )
    finally:
        if started:
            run(
                [
                    _pg_tool(layout, "pg_ctl"),
                    "-D",
                    str(layout.postgres_data),
                    "-m",
                    "fast",
                    "-w",
                    "stop",
                ],
                env=env,
            )


def _gem_script(layout: Layout) -> Path:
    gem = layout.ruby_dir / "bin" / "gem"
    if not gem.is_file():
        raise SystemExit(f"Thiếu gem trong Ruby portable: {gem}")
    return gem


def ensure_ruby(layout: Layout, bundle: Path, env: dict[str, str], offline: bool) -> None:
    if layout.ruby_exe.is_file():
        print(f"  Ruby: {layout.ruby_exe}")
    else:
        installer = bundle / "tools" / "installers" / "rubyinstaller.exe"
        if not installer.is_file():
            if offline:
                raise SystemExit(
                    "Gói cài thiếu tools/installers/rubyinstaller.exe và đang cài offline."
                )
            installer = download(components.RUBY_URL, installer)
        print("  cài Ruby portable (im lặng)...")
        run(
            [
                installer,
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/DIR={layout.ruby_dir}",
            ],
            env=env,
        )
        if not layout.ruby_exe.is_file():
            raise SystemExit(f"Ruby không cài được vào {layout.ruby_dir}")

    gem_env = {**env, "GEM_HOME": str(layout.ruby_dir / "gems")}
    check = subprocess.run(
        [str(layout.ruby_exe), "-e", "require 'mathtype_to_mathml'"],
        env=gem_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check.returncode == 0:
        print("  gem mathtype_to_mathml đã có.")
        return
    if offline:
        raise SystemExit("Gói cài thiếu gem mathtype_to_mathml và đang cài offline.")
    print("  cài gem mathtype_to_mathml + pry...")
    gem = _gem_script(layout)
    run(
        [
            layout.ruby_exe,
            gem,
            "install",
            "mathtype_to_mathml",
            "-v",
            components.MATTYPE_GEM_VERSION,
            "--no-document",
        ],
        env=gem_env,
    )
    run([layout.ruby_exe, gem, "install", "pry", "--no-document"], env=gem_env)
    updated = read_env(layout.env_file)
    updated["RUBY_BIN"] = layout.ruby_exe.as_posix()
    updated["GEM_HOME"] = (layout.ruby_dir / "gems").as_posix()
    write_env(layout.env_file, updated)


def _ask_admin(args: argparse.Namespace) -> tuple[str, str]:
    username = args.admin_user
    if not username:
        if not sys.stdin.isatty():
            raise SystemExit("Thiếu --admin-user khi chạy không tương tác.")
        username = input("Tên đăng nhập quản trị [admin]: ").strip() or "admin"
    password = args.admin_password or os.environ.get("QTKD_ADMIN_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Thiếu --admin-password khi chạy không tương tác.")
        while True:
            first = getpass.getpass("Mật khẩu quản trị (ít nhất 8 ký tự): ")
            second = getpass.getpass("Nhập lại mật khẩu: ")
            if first == second and len(first) >= 8:
                password = first
                break
            print("  Mật khẩu chưa khớp hoặc quá ngắn, thử lại.")
    return username, password


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_shortcut(link: Path, target: Path, workdir: Path, description: str) -> None:
    icon = (
        target
        if target.suffix.lower() in (".exe", ".ico")
        else target.parent / "runtime" / "python" / "python.exe"
    )
    script = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(str(link))});"
        f"$s.TargetPath={_ps_quote(str(target))};"
        f"$s.WorkingDirectory={_ps_quote(str(workdir))};"
        f"$s.Description={_ps_quote(description)};"
        + (f"$s.IconLocation={_ps_quote(str(icon))};" if icon.is_file() else "")
        + "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        capture_output=True,
    )


def install_shortcuts(layout: Layout, autostart: bool) -> None:
    if not IS_WINDOWS:
        return
    bat = layout.root / "QTKD-RAG.bat"
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return
    start_menu = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    desktop = Path.home() / "Desktop"
    for folder, name in (
        (start_menu, "QTKD RAG"),
        (desktop, "QTKD RAG"),
    ):
        if folder.is_dir():
            create_shortcut(folder / f"{name}.lnk", bat, layout.root, "QTKD RAG - trợ lý kiểm định")
    if autostart:
        startup = start_menu / "Startup"
        if startup.is_dir():
            create_shortcut(startup / "QTKD RAG.lnk", bat, layout.root, "QTKD RAG")
    print(f"  shortcut: {start_menu / 'QTKD RAG.lnk'}")


def register_uninstall(layout: Layout, version: str) -> None:
    if not IS_WINDOWS:
        return
    import winreg

    script = (
        f'"{layout.python_exe}" "{layout.app / "windows" / "uninstall.py"}" --root "{layout.root}"'
    )
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\QTKD-RAG",
    ) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "QTKD RAG")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "QTKD")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(layout.root))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(layout.python_exe))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, script)
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, script + " --yes")
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def write_launchers(layout: Layout) -> None:
    bat = layout.root / "QTKD-RAG.bat"
    bat.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title QTKD RAG\r\n"
        'cd /d "%~dp0app"\r\n'
        '"%~dp0runtime\\python\\python.exe" -m windows.launcher %*\r\n'
        "if errorlevel 1 (\r\n"
        "  echo.\r\n"
        '  echo QTKD RAG da dung do loi. Xem log trong "%~dp0data\\logs".\r\n'
        "  pause\r\n"
        ")\r\n",
        encoding="utf-8",
    )
    installer = layout.root / "CaiDat.bat"
    installer.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title Cai dat QTKD RAG\r\n"
        'set "PY=%~dp0runtime\\python\\python.exe"\r\n'
        'if not exist "%PY%" set "PY=python"\r\n'
        '"%PY%" "%~dp0app\\windows\\install.py" %*\r\n'
        "if errorlevel 1 pause\r\n",
        encoding="utf-8",
    )


def preflight() -> None:
    if IS_WINDOWS:
        if sys.maxsize <= 2**32:
            raise SystemExit("Cần Windows 64-bit.")
        try:
            if sys.getwindowsversion().major < 10:
                raise SystemExit("Cần Windows 10 trở lên.")
        except AttributeError:
            pass
        if shutil.which("nvidia-smi") is None:
            print(
                "  CẢNH BÁO: không thấy nvidia-smi. Máy có thể không có GPU NVIDIA; "
                "hệ thống vẫn chạy nhưng chat/rerank sẽ chậm (CPU)."
            )
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        if not (Path(system_root) / "System32" / "msvcp140.dll").is_file():
            print(
                "  CẢNH BÁO: thiếu Microsoft Visual C++ 2015-2022 Redistributable (x64). "
                "torch sẽ không nạp được. Cài từ https://aka.ms/vs/17/release/vc_redist.x64.exe "
                "rồi chạy lại CaiDat.bat."
            )


def _free_space_gb(path: Path) -> float:
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return shutil.disk_usage(probe).free / 1024**3


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.skip_models and not args.skip_index:
        print("  --skip-models: bỏ qua index vì cần model embedding.")
        args.skip_index = True
    preflight()
    bundle = Path(args.bundle).resolve()
    root = Path(args.root).resolve()
    if not (bundle / "app" / "windows" / "install.py").is_file():
        raise SystemExit(f"Không phải gói cài hợp lệ: {bundle}")
    _stop_postgres(Layout.at(root))
    free_gb = _free_space_gb(root)
    need_gb = 15 if root == bundle else 30
    if free_gb < need_gb:
        raise SystemExit(
            f"Ổ đĩa còn {free_gb:.1f} GB, cần ít nhất {need_gb} GB cho chương trình và model."
        )
    if root == bundle:
        print("Cài tại chỗ (portable).")
    else:
        print(f"Cài vào: {root}")
        if not (root / "app").is_dir():
            root.mkdir(parents=True, exist_ok=True)
        fresh = not (root / "app").is_dir()
        source_manifest = load_json(bundle / "manifest.json", {})
        target_manifest = load_json(root / "manifest.json", {})
        copy_tools = (
            fresh
            or source_manifest.get("tools_key") != target_manifest.get("tools_key")
            or not (root / "runtime" / "python").is_dir()
        )
        print("  chép chương trình...")
        copy_tree(bundle / "app", root / "app")
        # copy_tree bỏ qua build/ (dữ liệu sinh ra); Markdown mồi nằm ở đây.
        if (bundle / "app" / "build" / "spike_a").is_dir():
            copy_tree(
                bundle / "app" / "build" / "spike_a",
                root / "app" / "build" / "spike_a",
            )
        for name in ("runtime", "tools", "wheels"):
            if copy_tools or not (root / name).is_dir():
                copy_tree(bundle / name, root / name)
        if source_manifest:
            write_json(root / "manifest.json", source_manifest)

    layout = Layout.at(root)
    if (bundle / "models").is_dir():
        print("  chép model có sẵn trong gói...")
        copy_missing(bundle / "models", layout.data / "models")
    missing = [
        path
        for path in (
            layout.app / "api" / "main.py",
            layout.app / "frontend" / "dist" / "index.html",
            layout.python_exe,
            layout.qdrant_exe,
            layout.pg_bin,
            layout.ollama_exe,
        )
        if not path.exists()
    ]
    if missing:
        raise SystemExit(
            "Gói cài thiếu thành phần:\n  " + "\n  ".join(str(path) for path in missing)
        )
    layout.data.mkdir(parents=True, exist_ok=True)
    layout.logs.mkdir(parents=True, exist_ok=True)
    if not layout.python_exe.is_file():
        raise SystemExit(f"Thiếu Python portable: {layout.python_exe}")

    # .env cũ được đọc trước khi chép đè (đã chép ở trên nhưng app/.env được giữ nguyên
    # qua shutil.copytree với dirs_exist_ok); đọc để giữ bí mật và cổng.
    existing = read_env(layout.env_file)
    ports = choose_ports(existing)
    env = build_env(layout, ports, existing)
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "PATH": os.pathsep.join(
                [str(layout.python_dir), str(layout.ruby_dir / "bin"), os.environ.get("PATH", "")]
            ),
        }
    )
    write_env(layout.env_file, env)

    # Tài liệu mồi: chỉ thêm tệp chưa có, không ghi đè tài liệu người dùng đã sửa/nạp.
    copy_missing(layout.app / "TC_DL", layout.source_dir)
    copy_missing(layout.app / "build" / "spike_a", layout.markdown_dir)
    layout.source_dir.mkdir(parents=True, exist_ok=True)
    layout.markdown_dir.mkdir(parents=True, exist_ok=True)

    install_deps(layout, env, force=args.force_deps)
    init_database(layout, env)

    if args.skip_ruby:
        print("  bỏ qua Ruby (--skip-ruby): upload .docx có công thức sẽ không trích được LaTeX.")
    else:
        ensure_ruby(layout, bundle, env, offline=args.offline)

    if not args.skip_models:
        print("Tải model (embedding, reranker, LLM)...")
        run(
            [
                layout.python_exe,
                "-m",
                "windows.launcher",
                "models",
                *(["--offline"] if args.offline else []),
            ],
            cwd=layout.app,
            env=env,
        )

    admin_user, admin_password = _ask_admin(args)
    print("Hoàn tất cơ sở dữ liệu, sổ tài liệu và chỉ mục...")
    run(
        [layout.python_exe, "-m", "windows.launcher", "setup"]
        + (["--skip-index"] if args.skip_index else []),
        cwd=layout.app,
        env={
            **env,
            "QTKD_ADMIN_USERNAME": admin_user,
            "QTKD_ADMIN_PASSWORD": admin_password,
        },
    )

    write_launchers(layout)
    if not args.no_shortcuts:
        install_shortcuts(layout, autostart=args.autostart)
    version = str(load_json(bundle / "manifest.json", {}).get("version") or INSTALL_VERSION)
    register_uninstall(layout, version)
    write_json(
        layout.data / "install.json",
        {
            "version": version,
            "root": str(layout.root),
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "admin_user": admin_user,
        },
    )

    url = f"http://{env['API_HOST']}:{env['API_PORT']}"
    print("\n✓ Cài đặt xong.")
    print(f"  Ứng dụng: {url}")
    print(f"  Tài khoản: {admin_user}")
    print(f"  Dữ liệu:  {layout.data}")
    print(f"  Log:      {layout.logs}")
    print("  Mở bằng shortcut 'QTKD RAG' trên Desktop/Start Menu.")
    print("  Dừng: nhấn Ctrl+C trong cửa sổ QTKĐ RAG.")
    open_now = args.start
    if not open_now and sys.stdin.isatty():
        open_now = input("Mở QTKĐ RAG ngay? [Y/n]: ").strip().lower() in ("", "y", "yes")
    if open_now and IS_WINDOWS:
        subprocess.Popen(["cmd", "/c", "start", "", "QTKD-RAG.bat"], cwd=root)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\n✗ Lệnh thất bại (mã {exc.returncode}): {' '.join(map(str, exc.cmd))}")
        print("  Xem log trong data\\logs rồi chạy lại CaiDat.bat.")
        sys.exit(1)
