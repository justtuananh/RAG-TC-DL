# Sprint 0 + 1 Implementation Guide

## Overview

**Sprint 0** establishes PostgreSQL foundation without affecting current chat operations.
**Sprint 1** implements user authentication and audit logging for all write operations.

## Sprint 0 Completion Checklist

### ✅ Database Service Setup
- PostgreSQL added to `docker-compose.yml`
  - Service name: `postgres`
  - Internal port: 5432 (not exposed to host)
  - Persistent volume: `postgres_storage`
  - Health check: `pg_isready`
- Environment variables in `.env.example`:
  - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
  - Alternative: `DATABASE_URL` (full connection string)

### ✅ Database Module (`db/`)
```
db/
├── __init__.py          # Package exports
├── config.py            # Connection URL configuration
├── session.py           # SQLAlchemy engine and session factory
├── models.py            # ORM models (AppUser, AuditLog, etc.)
└── migrations/
    ├── env.py           # Alembic environment
    ├── script.py.mako   # Migration template
    ├── __init__.py
    └── versions/
        └── 001_create_auth_tables.py  # Initial migration
```

**Key Functions:**
- `db.config.get_database_url()` - Builds connection URL from env vars
- `db.session.SessionLocal` - Session factory for routes
- `db.session.get_db()` - FastAPI dependency

### ✅ Alembic Migration System
- Manual migration files in `db/migrations/versions/`
- Simple migration runner: `scripts/migrate.py`
  - Does NOT require Alembic CLI to be installed
  - Handles up/down migrations
  - Tracks applied migrations in `schema_migrations` table

**Migration Files:**
- Named: `NNN_description.py` (e.g., `001_create_auth_tables.py`)
- Must have `upgrade()` and `downgrade()` functions
- Use SQLAlchemy `text()` for raw SQL

### ✅ Database Backup Scripts
- `scripts/backup_db.sh` - Creates timestamped SQL dumps
  - Keeps last 10 backups automatically
  - Output: `backups/qtkd_db_YYYYMMDD_HHMMSS.sql`
- `scripts/restore_db.sh` - Restores from backup
  - Validates backup file exists
  - Requires confirmation prompt
  - Swaps databases atomically

### ✅ Makefile Targets
```bash
make db-upgrade      # Run all pending migrations
make db-downgrade    # Revert all migrations
make db-backup       # Create timestamped backup
make db-check        # Test migrations forward/backward on fresh DB
```

---

## Sprint 1 Implementation

### ✅ Authentication Module (`auth/`)
```
auth/
├── __init__.py          # Package exports
├── security.py          # Password hashing, JWT tokens
├── dependencies.py      # FastAPI auth dependencies
└── utils.py            # Audit logging helpers
```

**Password Hashing:**
- Uses bcrypt with automatic salt generation
- `hash_password(password: str) -> str`
- `verify_password(plain: str, hashed: str) -> bool`

**JWT Tokens:**
- Algorithm: HS256
- Payload: `user_id`, `username`, `role`, `exp`
- Duration: `JWT_EXPIRATION_HOURS` (default 24)
- Secret: `JWT_SECRET_KEY` (⚠️ change in production!)
- Functions:
  - `create_access_token(user_id, username, role) -> str`
  - `decode_access_token(token) -> Optional[TokenPayload]`

### ✅ Database Models
Created in `db/models.py`:

**AppUser:**
```python
id              # Primary key
username        # Unique identifier
full_name       # Optional display name
password_hash   # Bcrypt hash
role            # Enum: viewer, technician, approver, admin
is_active       # Soft-delete flag
created_at      # Registration timestamp
```

**AuditLog:**
```python
id              # Primary key
actor_id        # Foreign key to AppUser
action          # "upload", "delete", "approve", etc.
entity_type     # "document", "extraction", "user", etc.
entity_id       # Reference to affected entity
before          # JSON state before change
after           # JSON state after change
at              # Timestamp (indexed)
```

### ✅ User Roles & Permissions Matrix

| Role | Upload | Process | Delete | Rename | Approve | Admin |
|------|--------|---------|--------|--------|---------|-------|
| Viewer | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Technician | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Approver | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### ✅ Admin User Creation

**Initial Setup:**
```bash
python scripts/create_admin.py
```

Interactive prompt:
- Username (required, unique)
- Full Name (optional)
- Password (min 8 chars, confirmed)

### ✅ Auth Configuration

**Environment Variables:**
```bash
# Enable/disable authentication
AUTH_ENABLED=true          # Set to false for dev-without-auth mode

# JWT settings
JWT_SECRET_KEY=prod-secret-here  # ⚠️ Change this!
JWT_EXPIRATION_HOURS=24
```

**Dev Mode (Auth Disabled):**
- `AUTH_ENABLED=false` bypasses token checks
- Useful for local frontend development
- Always enabled in Docker production

### ✅ Dependency Injection

**FastAPI Integration:**
```python
from auth import get_current_user, require_role
from db.models import UserRole, AppUser

# Get current authenticated user
@app.get("/me")
async def get_profile(user: AppUser = Depends(get_current_user)):
    return {"username": user.username, "role": user.role}

# Require specific role
@app.delete("/documents/{id}")
async def delete_doc(
    id: str,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN))
):
    # Delete logic...
    return {"deleted": True}
```

### ✅ Audit Logging

**Manual Logging:**
```python
from auth import create_audit_log

create_audit_log(
    db=session,
    actor=current_user,
    action="upload",
    entity_type="document",
    entity_id=doc_id,
    after={"file_name": "test.docx", "size": 12345}
)
```

---

## Testing

### Unit Tests
Location: `tests/unit/backend/test_auth.py`

**Coverage:**
- Password hashing (correct, wrong, different salts)
- JWT token creation and validation
- Token expiration handling

Run:
```bash
make check      # Runs lint + fidelity + unit tests
pytest tests/unit/backend/test_auth.py -v
```

### Integration Tests (Sprint 1 scope incomplete)
- Auth route protection (401 on missing token, 403 on wrong role)
- Audit log creation for all write operations
- Token refresh mechanics

---

## Environment Setup

### Local Development (No Docker)

1. Create `.env` from template:
```bash
cp .env.example .env
# Edit .env: set POSTGRES_HOST=localhost, AUTH_ENABLED=false for dev
```

2. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Run migrations:
```bash
python scripts/migrate.py upgrade
```

4. Create admin user:
```bash
python scripts/create_admin.py
```

### Docker Production

1. Compose services start automatically:
```bash
make up
```

2. Migrations run at container startup (TBD: add init script to api service)

3. Create admin via container:
```bash
docker compose exec api python scripts/create_admin.py
```

---

## Database Lifecycle

### First Time Setup
```bash
make up                          # Start postgres + services
make db-upgrade                  # Run migrations (creates tables)
python scripts/create_admin.py   # Create first user
```

### Regular Maintenance
```bash
make db-backup                   # Periodic backup
make db-check                    # Verify migrations are sound
```

### Data Recovery
```bash
ls backups/                                  # Find backup
python scripts/restore_db.sh backups/...sql  # Restore (with confirmation)
```

### Clean Reset (dev only!)
```bash
docker compose down -v           # Wipe all volumes
make up && make db-upgrade       # Start fresh
```

---

## Remaining Sprint 1 Tasks

### ✅ Route Protection (backend)
- Wrapped `api_server.py` write routes with `require_role()` dependency
- Routes affected: upload, process, delete, rename
- Each records an audit entry on success (`upload`, `process`, `delete`, `rename`)
- Covered by `tests/unit/backend/test_auth_routes.py` (401 no token / 403 wrong role / audit actor)

### ✅ API Endpoints (backend)
- `POST /api/auth/login` — username + password → token
- `POST /api/auth/logout` — authenticated, 204 (client discards token)
- `GET /api/auth/me` — current user info + role
- `POST /api/auth/refresh` — issue a fresh token for the current user

### ✅ Frontend Login (Sprint 1 complete)
- `services/auth.ts` — token localStorage (`qtkd.auth.token`), giải mã JWT (payload), kiểm hạn,
  `canWrite(role)`, `authFetch` (gắn `Authorization: Bearer`), API `login/logout/me/refresh`,
  và tín hiệu 401 toàn cục (`subscribeUnauthorized`).
- `components/modals/LoginModal.tsx` — form đăng nhập (username + password) theo đúng kiểu modal sẵn có.
- `components/layout/AccountMenu.tsx` — nút tài khoản trên TopBar: "Đăng nhập" hoặc tên + vai trò + "Đăng xuất".
- Token storage: localStorage `qtkd.auth.token`; khôi phục phiên khi mount qua `GET /api/auth/me`.
- Attach `Authorization: Bearer` cho route ghi + `/api/auth/me` + `/api/auth/refresh`; route đọc/chat
  (`/api/documents`, markdown, file, chat, examples, health) vẫn gọi `fetch` thường → khách xem được.
- Xử lý 401/hết hạn: request ghi gặp 401 → xoá token + mở màn hình đăng nhập; thao tác ghi đang chờ
  được chạy lại sau khi đăng nhập. Token hết hạn lúc tải trang bị xoá im lặng (không bắt khách đăng nhập).
- Phân quyền: `viewer`/`approver` bị chặn tại UI (toast) trước khi gọi backend; `technician`/`admin` đi tiếp.
- Test: `services/auth.test.ts` (21 test) + `services/liveApi.test.ts` (bearer cho route ghi, đọc không token).

> Ghi chú: app là SPA không dùng router, nên "chuyển hướng khi hết hạn" được hiện thực bằng
> `LoginModal` (overlay) thay vì route `/login` — đúng kiến trúc hiện có, không phá UI.

### ✅ Documentation
- Auth setup guide (this file)
- Frontend integration guide (mục Frontend Login ở trên)
- Troubleshooting auth issues (xem dưới)

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'bcrypt'"**
- Install dev dependencies: `pip install -r requirements.txt -r requirements-dev.txt`

**"pg: could not translate host name"**
- Ensure `POSTGRES_HOST` is correct (localhost for local, postgres for Docker)

**"FATAL: password authentication failed"**
- Check `POSTGRES_PASSWORD` matches in `.env` and docker-compose

**"User authentication bypass in dev"**
- Set `AUTH_ENABLED=false` in `.env` (then FastAPI won't require token)

**"Token expired immediately"**
- Verify `JWT_SECRET_KEY` is consistent (token signed with one key, verified with another causes failure)

---

## Next Steps (Future Sprints)

- **Sprint 2:** Document management (replace filesystem with DB records)
- **Sprint 3:** Semantic framework (quantities, units, procedures)
- **Sprint 4:** Rule-based extraction (QTKĐ §1-7)
- **Sprint 5:** LLM-assisted extraction (§6 limits)
- **Sprint 6:** Approval workflow UI
- **Sprint 7:** Record reader for calibration forms
- **Sprint 8:** Data query and device history
- **Sprint 9:** Hybrid chat (text + numerical queries)

---

## References

- **Design Spec:** `docs/superpowers/specs/2026-09-22-quan-ly-tri-thuc-do-luong-design.md`
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/
- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/
- **Bcrypt Python:** https://github.com/pyca/bcrypt
- **JWT.io:** https://jwt.io/
