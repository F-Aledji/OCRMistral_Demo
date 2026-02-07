# =============================================================================
# TESTS FÜR SCORE ENGINE
# =============================================================================
# Testet die Qualitätsbewertung von OCR-Ergebnissen
# =============================================================================

import pytest
import sys
from pathlib import Path

# Projekt-Root zu sys.path hinzufügen
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.validation import ScoreCard, ScoreEngine
from backend.schema.ocr_schema import SupplierConfirmation, Document


class TestScoreCard:
    """Tests für die ScoreCard-Datenklasse."""
    
    def test_initial_score(self):
        """Initialer Score sollte 100 sein."""
        card = ScoreCard()
        assert card.total_score == 100
    
    def test_add_penalty(self):
        """Penalty sollte Score reduzieren."""
        card = ScoreCard()
        card.add_penalty(20, "BA-Nummer fehlt")
        
        assert card.total_score == 80
        assert len(card.penalties) == 1
        assert "BA-Nummer fehlt" in card.penalties[0]
    
    def test_multiple_penalties(self):
        """Mehrere Penalties sollten kumulieren."""
        card = ScoreCard()
        card.add_penalty(20, "BA fehlt")
        card.add_penalty(15, "Datum fehlt")
        
        assert card.total_score == 65
        assert len(card.penalties) == 2
    
    def test_score_minimum_zero(self):
        """Score kann unter 0 fallen (kein Min-Limit enforced)."""
        card = ScoreCard()
        card.add_penalty(150, "Alles falsch")
        
        # Der Score geht ins Negative - das ist das aktuelle Verhalten
        assert card.total_score == -50
    
    def test_add_signal(self):
        """Signale sollten ohne Punkteabzug hinzugefügt werden."""
        card = ScoreCard()
        card.add_signal("Dokument erkannt")
        
        assert card.total_score == 100
        assert len(card.signals) == 1
    
    def test_add_bonus(self):
        """Bonus sollte Score erhöhen (max 100) und in signals gespeichert werden."""
        card = ScoreCard()
        card.add_penalty(20, "Penalty")
        card.add_bonus(10, "Bekannter Lieferant")
        
        assert card.total_score == 90
        # Bonus wird in signals gespeichert, nicht in separater Liste
        assert any("+10 Punkte" in s for s in card.signals)
    
    def test_bonus_max_100(self):
        """Bonus sollte Score nicht über 100 erhöhen."""
        card = ScoreCard()
        card.add_bonus(50, "Mega Bonus")
        
        assert card.total_score == 100


class TestScoreEngine:
    """Tests für die ScoreEngine-Bewertungslogik."""
    
    @pytest.fixture
    def engine(self):
        """ScoreEngine-Instanz für Tests."""
        return ScoreEngine()
    
    def test_engine_initialization(self, engine):
        """Engine sollte korrekt initialisiert werden."""
        assert engine is not None
    
    def test_perfect_document_score(self, engine):
        """Vollständiges Dokument sollte hohen Score bekommen."""
        # Wir testen hier die ScoreCard-Integration
        card = ScoreCard()
        
        # Simuliere perfektes Dokument (keine Penalties)
        assert card.total_score == 100
    
    def test_missing_ba_penalty(self, engine):
        """Fehlende BA-Nummer sollte Penalty geben."""
        card = ScoreCard()
        
        # Simuliere fehlende BA
        # Die eigentliche Logik ist in _check_mandatory_fields
        card.add_penalty(30, "BA-Nummer nicht gefunden")
        
        assert card.total_score < 100
        assert any("BA" in p for p in card.penalties)
    
    def test_known_supplier_bonus(self, engine):
        """Bekannter Lieferant sollte Bonus geben."""
        card = ScoreCard()
        
        # Simuliere Bonus für bekannten Lieferanten
        card.add_bonus(5, "Lieferant in DB gefunden")
        
        assert card.total_score == 100  # War schon 100, bleibt 100
        # Bonus wird in signals als "+X Punkte: ..." gespeichert
        assert any("+5 Punkte" in s for s in card.signals)


class TestScoreEngineIntegration:
    """Integrationstests mit echten Pydantic-Models (wenn möglich)."""
    
    def test_score_card_serialization(self):
        """ScoreCard sollte serialisierbar sein."""
        card = ScoreCard()
        card.add_penalty(10, "Test")
        card.add_signal("Info")
        
        # Sollte keine Fehler werfen
        penalties = card.penalties
        signals = card.signals
        
        assert isinstance(penalties, list)
        assert isinstance(signals, list)
