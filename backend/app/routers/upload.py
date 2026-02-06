# =============================================================================
# ROUTER: UPLOAD
# =============================================================================
# POST /documents – Neues Dokument hochladen
# =============================================================================

from fastapi import APIRouter, Depends, UploadFile, File
from sqlmodel import Session

from ..db import get_session
from ..db_models import Document, DocumentFile, DocumentStatus, FileKind
from ..services import storage

router = APIRouter(tags=["upload"])


@router.post("/documents", response_model=Document)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    Lädt ein neues PDF hoch und erstellt einen Eintrag in der Warteschlange.
    
    Beispiel (mit curl):
        curl -X POST -F "file=@rechnung.pdf" http://localhost:8000/api/v1/documents
    """
    # 1. Dokument-Eintrag erstellen
    doc = Document(
        status=DocumentStatus.NEW,
        filename=file.filename
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    
    # 2. PDF speichern
    content = await file.read()
    path = storage.save_original_pdf(doc.id, content)
    
    # 3. Datei-Eintrag erstellen
    doc_file = DocumentFile(
        document_id=doc.id,
        kind=FileKind.ORIGINAL_PDF,
        path=path
    )
    session.add(doc_file)
    session.commit()
    
    return doc
