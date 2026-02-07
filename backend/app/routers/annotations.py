# =============================================================================
# ROUTER: ANNOTATIONS
# =============================================================================
# GET /documents/{id}/annotations  – Annotationen abrufen
# PUT /documents/{id}/annotations  – Annotationen speichern
# POST /documents/{id}/artifacts/annotated-pdf – Annotiertes PDF erstellen
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import Dict, Any
from datetime import datetime
from uuid import UUID
import os

from ..db import get_session
from ..db_models import Document, DocumentFile, Annotation, FileKind
from ..services import storage, pdf_renderer
from ..schemas import AnnotationUpdate

router = APIRouter(tags=["annotations"])


@router.get("/documents/{doc_id}/annotations")
def get_annotations(doc_id: UUID, session: Session = Depends(get_session)):
    """
    Gibt die neueste Annotation für ein Dokument zurück.
    
    Rückgabe:
        {
            "version": 1,
            "fields": {
                "ba_number": {"value": "BA123", "bbox": {...}},
                "total": {"value": 1234.56, "bbox": {...}}
            }
        }
    """
    # Auch das Dokument laden, um die aktuelle Version zu haben (Source of Truth)
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    # Neueste Annotation laden
    query = select(Annotation).where(Annotation.document_id == doc_id).order_by(Annotation.version.desc())
    annotation = session.exec(query).first()
    
    if not annotation:
        return {"version": doc.version, "fields": {}}
    
    return {
        "version": doc.version,  # Immer Doc-Version nehmen (sollte gleich sein wie annot.version)
        "fields": annotation.fields,
        "source": annotation.source,
        "author": annotation.author_user_id
    }


@router.put("/documents/{doc_id}/annotations")
def update_annotations(
    doc_id: UUID,
    update: AnnotationUpdate,
    current_version: int = Query(..., description="Aktuelle Version (für Konflikt-Prüfung)"),
    user_id: str = Query(..., description="Deine User-ID"),
    session: Session = Depends(get_session)
):
    """
    Speichert neue Annotationen.
    
    Optimistic Locking:
        Der Client muss die aktuelle Version mitsenden.
        Falls jemand anderes in der Zwischenzeit gespeichert hat,
        gibt es einen 409 Conflict Error.
    """
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Version prüfen
    if doc.version != current_version:
        raise HTTPException(
            status_code=409,
            detail=f"Versionskonflikt! Du hast Version {current_version}, Server hat {doc.version}. "
                   "Bitte Seite neu laden."
        )
    
    # Neue Annotation erstellen
    new_annotation = Annotation(
        document_id=doc.id,
        author_user_id=user_id,
        source="user",
        fields=update.fields,
        version=doc.version + 1
    )
    session.add(new_annotation)
    
    # Document-Version erhöhen
    doc.version += 1
    doc.updated_at = datetime.now()
    session.add(doc)
    session.commit()
    
    return {
        "status": "saved",
        "new_version": doc.version
    }


@router.post("/documents/{doc_id}/artifacts/annotated-pdf")
def generate_annotated_pdf(doc_id: UUID, session: Session = Depends(get_session)):
    """
    Erzeugt ein PDF mit eingezeichneten Bounding Boxes (Burn-in).
    
    Returns:
        FileResponse mit dem annotierten PDF
    """
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Original-PDF laden
    original_path = storage.get_original_pdf_path(doc_id)
    if not os.path.exists(original_path):
        raise HTTPException(status_code=404, detail="Original-PDF nicht gefunden")
    
    # Neueste Annotationen holen
    query = (
        select(Annotation)
        .where(Annotation.document_id == doc_id)
        .order_by(Annotation.version.desc())
    )
    annotation = session.exec(query).first()
    
    if not annotation or not annotation.fields:
        raise HTTPException(status_code=400, detail="Keine Annotationen vorhanden")
    
    # PDF mit Annotationen rendern
    with open(original_path, "rb") as f:
        original_bytes = f.read()
    
    annotated_bytes = pdf_renderer.render_annotated_pdf(original_bytes, annotation.fields)
    
    # Speichern
    annotated_path = storage.save_annotated_pdf(doc_id, annotated_bytes)
    
    # Datei-Eintrag erstellen (falls noch nicht vorhanden)
    existing_file = session.exec(
        select(DocumentFile)
        .where(DocumentFile.document_id == doc_id)
        .where(DocumentFile.kind == FileKind.ANNOTATED_PDF)
    ).first()
    
    if not existing_file:
        doc_file = DocumentFile(
            document_id=doc_id,
            kind=FileKind.ANNOTATED_PDF,
            path=annotated_path
        )
        session.add(doc_file)
        session.commit()
    
    return FileResponse(
        annotated_path, 
        media_type="application/pdf",
        filename=f"annotated_{doc_id}.pdf"
    )
