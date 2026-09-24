#!/usr/bin/env python
"""Verification script for Sprint 0+1 database and auth setup."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODULE_CHECKS = [
    ("db.session", ["SessionLocal", "get_db", "engine"], "SQLAlchemy engine, session factory"),
    ("db.models", ["AppUser", "AuditLog", "UserRole", "Document"], "ORM models"),
    ("db.config", ["get_database_url"], "database URL builder"),
    (
        "auth.security",
        ["hash_password", "verify_password", "create_access_token", "decode_access_token"],
        "password + JWT",
    ),
    ("auth.dependencies", ["get_current_user", "require_role"], "FastAPI integration"),
    ("auth.utils", ["create_audit_log"], "audit logging"),
]


def check_imports() -> bool:
    """Verify all key modules and symbols can be imported."""
    print("Checking module imports...")

    all_ok = True
    for module_name, symbols, label in MODULE_CHECKS:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            print(f"  ✗ {module_name}: {exc}")
            all_ok = False
            continue

        missing = [name for name in symbols if not hasattr(module, name)]
        if missing:
            print(f"  ✗ {module_name} missing: {', '.join(missing)}")
            all_ok = False
        else:
            print(f"  ✓ {module_name} ({label})")

    return all_ok


def check_migrations() -> bool:
    """Verify migration files exist."""
    print("\nChecking migration files...")

    migrations_dir = ROOT / "db" / "migrations"

    required_files = [
        "env.py",
        "script.py.mako",
        "versions/001_create_auth_tables.py",
        "versions/002_create_document.py",
    ]

    all_exist = True
    for rel_path in required_files:
        file_path = migrations_dir / rel_path
        if file_path.exists():
            print(f"  ✓ {rel_path}")
        else:
            print(f"  ✗ {rel_path} not found")
            all_exist = False

    return all_exist


def check_scripts() -> bool:
    """Verify utility scripts exist and are executable."""
    print("\nChecking utility scripts...")

    scripts_dir = Path(__file__).parent

    required_scripts = [
        "migrate.py",
        "create_admin.py",
        "migrate_documents.py",
        "backup_db.sh",
        "restore_db.sh",
    ]

    all_exist = True
    for script in required_scripts:
        script_path = scripts_dir / script
        if script_path.exists():
            is_exec = os.access(script_path, os.X_OK)
            status = "✓" if is_exec else "⚠"
            print(f"  {status} {script} (executable: {is_exec})")
        else:
            print(f"  ✗ {script} not found")
            all_exist = False

    return all_exist


def check_env() -> bool:
    """Verify environment file exists."""
    print("\nChecking environment setup...")

    env_file = ROOT / ".env"
    env_example = ROOT / ".env.example"

    if env_file.exists():
        print("  ✓ .env exists")
    else:
        print("  ⚠ .env not found (copy from .env.example)")

    if env_example.exists():
        print("  ✓ .env.example exists")
    else:
        print("  ✗ .env.example not found")
        return False

    return True


def main() -> int:
    """Run all verification checks."""
    print("=" * 60)
    print("Sprint 0+1 Verification")
    print("=" * 60)
    print()

    checks = [
        ("Module Imports", check_imports),
        ("Migration Files", check_migrations),
        ("Utility Scripts", check_scripts),
        ("Environment Setup", check_env),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as exc:  # noqa: BLE001 - report any failure as a failed check
            print(f"  ✗ Error during check: {exc}")
            results.append((name, False))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    print()
    if all_passed:
        print("✓ All checks passed! Ready for testing.")
        return 0

    print("✗ Some checks failed. See details above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
