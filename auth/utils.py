"""Authentication utilities."""
from typing import Optional, Any
from sqlalchemy.orm import Session
from db.models import AuditLog, AppUser


def create_audit_log(
    db: Session,
    actor: AppUser,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
) -> AuditLog:
    """
    Create an audit log entry.
    
    Args:
        db: Database session
        actor: User performing the action
        action: Action name (e.g., "upload", "delete", "approve")
        entity_type: Type of entity (e.g., "document", "extraction")
        entity_id: ID of the entity
        before: State before change (for modifications)
        after: State after change (for modifications)
    
    Returns:
        Created AuditLog object
    """
    log_entry = AuditLog(
        actor_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
