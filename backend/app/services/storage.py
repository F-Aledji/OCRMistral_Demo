# =============================================================================
# STORAGE SERVICE
# =============================================================================
# Kümmert sich um das Speichern und Laden von Dateien.
# Alle Dokumente werden unter backend/data/{document_id}/ gespeichert.
# =============================================================================

import os
import shutil
from uuid import UUID


# -----------------------------------------------------------------------------
# PFADE
# -----------------------------------------------------------------------------

# Basis-Pfad: backend/data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")


# -----------------------------------------------------------------------------
# HELPER FUNKTIONEN
# -----------------------------------------------------------------------------

def get_document_dir(doc_id: UUID) -> str:
    """
    Gibt den Ordner-Pfad für ein Dokument zurück.
    Erstellt den Ordner, falls er nicht existiert.
    
    Beispiel:
        get_document_dir("abc-123") → "/backend/data/abc-123/"
    """
    path = os.path.join(DATA_DIR, str(doc_id))
    os.makedirs(path, exist_ok=True)  # exist_ok=True: Kein Fehler wenn existiert
    return path


def save_original_pdf(doc_id: UUID, file_content: bytes) -> str:
    """
    Speichert das hochgeladene PDF als 'original.pdf'.
    
    Args:
        doc_id: UUID des Dokuments
        file_content: Bytes des PDF (kommt vom Upload)
    
    Returns:
        Pfad zur gespeicherten Datei
    """
    doc_dir = get_document_dir(doc_id)
    file_path = os.path.join(doc_dir, "original.pdf")
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    return file_path


def get_original_pdf_path(doc_id: UUID) -> str:
    """Gibt den Pfad zum Original-PDF zurück."""
    return os.path.join(DATA_DIR, str(doc_id), "original.pdf")


def save_annotated_pdf(doc_id: UUID, pdf_bytes: bytes) -> str:
    """
    Speichert das annotierte PDF (mit eingezeichneten Boxen).
    
    Args:
        doc_id: UUID des Dokuments
        pdf_bytes: Das bearbeitete PDF als Bytes
    
    Returns:
        Pfad zur gespeicherten Datei
    """
    doc_dir = get_document_dir(doc_id)
    file_path = os.path.join(doc_dir, "annotated.pdf")
    
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
    
    return file_path


def get_annotated_pdf_path(doc_id: UUID) -> str:
    """Gibt den Pfad zum annotierten PDF zurück."""
    return os.path.join(DATA_DIR, str(doc_id), "annotated.pdf")
