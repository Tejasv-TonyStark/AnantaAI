from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import write_audit_log

router = APIRouter()


def agent_response(db: Session, user: User, resource: str, name: str) -> dict[str, str]:
    write_audit_log(db, user.id, "AI_AGENT_REQUEST", resource, "success")
    return {"message": f"{name} Agent placeholder", "access": "granted"}


@router.post("/rag/chat")
def rag_chat(user: User = Depends(require_permission("agent.rag.use")), db: Session = Depends(get_db)):
    return agent_response(db, user, "/agents/rag/chat", "Smriti RAG")


@router.post("/sql/query")
def sql_query(user: User = Depends(require_permission("agent.sql.use")), db: Session = Depends(get_db)):
    return agent_response(db, user, "/agents/sql/query", "SQL")


@router.post("/security/investigate")
def security_investigate(user: User = Depends(require_permission("agent.security.use")), db: Session = Depends(get_db)):
    return agent_response(db, user, "/agents/security/investigate", "Security")


@router.post("/cloud/analyze")
def cloud_analyze(user: User = Depends(require_permission("agent.cloud.use")), db: Session = Depends(get_db)):
    return agent_response(db, user, "/agents/cloud/analyze", "Cloud")
