#!/usr/bin/env python
"""Create the first admin user for QTKĐ RAG system.

Chạy tương tác:      python scripts/create_admin.py
Bộ cài Windows:      python scripts/create_admin.py --username admin --password-stdin --if-missing
"""

from __future__ import annotations

import argparse
import sys
from getpass import getpass
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth.dependencies import LOCAL_ADMIN_USERNAME
from auth.security import hash_password
from db import SessionLocal
from db.models import AppUser, UserRole


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo tài khoản quản trị đầu tiên")
    parser.add_argument("--username", help="tên đăng nhập (bỏ trống để hỏi)")
    parser.add_argument("--full-name", help="họ tên hiển thị")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="đọc mật khẩu từ stdin thay vì hỏi (dùng cho bộ cài tự động)",
    )
    parser.add_argument(
        "--if-missing",
        action="store_true",
        help="thoát 0 nếu đã có quản trị viên (bộ cài chạy lại an toàn)",
    )
    return parser.parse_args(argv)


def _read_password(use_stdin: bool) -> str:
    if use_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    # Nhập qua pipe từ PowerShell kết thúc dòng bằng CRLF; getpass chỉ bỏ LF.
    return getpass("Password: ").rstrip("\r")


def create_admin(args: argparse.Namespace | None = None) -> None:
    """Create a new admin user."""
    args = args or _parse_args()
    db = SessionLocal()

    try:
        # Check if admin already exists
        # Tài khoản `local` (tự tạo khi tắt đăng nhập) không đăng nhập được nên không tính.
        existing_admin = (
            db.query(AppUser)
            .filter(AppUser.role == UserRole.ADMIN, AppUser.username != LOCAL_ADMIN_USERNAME)
            .first()
        )
        if existing_admin:
            print(f"❌ Admin user already exists: {existing_admin.username}")
            if args.if_missing:
                return
            sys.exit(1)

        print("=== Create First Admin User ===\n")

        username = (args.username or input("Username: ")).strip()
        if not username:
            print("❌ Username cannot be empty")
            sys.exit(1)

        # Check if username already exists
        existing_user = db.query(AppUser).filter(AppUser.username == username).first()
        if existing_user:
            print(f"❌ Username '{username}' already exists")
            sys.exit(1)

        full_name = args.full_name
        if full_name is None:
            # Không hỏi khi đã có --username: bộ cài chạy không tương tác.
            full_name = None if args.username else input("Full Name (optional): ")
        full_name = full_name.strip() or None

        password = _read_password(args.password_stdin)
        if len(password) < 8:
            print("❌ Password must be at least 8 characters")
            sys.exit(1)

        if not args.password_stdin:
            password_confirm = getpass("Confirm Password: ").rstrip("\r")
            if password != password_confirm:
                print("❌ Passwords do not match")
                sys.exit(1)

        # Create user
        user = AppUser(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print("\n✓ Admin user created successfully!")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Full Name: {user.full_name or '(none)'}")
        print(f"  Role: {user.role.value}")

    except UnicodeDecodeError:
        # Bộ gõ tiếng Việt (Unikey/EVKey) gửi phím vào terminal docker exec theo bảng mã của Windows, không phải UTF-8.
        print(
            "❌ Không đọc được ký tự vừa gõ (không phải UTF-8).\n"
            "   Tắt bộ gõ tiếng Việt (chuyển Unikey/EVKey sang E) rồi chạy lại, hoặc nhập qua stdin:\n"
            "   \"admin`n`n<mật khẩu>`n<mật khẩu>`n\" | docker compose exec -T api python scripts/create_admin.py"
        )
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
