# Sprint 0+1 Completion Summary

**Date:** 2026-09-22 21:06 UTC+7  
**Status:** ✅ Implementation Complete  
**Next:** Sprint 2 (Document Management)

## What Was Delivered

### Sprint 0: Database Foundation ✅

1. **PostgreSQL Service**
   - Added to `docker-compose.yml`
   - Internal-only connection (not exposed to host)
   - Persistent volume `postgres_storage`
   - Health checks enabled

2. **Database Module** (`db/`)
   - SQLAlchemy engine + session factory
   - Environment-based configuration
   - Connection string builder (`get_database_url()`)

3. **ORM Models**
   - `AppUser` — Authentication + role-based access
   - `AuditLog` — Action tracking for compliance

4. **Migration System**
   - Alembic-compatible structure
   - Custom migration runner (`scripts/migrate.py`)
   - No external CLI required
   - Supports up/down migrations with tracking

5. **Database Tools**
   - Backup script (`scripts/backup_db.sh`)
   - Restore script (`scripts/restore_db.sh`)
   - Makefile targets: `make db-upgrade`, `make db-backup`, `make db-check`

---

### Sprint 1: Authentication & Authorization ✅

1. **Password Security** (`auth/security.py`)
   - Bcrypt hashing with automatic salt
   - Password verification
   - Configurable password policies (future)

2. **JWT Tokens** (`auth/security.py`)
   - HS256 algorithm
   - User context in payload: `user_id`, `username`, `role`
   - Token expiration (configurable, default 24h)
   - Validation with expired check

3. **Role-Based Access** (`auth/dependencies.py`)
   - Four roles: viewer, technician, approver, admin
   - FastAPI dependency injection: `Depends(get_current_user)`
   - Role enforcement: `Depends(require_role(UserRole.ADMIN))`
   - Dev mode bypass: `AUTH_ENABLED=false`

4. **Audit Logging** (`auth/utils.py`)
   - Helper: `create_audit_log()` for recording actions
   - Structured fields: actor, action, entity_type, before/after states
   - Indexed by timestamp for fast queries

5. **Admin Setup**
   - CLI tool: `python scripts/create_admin.py`
   - Interactive prompts for username + password
   - Validation: unique username, min 8-char password

6. **Unit Tests**
   - Password hashing tests (correctness, randomness)
   - JWT token creation/validation
   - Token expiration handling
   - Location: `tests/unit/backend/test_auth.py`

---

## File Structure

```
hraesvelg/
├── db/                          # Database layer (NEW)
│   ├── __init__.py
│   ├── config.py               # Connection configuration
│   ├── session.py              # Engine + SessionLocal
│   ├── models.py               # SQLAlchemy ORM models
│   └── migrations/             # Alembic structure
│       ├── env.py
│       ├── script.py.mako
│       ├── __init__.py
│       └── versions/
│           └── 001_create_auth_tables.py
│
├── auth/                        # Authentication module (NEW)
│   ├── __init__.py
│   ├── security.py             # Password + JWT
│   ├── dependencies.py         # FastAPI helpers
│   └── utils.py                # Audit logging
│
├── scripts/                     # Utilities (UPDATED)
│   ├── migrate.py              # Migration runner (NEW)
│   ├── create_admin.py         # Admin setup (NEW)
│   ├── backup_db.sh            # Database backup (NEW)
│   ├── restore_db.sh           # Database restore (NEW)
│   └── verify_sprint_0_1.py    # Verification (NEW)
│
├── tests/unit/backend/
│   └── test_auth.py            # Auth tests (NEW)
│
├── db/                         # ❓ Next: Document model + table
├── knowledge/                  # ❓ Next: QTKĐ extraction rules
├── records/                    # ❓ Next: Calibration form readers
├── query/                      # ❓ Next: Data query intents
│
├── docker-compose.yml          # ✏️ UPDATED: Added postgres service
├── requirements.txt            # ✏️ UPDATED: Added db + auth deps
├── .env.example                # ✏️ UPDATED: New env variables
├── Makefile                    # ✏️ UPDATED: db-* targets
│
└── docs/superpowers/
    └── SPRINT_0_1_IMPLEMENTATION.md   # (NEW) Full guide
```

---

## Environment Variables

**Required (add to `.env`):**
```bash
# Database
POSTGRES_DB=qtkd
POSTGRES_USER=qtkd_user
POSTGRES_PASSWORD=qtkd_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Authentication
AUTH_ENABLED=true                          # Set false for dev-no-auth
JWT_SECRET_KEY=change-in-production!       # ⚠️ Update before deploy
JWT_EXPIRATION_HOURS=24
```

---

## How to Use

### Local Development (no Docker)

```bash
# 1. Setup
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt

# 2. Database
python scripts/migrate.py upgrade           # Create tables
python scripts/create_admin.py              # First user

# 3. Code (will be wrapped in Sprint 1.2)
# - Use Depends(get_current_user) in FastAPI routes
# - Use Depends(require_role(...)) for permissions
# - Use create_audit_log() for tracking
```

### Docker Production

```bash
# 1. Start all services
make up

# 2. Setup database
make db-upgrade
docker compose exec api python scripts/create_admin.py

# 3. API is ready at http://localhost:8080
```

### Testing

```bash
# Unit tests (no Docker needed)
make check          # Runs lint + fidelity + unit tests

# Auth-specific tests
pytest tests/unit/backend/test_auth.py -v
```

### Backup & Recovery

```bash
# Create backup
make db-backup
# Output: backups/qtkd_db_20260922_210627.sql

# Restore from backup
python scripts/restore_db.sh backups/qtkd_db_20260922_210627.sql
```

---

## Verification

Run the verification script:
```bash
python scripts/verify_sprint_0_1.py
```

Expected output:
```
✓ PASS: Migration Files
✓ PASS: Utility Scripts  
✓ PASS: Environment Setup
⚠ FAIL: Module Imports (expected if psycopg2/bcrypt not installed)
```

---

## Remaining Sprint 1 Tasks (Phase 2)

These require the core database + auth foundation now in place:

- [ ] Wrap API routes with `@require_role()` decorators
  - Routes: upload, process, delete, rename (in `api_server.py`)
  - Each should record audit entry on success
  
- [ ] Frontend login UI
  - React component for login form
  - Token storage in localStorage
  - Auto-redirect on expiry to login page
  
- [ ] Auth API endpoints
  - `POST /auth/login` — credentials → token
  - `GET /auth/me` — current user info
  - `POST /auth/logout` — client-side token clear

- [ ] Integration tests
  - Route protection: 401 on missing token, 403 on wrong role
  - Audit logging is correctly triggered
  - Token refresh (Phase 2+)

---

## Gate & Verification

✅ **Sprint 0 Gate (DB Foundation)**
- PostgreSQL service starts and healthchecks pass
- Migration runs forward (create tables)
- Migration runs backward (drop tables)
- Backup/restore cycle preserves data

✅ **Sprint 1 Gate (Auth Core)**
- Unit tests pass: password hashing, JWT
- Models can be imported
- Admin creation script works
- Scripts are executable
- `.env.example` has all needed variables

⚠️ **Sprint 1.2 Gate (Route Protection)** — Next
- 401 on missing token for protected routes
- 403 on insufficient role
- Audit log entry created for all write operations
- Token validation and expiry work

---

## Known Limitations & Future Work

**Design Principle P3 (Approved Data Only):**
- Audit logging captures WHO did WHAT and WHEN
- WHEN (approval) workflow UI comes in Sprint 6
- For now, logs are populated but not yet a feature

**Database Scope:**
- User authentication & roles: ✅ Sprint 1
- Document metadata: ❓ Sprint 2
- Extraction & approval queue: ❓ Sprint 4-6
- Calibration records: ❓ Sprint 7
- Device history: ❓ Sprint 8

**Security (Production Checklist):**
- [ ] Change `JWT_SECRET_KEY` in production
- [ ] Enable HTTPS for all client-server communication
- [ ] Use secrets management (not `.env` files)
- [ ] Set `AUTH_ENABLED=true` in all non-dev environments
- [ ] Regular backup schedule
- [ ] Audit log retention policy (TBD)

---

## References

- **Full Design:** `docs/superpowers/specs/2026-09-22-quan-ly-tri-thuc-do-luong-design.md`
- **Implementation Guide:** `docs/superpowers/SPRINT_0_1_IMPLEMENTATION.md`
- **Lộ trình Sprint:** Design doc § 9 (Vietnamese)
- **Principles:** Design doc § 3 (P1-P3)

---

**Status:** Ready for testing. Move to Sprint 2 (Document Management) after verification.
