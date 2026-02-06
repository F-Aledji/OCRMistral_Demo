# =============================================================================
# ROUTER: PROCESSING
# =============================================================================
# POST /documents/{id}/process – OCR-Pipeline ausführen
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from datetime import datetime
from uuid import UUID
import os

from ..db import get_session
from ..db_models import Document, Annotation, DocumentStatus
from ..services import storage
from ..services.pipeline import get_pipeline_service

router = APIRouter(tags=["processing"])


@router.post("/documents/{doc_id}/process")
async def process_document(doc_id: UUID, session: Session = Depends(get_session)):
    """
    Führt die OCR-Pipeline auf einem Dokument aus.
    
    Dies macht:
    1. PDF einlesen
    2. OCR (Gemini)
    3. Pydantic-Validierung
    4. Score berechnen
    5. Annotations speichern
    6. Status aktualisieren
    
    Returns:
        {
            "success": bool,
            "score": int,
            "data": {...}
        }
    """
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    
    # Status: OCR läuft
    doc.status = DocumentStatus.OCR_RUNNING
    doc.updated_at = datetime.now()
    session.add(doc)
    session.commit()
    
    try:
        # PDF laden
        pdf_path = storage.get_original_pdf_path(doc_id)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF nicht gefunden")
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Pipeline ausführen
        pipeline = get_pipeline_service()
        result = pipeline.process_pdf(pdf_bytes)
        
        if not result.get("success"):
            # Fehler bei OCR
            doc.status = DocumentStatus.ERROR
            doc.updated_at = datetime.now()
            session.add(doc)
            session.commit()
            raise HTTPException(status_code=500, detail=result.get("error", "OCR fehlgeschlagen"))
        
        # Erfolg: Daten speichern
        doc.score = result.get("score", 0)
        
        # BA-Nummer aus Annotations extrahieren
        annotations = result.get("annotations", {})
        if "ba_number" in annotations:
            doc.ba_number = annotations["ba_number"].get("value")
        if "vendor_name" in annotations:
            doc.vendor_name = annotations["vendor_name"].get("value")
        if "total_value" in annotations:
            try:
                doc.total_value = float(annotations["total_value"].get("value", 0))
            except:
                pass
        
        # Status basierend auf Score setzen
        if doc.score and doc.score >= 85:
            doc.status = DocumentStatus.VALID
        elif doc.score and doc.score >= 70:
            doc.status = DocumentStatus.OCR_DONE
        else:
            doc.status = DocumentStatus.NEEDS_REVIEW
        
        doc.version += 1
        doc.updated_at = datetime.now()
        session.add(doc)
        
        # Annotations speichern
        if annotations:
            annotation = Annotation(
                document_id=doc.id,
                author_user_id="system",
                source="ocr",
                fields=annotations,
                version=doc.version
            )
            session.add(annotation)
        
        session.commit()
        
        return {
            "success": True,
            "score": result.get("score"),
            "status": doc.status.value,
            "data": result.get("data"),
            "annotations": annotations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        doc.status = DocumentStatus.ERROR
        doc.updated_at = datetime.now()
        session.add(doc)
        session.commit()
        raise HTTPException(status_code=500, detail=str(e))
