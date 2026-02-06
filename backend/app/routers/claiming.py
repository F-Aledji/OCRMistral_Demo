# =============================================================================
# ROUTER: CLAIMING
# =============================================================================
# POST /documents/{id}/claim   – Dokument sperren
# POST /documents/{id}/release – Dokument freigeben
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from datetime import datetime, timedelta
from uuid import UUID

from ..db import get_session
from ..db_models import Document

router = APIRouter(tags=["claiming"])


def is_claim_active(doc: Document) -> bool:
    """Prüft ob ein Dokument aktiv gesperrt ist."""
    if not doc.claimed_by_user_id:
        return False
    if not doc.claim_expires_at:
        return False
    return doc.claim_expires_at > datetime.now()


@router.post("/documents/{doc_id}/claim")
def claim_document(
    doc_id: UUID, 
    user_id: str = Query(..., description="Deine User-ID"),
    session: Session = Depends(get_session)
):
    """
    Sperrt ein Dokument für dich.
    Andere User können es dann 15 Minuten lang nicht bearbeiten.
    """
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Prüfen: Ist es bereits von jemand anderem gesperrt?
    if is_claim_active(doc) and doc.claimed_by_user_id != user_id:
        raise HTTPException(
            status_code=409, 
            detail=f"Dokument ist bereits von '{doc.claimed_by_user_id}' gesperrt"
        )
    
    # Sperre setzen
    doc.claimed_by_user_id = user_id
    doc.claim_expires_at = datetime.now() + timedelta(minutes=15)
    doc.updated_at = datetime.now()
    session.add(doc)
    session.commit()
    
    return {
        "status": "claimed",
        "user_id": user_id,
        "expires_at": doc.claim_expires_at.isoformat()
    }


@router.post("/documents/{doc_id}/release")
def release_document(
    doc_id: UUID,
    user_id: str = Query(..., description="Deine User-ID"),
    session: Session = Depends(get_session)
):
    """Gibt ein Dokument wieder frei."""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Nur der aktuelle Besitzer darf freigeben
    if doc.claimed_by_user_id == user_id:
        doc.claimed_by_user_id = None
        doc.claim_expires_at = None
        doc.updated_at = datetime.now()
        session.add(doc)
        session.commit()
    
    return {"status": "released"}
