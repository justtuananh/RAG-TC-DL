"""Dựng gói cài Windows một lần (chạy được trên Windows hoặc Linux).

Kết quả là một thư mục tự chứa, mang sang máy đích rồi chạy ``CaiDat.bat``:

    <out>/
      app/            mã nguồn + frontend/dist + TC_DL + build/spike_a
      runtime/python/ CPython 3.12 portable
      tools/qdrant/   qdrant.exe (bản Windows)
      tools/postgres/ Postgres portable
      tools/ollama/   ollama.exe
      tools/installers/rubyinstaller.exe   (cài trên máy đích nếu chưa có)
      wheels/         toàn bộ wheel Python cho win_amd64/cp312
      manifest.json

Ví dụ:

    python windows/build_bundle.py
    python windows/build_bundle.py --out D:/QTKD-RAG --zip
    python windows/build_bundle.py --with-models   # chỉ trên Windows

Wheels tải trên Linux vẫn đúng cho Windows nhờ --platform win_amd64; model thì
để bộ cài tải ở lần cài đầu (mặc định).
"""

from __future__ import annotations

import argparse
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
    copy_tree,
    download,
    extract_tar_gz,
    extract_zip,
    http_ok,
    requirement_files,
    run,
    wait_for,
    write_json,
)

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "dist" / "cache"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dựng gói cài Windows cho QTKĐ RAG")
    parser.add_argument("--out", help="thư mục đầu ra (mặc định dist/QTKD-RAG-<ngày>)")
    parser.add_argument("--with-models", action="store_true", help="chép sẵn model (chỉ Windows)")
    parser.add_argument("--zip", action="store_true", help="nén thành .zip sau khi dựng")
    parser.add_argument("--skip-frontend", action="store_true", help="dùng frontend/dist có sẵn")
    parser.add_argument("--skip-wheels", action="store_true", help="giữ wheels/ đã có")
    parser.add_argument("--skip-downloads", action="store_true", help="dùng dist/cache, không tải")
    return parser.parse_args(argv)


def _version() -> str:
    stamp = time.strftime("%Y%m%d")
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "local"
    return f"{stamp}-{commit}"


def _cache_download(url: str, name: str, skip: bool) -> Path:
    dest = CACHE / name
    if skip:
        if not dest.is_file():
            raise SystemExit(f"--skip-downloads nhưng thiếu {dest}")
        return dest
    return download(url, dest)


def _build_frontend(out: Path, skip: bool) -> None:
    dist = REPO / "frontend" / "dist" / "index.html"
    if skip and not dist.is_file():
        raise SystemExit("--skip-frontend nhưng chưa có frontend/dist; chạy npm run build trước.")
    if not skip:
        npm = shutil.which("npm")
        if not npm:
            raise SystemExit("Không thấy npm; cài Node hoặc dùng --skip-frontend với dist có sẵn.")
        run([npm, "ci"], cwd=REPO / "frontend")
        run([npm, "run", "build"], cwd=REPO / "frontend")
    if not dist.is_file():
        raise SystemExit("frontend/dist/index.html không tồn tại sau khi build.")
    target = out / "app" / "frontend" / "dist"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(REPO / "frontend" / "dist", target)
    print(f"  frontend/dist ({sum(1 for _ in target.rglob('*'))} mục)")


def _python(out: Path, skip: bool) -> None:
    archive = _cache_download(
        components.PYTHON_URL, f"python-{components.PYTHON_VERSION}.tar.gz", skip
    )
    print("  giải nén Python...")
    extract_tar_gz(archive, out / "runtime" / "python", strip_top=True)
    exe = out / "runtime" / "python" / "python.exe"
    if not exe.is_file():
        raise SystemExit(f"Python giải nén không đúng: thiếu {exe}")


def _flatten_tool(root: Path, exe_name: str) -> None:
    """Đưa exe về đúng gốc tools/<tên>/ dù zip có thêm một thư mục bao."""
    if (root / exe_name).is_file():
        return
    matches = list(root.rglob(exe_name))
    if len(matches) != 1:
        raise SystemExit(f"Không xác định được {exe_name} trong {root} ({len(matches)} kết quả)")
    parent = matches[0].parent
    if parent == root:
        return
    for child in parent.iterdir():
        target = root / child.name
        if not target.exists():
            shutil.move(str(child), str(target))
    shutil.rmtree(parent, ignore_errors=True)


def _trim_postgres(root: Path) -> None:
    """Bỏ phần không cần cho server: pgAdmin, StackBuilder, tài liệu, header, symbols."""
    for name in ("pgAdmin 4", "StackBuilder", "doc", "include", "symbols"):
        shutil.rmtree(root / name, ignore_errors=True)


def _tools(out: Path, skip: bool) -> None:
    downloads = {
        "qdrant": (components.QDRANT_URL, f"qdrant-{components.QDRANT_VERSION}.zip"),
        "postgres": (components.POSTGRES_URL, f"postgres-{components.POSTGRES_VERSION}.zip"),
        "ollama": (components.OLLAMA_URL, f"ollama-{components.OLLAMA_VERSION}.zip"),
    }
    for name, (url, filename) in downloads.items():
        archive = _cache_download(url, filename, skip)
        print(f"  giải nén {name}...")
        extract_zip(archive, out / "tools" / name, strip_top=(name == "postgres"))
    _flatten_tool(out / "tools" / "qdrant", "qdrant.exe")
    _flatten_tool(out / "tools" / "ollama", "ollama.exe")
    _trim_postgres(out / "tools" / "postgres")

    ruby_installer = _cache_download(
        components.RUBY_URL, f"rubyinstaller-{components.RUBY_VERSION}.exe", skip
    )
    target = out / "tools" / "installers" / "rubyinstaller.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ruby_installer, target)


def _prepare_ruby(out: Path) -> None:
    """Chỉ làm được trên Windows: cài Ruby + gem vào gói để dùng offline sau này."""
    if not IS_WINDOWS:
        print("  Ruby: để bộ cài tự cài trên máy đích (cần Internet lần đầu).")
        return
    ruby = out / "tools" / "ruby" / "bin" / "ruby.exe"
    if not ruby.is_file():
        installer = out / "tools" / "installers" / "rubyinstaller.exe"
        print("  cài Ruby vào gói...")
        run(
            [
                installer,
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/DIR={out / 'tools' / 'ruby'}",
            ]
        )
    gem_env = {**os.environ, "GEM_HOME": str(out / "tools" / "ruby" / "gems")}
    gem = out / "tools" / "ruby" / "bin" / "gem"
    run(
        [
            ruby,
            gem,
            "install",
            "mathtype_to_mathml",
            "-v",
            components.MATTYPE_GEM_VERSION,
            "--no-document",
        ],
        env=gem_env,
    )
    run([ruby, gem, "install", "pry", "--no-document"], env=gem_env)
    print("  Ruby + gem đã sẵn trong gói.")


def _wheels(out: Path, skip: bool) -> None:
    wheels = out / "wheels"
    complete = wheels / ".complete"
    if skip and complete.is_file():
        print(f"  wheels: dùng {sum(1 for _ in wheels.glob('*.whl'))} wheel có sẵn.")
        return
    wheels.mkdir(parents=True, exist_ok=True)
    complete.unlink(missing_ok=True)
    requirements = requirement_files(REPO)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(wheels),
        "--only-binary=:all:",
        "--platform",
        "win_amd64",
        "--python-version",
        "3.12",
        "--implementation",
        "cp",
        "--abi",
        "cp312",
        "--extra-index-url",
        components.TORCH_INDEX_URL,
        *[str(path) for path in requirements],
    ]
    print("  tải wheels cho win_amd64/cp312 (có thể vài GB)...")
    run(cmd)
    count = sum(1 for _ in wheels.glob("*.whl"))
    size = sum(path.stat().st_size for path in wheels.glob("*.whl"))
    print(f"  {count} wheel, {size / 1024**3:.1f} GB")
    if count == 0:
        raise SystemExit("Không tải được wheel nào.")
    complete.write_text(f"{count} wheel\n", encoding="utf-8")


def _prefetch_models(out: Path) -> None:
    if not IS_WINDOWS:
        print("  --with-models cần chạy trên Windows; bỏ qua.")
        return
    python = out / "runtime" / "python" / "python.exe"
    run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(out / "wheels"),
            *[arg for path in requirement_files(out / "app") for arg in ("-r", str(path))],
        ],
        cwd=out / "app",
    )
    hf_home = out / "models" / "hf"
    env = {
        **os.environ,
        "HF_HOME": str(hf_home),
        "HF_HUB_OFFLINE": "0",
        "TRANSFORMERS_OFFLINE": "0",
        "PYTHONUTF8": "1",
    }
    run([python, "-m", "windows.models"], cwd=out / "app", env=env)

    ollama = out / "tools" / "ollama" / "ollama.exe"
    models = out / "models" / "ollama"
    models.mkdir(parents=True, exist_ok=True)
    # Cổng riêng để không đụng Ollama đang chạy trên máy build.
    ollama_env = {**os.environ, "OLLAMA_MODELS": str(models), "OLLAMA_HOST": "127.0.0.1:11435"}
    proc = subprocess.Popen(
        [str(ollama), "serve"],
        env=ollama_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(lambda: http_ok("http://127.0.0.1:11435/api/tags"), what="Ollama", timeout_s=120)
        run([ollama, "pull", components.OLLAMA_MODEL], env=ollama_env)
    finally:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.terminate()
        proc.wait(timeout=20)


def _launcher_bat(out: Path) -> None:
    (out / "CaiDat.bat").write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title Cai dat QTKD RAG\r\n"
        'set "PY=%~dp0runtime\\python\\python.exe"\r\n'
        'if not exist "%PY%" set "PY=python"\r\n'
        '"%PY%" "%~dp0app\\windows\\install.py" %*\r\n'
        "if errorlevel 1 pause\r\n",
        encoding="utf-8",
    )
    (out / "DOC-TRUOC.txt").write_text(
        "QTKD RAG - bản cài Windows\r\n"
        "================================\r\n\r\n"
        "1. Chép cả thư mục này sang máy đích (hoặc giải nén tệp zip).\r\n"
        "2. Nháy đúp CaiDat.bat và làm theo hướng dẫn.\r\n"
        "3. Lần cài đầu cần Internet để tải model (~9-10 GB) và Ruby/gem.\r\n"
        "   Muốn cài offline hoàn toàn: dựng gói bằng --with-models trên Windows,\r\n"
        "   và chép sẵn tools/ruby đã cài gem.\r\n"
        "4. Sau khi cài, mở shortcut 'QTKD RAG' trên Desktop.\r\n\r\n"
        "Dữ liệu nằm trong thư mục data\\, giữ lại khi cài lại/nâng cấp.\r\n"
        "Gỡ cài: Settings > Apps > QTKD RAG, hoặc chạy app\\windows\\uninstall.py.\r\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    version = _version()
    out = Path(args.out).resolve() if args.out else REPO / "dist" / f"QTKD-RAG-{version}"
    if out.is_relative_to(REPO) and not out.is_relative_to(REPO / "dist"):
        raise SystemExit("--out phải nằm ngoài repo hoặc trong thư mục dist/.")
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} đã có dữ liệu; chọn --out khác hoặc xoá thư mục đó.")
    out.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"Dựng gói: {out}")

    print("Chép mã nguồn...")
    copy_tree(
        REPO,
        out / "app",
        skip=(
            "dist",
            "documents",
            ".claude",
            ".github",
            ".impeccable",
            "design",
            "frontend-legacy",
            "kotaemon_ext",
        ),
    )
    build_dir = REPO / "build" / "spike_a"
    if build_dir.is_dir():
        copy_tree(build_dir, out / "app" / "build" / "spike_a")
    else:
        print("  CẢNH BÁO: chưa có build/spike_a; bộ cài sẽ không có Markdown mồi.")

    _build_frontend(out, skip=args.skip_frontend)
    _python(out, skip=args.skip_downloads)
    _tools(out, skip=args.skip_downloads)
    _prepare_ruby(out)
    if not args.skip_wheels:
        _wheels(out, skip=args.skip_downloads)
    if args.with_models:
        _prefetch_models(out)
    _launcher_bat(out)

    manifest = {
        "version": version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backend_commit": version.rsplit("-", 1)[-1],
        "tools_key": (
            f"{components.PYTHON_VERSION}|{components.QDRANT_VERSION}|"
            f"{components.POSTGRES_VERSION}|{components.OLLAMA_VERSION}|"
            f"{components.RUBY_VERSION}|torch-2.9.1-cu128"
        ),
        "python": components.PYTHON_VERSION,
        "qdrant": components.QDRANT_VERSION,
        "postgres": components.POSTGRES_VERSION,
        "ollama": components.OLLAMA_VERSION,
        "ruby": components.RUBY_VERSION,
        "image": "torch-2.9.1-cu128",
        "with_models": bool(args.with_models),
    }
    write_json(out / "manifest.json", manifest)
    print(f"\n✓ Xong: {out}")
    print("  Mang thư mục này sang máy Windows và chạy CaiDat.bat.")
    if args.zip:
        base = str(out) + "-windows-x64"
        print("  đang nén zip...")
        shutil.make_archive(base, "zip", root_dir=out.parent, base_dir=out.name)
        print(f"  zip: {base}.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
