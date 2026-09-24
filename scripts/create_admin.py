#!/usr/bin/env python
"""Create the first admin user for QTKĐ RAG system."""

import sys
from getpass import getpass
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth.security import hash_password
from db import SessionLocal
from db.models import AppUser, UserRole


def create_admin():
    """Create a new admin user."""
    db = SessionLocal()

    try:
        # Check if admin already exists
        existing_admin = db.query(AppUser).filter(AppUser.role == UserRole.ADMIN).first()
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

        password = getpass("Password: ")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters")
            sys.exit(1)

        password_confirm = getpass("Confirm Password: ")
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

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
