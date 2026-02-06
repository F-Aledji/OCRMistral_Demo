# =============================================================================
# ROUTER: QUEUE
# =============================================================================
# GET /documents       – Liste aller Dokumente  
# GET /documents/{id}  – Einzelnes Dokument
# GET /documents/{id}/file – PDF Download
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select, or_
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import os

from ..db import get_session
from ..db_models import Document, DocumentStatus
from ..services import storage

router = APIRouter(tags=["queue"])


@router.get("/documents", response_model=List[Document])
def list_documents(
    status: Optional[DocumentStatus] = Query(None, description="Filter nach Status"),
    claimed: Optional[bool] = Query(None, description="True=nur belegte, False=nur freie"),
    session: Session = Depends(get_session)
):
    """
    Gibt die Warteschlange zurück.
    
    Beispiele:
        GET /documents                    → Alle Dokumente
        GET /documents?status=NEEDS_REVIEW → Nur die, die geprüft werden müssen
        GET /documents?claimed=false      → Nur freie Dokumente
    """
    query = select(Document).order_by(Document.created_at.desc())
    
    # Filter: Status
    if status:
        query = query.where(Document.status == status)
    
    # Filter: Claimed
    now = datetime.now()
    if claimed is True:
        query = query.where(Document.claimed_by_user_id != None)
        query = query.where(Document.claim_expires_at > now)
    elif claimed is False:
        query = query.where(
            or_(
                Document.claimed_by_user_id == None,
                Document.claim_expires_at <= now
            )
        )
    
    return session.exec(query).all()


@router.get("/documents/{doc_id}", response_model=Document)
def get_document(doc_id: UUID, session: Session = Depends(get_session)):
    """Gibt ein einzelnes Dokument zurück."""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return doc


@router.get("/documents/{doc_id}/file")
def get_document_file(doc_id: UUID, session: Session = Depends(get_session)):
    """Gibt das Original-PDF zum Download zurück."""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    path = storage.get_original_pdf_path(doc_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF-Datei nicht gefunden")
    
    return FileResponse(path, media_type="application/pdf")
