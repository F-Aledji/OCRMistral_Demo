# =============================================================================
# PYTEST FIXTURES
# =============================================================================
# Gemeinsame Test-Fixtures für alle Tests
# =============================================================================

import pytest
import os
import sys
from pathlib import Path

# Projekt-Root zu sys.path hinzufügen
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# -----------------------------------------------------------------------------
# SAMPLE PDF FIXTURE
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_pdf_bytes():
    """Minimales gültiges PDF für Tests."""
    # Einfachstes gültiges PDF (1 leere Seite)
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""


@pytest.fixture
def corrupted_pdf_bytes():
    """Korrupte Datei (keine gültige PDF-Signatur)."""
    return b"This is not a valid PDF file"


@pytest.fixture
def encrypted_pdf_bytes():
    """Simuliert ein verschlüsseltes PDF (enthält /Encrypt)."""
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Encrypt /V 1 >>
endobj
xref
0 3
trailer
<< /Root 1 0 R /Encrypt 2 0 R >>
startxref
100
%%EOF"""


# -----------------------------------------------------------------------------
# OCR RESULT FIXTURES
# -----------------------------------------------------------------------------

@pytest.fixture
def valid_ocr_result():
    """Gültiges OCR-Ergebnis für Score-Tests."""
    return {
        "documents": [{
            "SupplierConfirmation": {
                "Correspondence": {
                    "number": "BA-12345",
                    "bbox": {"x0": 100, "y0": 100, "x1": 200, "y1": 120}
                },
                "supplierConfirmationData": {
                    "salesConfirmation": "ABC-2024-001",
                    "date": {"value": "15.01.2026"},
                    "documentType": "Auftragsbestätigung"
                },
                "invoiceSupplierData": {
                    "SupplierPartner": {
                        "number": 12345
                    }
                },
                "documentNetTotal": 1234.56,
                "positions": {
                    "Details": [{
                        "number": 10,
                        "totalQuantity": {"amount": 5, "Uom": {"code": "Stk"}},
                        "grossPrice": {"amount": 100.0, "Currency": {"isoCode": "EUR"}},
                        "netValue": 500.0,
                        "deliveryDate": {"date": "20.01.2026", "specialValue": "NONE"}
                    }]
                },
                "reasoning": "Das Dokument wurde vollständig erkannt."
            }
        }]
    }


@pytest.fixture
def incomplete_ocr_result():
    """OCR-Ergebnis ohne BA-Nummer (für Penalty-Tests)."""
    return {
        "documents": [{
            "SupplierConfirmation": {
                "Correspondence": {
                    "number": None
                },
                "supplierConfirmationData": {
                    "date": {"value": "15.01.2026"},
                    "documentType": "Auftragsbestätigung"
                },
                "invoiceSupplierData": {
                    "SupplierPartner": {"number": 0}
                },
                "documentNetTotal": 0
            }
        }]
    }


# -----------------------------------------------------------------------------
# TEMP DIRECTORY FIXTURE
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_dir(tmp_path):
    """Temporäres Verzeichnis für Datei-Tests."""
    return tmp_path


# -----------------------------------------------------------------------------
# DATABASE FIXTURE (In-Memory)
# -----------------------------------------------------------------------------

@pytest.fixture
def session():
    """Erzeugt eine isolierte In-Memory-Datenbank für Tests."""
    from sqlmodel import Session, create_engine, SQLModel
    from sqlmodel.pool import StaticPool
    from backend.app.db import get_session
    from backend.app.main import app

    # In-Memory SQLite mit StaticPool (damit Threads dieselbe DB sehen)
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    
    # Tabellen erstellen
    SQLModel.metadata.create_all(engine)
    
    # Session und Dependency Override
    with Session(engine) as session:
        # Dependency Override setzen
        app.dependency_overrides[get_session] = lambda: session
        yield session
        # Cleanup
        app.dependency_overrides.clear()
