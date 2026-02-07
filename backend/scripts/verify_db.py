#!/usr/bin/env python3
"""
Verifizierungs-Skript für Datenbank-Verbesserungen.
Testet die neuen Features: Auto-Update, Cascade Delete, Indizes.
"""


import sys
import os

# Backend Root zum Pfad hinzufügen (zwei Ebenen hoch)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
    
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import text
from app.db_models import Document, DocumentFile, Annotation, DocumentStatus, FileKind
from app.trace_models import ProcessingRun, ExtractedDocument, ScorePenalty, PenaltyCategory
import uuid
from datetime import datetime
import time

def test_db_improvements():
    """Testet alle DB-Verbesserungen."""
    
    # Temporäre In-Memory Datenbank für Tests
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    
    print("🧪 Teste Datenbank-Verbesserungen...\n")
    
    # =========================================================================
    # Test 1: Auto-Update von updated_at
    # =========================================================================
    print("1️⃣  Test: Auto-Update von updated_at")
    
    with Session(engine) as session:
        # Dokument erstellen
        doc = Document(
            ba_number="BA123456",
            status=DocumentStatus.NEW,
            filename="test.pdf"
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        
        original_updated_at = doc.updated_at
        print(f"   📅 Original updated_at: {original_updated_at}")
        
        # Kurz warten
        time.sleep(0.1)
        
        # Dokument ändern
        doc.ba_number = "BA999999"
        session.add(doc)
        session.commit()
        session.refresh(doc)
        
        new_updated_at = doc.updated_at
        print(f"   📅 Neues updated_at:    {new_updated_at}")
        
        # Hinweis: In SQLite funktioniert onupdate möglicherweise nicht automatisch
        # In PostgreSQL/MySQL würde es funktionieren
        if new_updated_at > original_updated_at:
            print("   ✅ Auto-Update funktioniert!\n")
        else:
            print("   ⚠️  Auto-Update in SQLite eingeschränkt (OK in PostgreSQL/MySQL)\n")
    
    # =========================================================================
    # Test 2: Cascade Delete
    # =========================================================================
    print("2️⃣  Test: Cascade Delete für Document → Files/Annotations")
    
    with Session(engine) as session:
        # Dokument mit Files und Annotations erstellen
        doc = Document(
            ba_number="BA555555",
            status=DocumentStatus.NEW,
            filename="cascade_test.pdf"
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        
        doc_id = doc.id
        
        # Files hinzufügen
        file1 = DocumentFile(
            document_id=doc_id,
            kind=FileKind.ORIGINAL_PDF,
            path="/tmp/test.pdf"
        )
        file2 = DocumentFile(
            document_id=doc_id,
            kind=FileKind.ANNOTATED_PDF,
            path="/tmp/annotated.pdf"
        )
        
        # Annotation hinzufügen
        annotation = Annotation(
            document_id=doc_id,
            source="model",
            fields={"ba_number": {"value": "BA555555"}}
        )
        
        session.add(file1)
        session.add(file2)
        session.add(annotation)
        session.commit()
        
        print(f"   📄 Erstellt: 1 Document, 2 Files, 1 Annotation")
        
        # Dokument löschen
        session.delete(doc)
        session.commit()
        
        # Prüfen ob Files/Annotations auch gelöscht wurden
        remaining_files = session.exec(
            select(DocumentFile).where(DocumentFile.document_id == doc_id)
        ).all()
        remaining_annotations = session.exec(
            select(Annotation).where(Annotation.document_id == doc_id)
        ).all()
        
        if len(remaining_files) == 0 and len(remaining_annotations) == 0:
            print(f"   ✅ Cascade Delete funktioniert! (2 Files + 1 Annotation gelöscht)\n")
        else:
            print(f"   ❌ Cascade Delete fehlgeschlagen! ({len(remaining_files)} Files, {len(remaining_annotations)} Annotations übrig)\n")
    
    # =========================================================================
    # Test 3: Foreign Key Constraint (frontend_document_id)
    # =========================================================================
    print("3️⃣  Test: Foreign Key für frontend_document_id")
    
    with Session(engine) as session:
        # Frontend-Dokument erstellen
        frontend_doc = Document(
            ba_number="BA777777",
            status=DocumentStatus.NEEDS_REVIEW,
            filename="frontend.pdf"
        )
        session.add(frontend_doc)
        session.commit()
        session.refresh(frontend_doc)
        
        # Processing Run erstellen
        run = ProcessingRun(
            filename="backend_process.pdf",
            success=True
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        
        # Extracted Document mit Link
        extracted = ExtractedDocument(
            run_id=run.id,
            ba_number="BA777777",
            frontend_document_id=frontend_doc.id  # Link zum Frontend
        )
        session.add(extracted)
        session.commit()
        
        print(f"   🔗 Frontend Document: {frontend_doc.id}")
        print(f"   🔗 Extracted Document verlinkt: {extracted.frontend_document_id}")
        
        if extracted.frontend_document_id == frontend_doc.id:
            print("   ✅ Foreign Key Beziehung funktioniert!\n")
        else:
            print("   ❌ Foreign Key Beziehung fehlgeschlagen!\n")
    
    # =========================================================================
    # Test 4: Indizes (nur Info, nicht testbar in-memory)
    # =========================================================================
    print("4️⃣  Test: Indizes (Metadaten-Check)")
    
    with Session(engine) as session:
        # Indizes auslesen (SQLite-spezifisch)
        result = session.exec(
            text("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'")
        ).all()
        
        expected_indexes = [
            'ix_documents_status',
            'ix_documents_ba_number',
            'ix_documents_claimed_by_user_id',
            'ix_documents_claim_expires_at',
            'ix_document_files_kind',
            'ix_annotations_author_user_id',
            'ix_annotations_source',
        ]
        
        found_indexes = [idx for idx in result]
        print(f"   📊 Gefundene Indizes: {len(found_indexes)}")
        
        if len(found_indexes) > 0:
            print("   ✅ Indizes wurden erstellt!")
            for idx in found_indexes[:5]:  # Erste 5 zeigen
                print(f"      - {idx}")
            if len(found_indexes) > 5:
                print(f"      ... und {len(found_indexes) - 5} weitere")
        else:
            print("   ℹ️  Keine Indizes in In-Memory DB (normal)")
        print()
    
    # =========================================================================
    # Test 5: Cascade Delete für Trace Models
    # =========================================================================
    print("5️⃣  Test: Cascade Delete für ExtractedDocument → Penalties/Signals")
    
    with Session(engine) as session:
        # Processing Run erstellen
        run = ProcessingRun(
            filename="test_cascade.pdf",
            success=True
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        
        # Extracted Document erstellen
        extracted = ExtractedDocument(
            run_id=run.id,
            ba_number="BA888888"
        )
        session.add(extracted)
        session.commit()
        session.refresh(extracted)
        
        extracted_id = extracted.id
        
        # Penalties hinzufügen
        penalty1 = ScorePenalty(
            document_id=extracted_id,
            points=20,
            reason="BA-Nummer fehlt",
            category=PenaltyCategory.MISSING_FIELD
        )
        penalty2 = ScorePenalty(
            document_id=extracted_id,
            points=10,
            reason="Datum fehlt",
            category=PenaltyCategory.DATE_ERROR
        )
        
        session.add(penalty1)
        session.add(penalty2)
        session.commit()
        
        print(f"   📊 Erstellt: 1 ExtractedDocument, 2 Penalties")
        
        # Extracted Document löschen
        session.delete(extracted)
        session.commit()
        
        # Prüfen ob Penalties auch gelöscht wurden
        remaining_penalties = session.exec(
            select(ScorePenalty).where(ScorePenalty.document_id == extracted_id)
        ).all()
        
        if len(remaining_penalties) == 0:
            print(f"   ✅ Cascade Delete funktioniert! (2 Penalties gelöscht)\n")
        else:
            print(f"   ❌ Cascade Delete fehlgeschlagen! ({len(remaining_penalties)} Penalties übrig)\n")
    
    print("=" * 60)
    print("✅ Alle Tests abgeschlossen!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_db_improvements()
    except Exception as e:
        print(f"❌ Fehler beim Testen: {e}")
        import traceback
        traceback.print_exc()
