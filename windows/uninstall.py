"""Gỡ QTKĐ RAG bản Windows native.

Chạy từ Apps & features, hoặc:

    runtime\\python\\python.exe app\\windows\\uninstall.py --root "%LOCALAPPDATA%\\QTKD-RAG"

Mặc định giữ data/ (tài liệu, chỉ mục, CSDL) để cài lại không mất dữ liệu.
Thêm ``--remove-data`` để xoá sạch.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from windows.common import IS_WINDOWS, Layout, default_root, stop_postgres  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gỡ QTKĐ RAG")
    parser.add_argument("--root", default=str(default_root()))
    parser.add_argument("--yes", action="store_true", help="không hỏi xác nhận")
    parser.add_argument("--keep-data", action="store_true", help="giữ data/ (mặc định)")
    parser.add_argument("--remove-data", action="store_true", help="xoá cả data/")
    return parser.parse_args(argv)


def _remove_shortcuts() -> None:
    if not IS_WINDOWS:
        return
    appdata = Path(os.environ.get("APPDATA", ""))
    paths = [
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "QTKD RAG.lnk",
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "QTKD RAG.lnk",
        Path.home() / "Desktop" / "QTKD RAG.lnk",
    ]
    for path in paths:
        path.unlink(missing_ok=True)


def _remove_registry() -> None:
    if not IS_WINDOWS:
        return
    import winreg

    try:
        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\QTKD-RAG",
        )
    except OSError:
        pass


def _schedule_runtime_delete(runtime: Path) -> None:
    """Không xoá được python.exe đang chạy: hẹn cmd xoá sau khi tiến trình thoát."""
    if not runtime.is_dir():
        return
    script = Path(tempfile.gettempdir()) / f"qtkd-uninstall-{os.getpid()}.bat"
    script.write_text(
        f"@echo off\r\ntimeout /t 2 /nobreak >nul\r\nrmdir /s /q \"{runtime}\"\r\ndel \"%~f0\"\r\n",
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        close_fds=True,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    layout = Layout.at(args.root)
    if not layout.root.is_dir():
        print(f"Không thấy thư mục cài: {layout.root}")
        return 0

    remove_data = args.remove_data
    if not args.yes:
        print(f"Sẽ gỡ: {layout.root}")
        print(
            "Dữ liệu (tài liệu, chỉ mục, CSDL, công thức) "
            + ("SẼ BỊ XOÁ." if remove_data else "được GIỮ LẠI.")
        )
        answer = input("Tiếp tục? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Đã huỷ.")
            return 1

    print("Dừng Postgres...")
    stop_postgres(layout)

    print("Xoá shortcut và mục Apps & features...")
    _remove_shortcuts()
    _remove_registry()

    for name in ("app", "tools", "wheels", "models", "manifest.json"):
        path = layout.root / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    for name in ("QTKD-RAG.bat", "CaiDat.bat"):
        (layout.root / name).unlink(missing_ok=True)

    if remove_data:
        print("Xoá dữ liệu...")
        shutil.rmtree(layout.data, ignore_errors=True)
    else:
        print(f"Giữ dữ liệu tại: {layout.data}")

    _schedule_runtime_delete(layout.runtime)
    print("Đã gỡ. Thư mục runtime sẽ được xoá sau khi cửa sổ này đóng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
