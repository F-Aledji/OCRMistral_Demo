"""
Migration: Business Repair Loop Tracking

Fügt neue Felder für Schema- und Business-Repair-Tracking hinzu.

Neue Felder in ProcessingRun:
- schema_repair_attempted
- schema_repair_success (abgeleitet)
- business_repair_attempted
- business_repair_success
- initial_score
- final_score
- score_improvement

Neue Felder in ExtractedDocument:
- initial_score

Ausführen mit:
    python backend/migrations/add_business_repair_tracking.py
"""

import sys
import os

# Projekt-Root zum Path hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import create_engine, Session, text
from backend.app.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Führt die Migration aus."""
    logger.info("🔄 Starte Migration: Business Repair Loop Tracking...")
    
    with Session(engine) as session:
        # ProcessingRun erweitern
        migrations = [
            # Schema Repair Tracking
            "ALTER TABLE processing_run ADD COLUMN schema_repair_attempted BOOLEAN DEFAULT FALSE",
            "ALTER TABLE processing_run ADD COLUMN schema_repair_success BOOLEAN DEFAULT FALSE",
            
            # Business Repair Tracking
            "ALTER TABLE processing_run ADD COLUMN business_repair_attempted BOOLEAN DEFAULT FALSE",
            "ALTER TABLE processing_run ADD COLUMN business_repair_success BOOLEAN DEFAULT FALSE",
            "ALTER TABLE processing_run ADD COLUMN initial_score INTEGER",
            "ALTER TABLE processing_run ADD COLUMN final_score INTEGER",
            "ALTER TABLE processing_run ADD COLUMN score_improvement INTEGER",
            
            # ExtractedDocument erweitern
            "ALTER TABLE extracted_document ADD COLUMN initial_score INTEGER"
        ]
        
        for sql in migrations:
            try:
                session.exec(text(sql))
                logger.info(f"✓ {sql}")
            except Exception as e:
                # Column existiert bereits (z.B. bei erneutem Ausführen)
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    logger.warning(f"⚠️ Column existiert bereits: {sql}")
                else:
                    logger.error(f"❌ Fehler: {e}")
                    raise
        
        session.commit()
    
    logger.info("✅ Migration abgeschlossen!")


def rollback():
    """Macht die Migration rückgängig."""
    logger.info("⏪ Rollback: Business Repair Loop Tracking...")
    
    with Session(engine) as session:
        rollbacks = [
            "ALTER TABLE processing_run DROP COLUMN schema_repair_attempted",
            "ALTER TABLE processing_run DROP COLUMN schema_repair_success",
            "ALTER TABLE processing_run DROP COLUMN business_repair_attempted",
            "ALTER TABLE processing_run DROP COLUMN business_repair_success",
            "ALTER TABLE processing_run DROP COLUMN initial_score",
            "ALTER TABLE processing_run DROP COLUMN final_score",
            "ALTER TABLE processing_run DROP COLUMN score_improvement",
            "ALTER TABLE extracted_document DROP COLUMN initial_score"
        ]
        
        for sql in rollbacks:
            try:
                session.exec(text(sql))
                logger.info(f"✓ {sql}")
            except Exception as e:
                logger.warning(f"⚠️ {e}")
        
        session.commit()
    
    logger.info("✅ Rollback abgeschlossen!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true", help="Rollback der Migration")
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
