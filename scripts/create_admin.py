#!/usr/bin/env python
"""Create the first admin user for QTKĐ RAG system."""

import sys
from getpass import getpass
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth.dependencies import LOCAL_ADMIN_USERNAME
from auth.security import hash_password
from db import SessionLocal
from db.models import AppUser, UserRole


def create_admin():
    """Create a new admin user."""
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
            sys.exit(1)

        print("=== Create First Admin User ===\n")

        username = input("Username: ").strip()
        if not username:
            print("❌ Username cannot be empty")
            sys.exit(1)

        # Check if username already exists
        existing_user = db.query(AppUser).filter(AppUser.username == username).first()
        if existing_user:
            print(f"❌ Username '{username}' already exists")
            sys.exit(1)

        full_name = input("Full Name (optional): ").strip() or None

        # Nhập qua pipe từ PowerShell kết thúc dòng bằng CRLF; getpass chỉ bỏ "\n".
        password = getpass("Password: ").rstrip("\r")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters")
            sys.exit(1)

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
