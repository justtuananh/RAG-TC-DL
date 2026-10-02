"""Ghi audit_log và snapshot tài liệu cho các thao tác ghi."""

from __future__ import annotations

from sqlalchemy.orm import Session

from auth import create_audit_log
from db.models import AppUser


def record_audit(
    db: Session,
    user: AppUser,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Record a write operation in audit_log (design §5.6).

    In dev-without-auth mode get_current_user may return a lightweight mock that
    is not a persisted row; persisting an audit entry for it would violate the
    actor_id foreign key, so it is skipped. Real accounts are always recorded.
    """
    if not isinstance(user, AppUser):
        return
    create_audit_log(
        db=db,
        actor=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )


def document_snapshot(doc: dict) -> dict:
    """Minimal, JSON-safe snapshot of a document row for before/after audit."""
    return {k: doc.get(k) for k in ("id", "name", "ext", "size", "doc_type", "status", "sha256")}
