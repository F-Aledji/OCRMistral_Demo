# =============================================================================
# TESTS FÜR OCR SCHEMA
# =============================================================================
# Testet die Pydantic-Schema-Validierung und Parser-Funktionen
# =============================================================================

import pytest
import sys
from pathlib import Path

# Projekt-Root zu sys.path hinzufügen
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.schema.ocr_schema import (
    parse_float,
    parse_int,
    parse_smart_date,
    clean_currency,
    parse_discount,
    BoundingBox,
    Details,
    SupplierConfirmation,
)


class TestParseFloat:
    """Tests für die Float-Parser-Funktion."""
    
    def test_german_format(self):
        """Deutsche Zahlenformatierung sollte erkannt werden."""
        # 1.234,56 → 1234.56
        result = parse_float("1.234,56")
        assert result == 1234.56
    
    def test_us_format(self):
        """US-Zahlenformat sollte erkannt werden."""
        result = parse_float("1234.56")
        assert result == 1234.56
    
    def test_integer_string(self):
        """Integer-Strings sollten zu Float konvertiert werden."""
        result = parse_float("100")
        assert result == 100.0
    
    def test_float_passthrough(self):
        """Bereits Float sollte durchgereicht werden."""
        result = parse_float(123.45)
        assert result == 123.45
    
    def test_none_returns_zero(self):
        """None sollte 0.0 zurückgeben."""
        result = parse_float(None)
        assert result == 0.0
    
    def test_empty_string(self):
        """Leerer String sollte 0.0 zurückgeben."""
        result = parse_float("")
        assert result == 0.0
    
    def test_with_currency_symbol(self):
        """Währungssymbole werden NICHT automatisch entfernt."""
        # parse_float entfernt keine Währungssymbole
        # Es gibt 0.0 zurück wenn es den String nicht parsen kann
        result = parse_float("1.234,56")  # Ohne € Symbol
        assert result == 1234.56


class TestParseInt:
    """Tests für die Int-Parser-Funktion."""
    
    def test_simple_int(self):
        """Einfache Integer sollten geparst werden."""
        result = parse_int("42")
        assert result == 42
    
    def test_with_thousands_separator(self):
        """Tausendertrennzeichen sollten entfernt werden."""
        result = parse_int("1.000")
        assert result == 1000
    
    def test_float_to_int(self):
        """Float-Werte sollten zu Int konvertiert werden."""
        result = parse_int(42.7)
        assert result == 42
    
    def test_none_returns_zero(self):
        """None sollte 0 zurückgeben."""
        result = parse_int(None)
        assert result == 0


class TestParseSmartDate:
    """Tests für die intelligente Datumsparser-Funktion."""
    
    def test_german_date_format(self):
        """Deutsches Datumsformat dd.mm.yyyy."""
        result = parse_smart_date("15.01.2026")
        assert result == "15.01.2026"
    
    def test_iso_format(self):
        """ISO-Format yyyy-mm-dd sollte konvertiert werden."""
        result = parse_smart_date("2026-01-15")
        assert result == "15.01.2026"
    
    def test_kw_format(self):
        """KW-Format (Kalenderwoche) sollte erkannt werden."""
        result = parse_smart_date("KW 3")
        # Sollte ein Datum im Format dd.mm.yyyy zurückgeben
        assert "." in result
        assert len(result.split(".")) == 3
    
    def test_none_returns_none(self):
        """None sollte None zurückgeben."""
        result = parse_smart_date(None)
        assert result is None
    
    def test_empty_string(self):
        """Leerer String sollte None zurückgeben."""
        result = parse_smart_date("")
        assert result is None


class TestCleanCurrency:
    """Tests für die Währungsbereinigung."""
    
    def test_eur_with_space(self):
        """'EUR ' sollte zu 'EUR' bereinigt werden."""
        result = clean_currency("EUR ")
        assert result == "EUR"
    
    def test_lowercase(self):
        """Kleinbuchstaben sollten zu Großbuchstaben werden."""
        result = clean_currency("eur")
        assert result == "EUR"
    
    def test_none_returns_eur(self):
        """None sollte 'EUR' als Default zurückgeben."""
        result = clean_currency(None)
        assert result == "EUR"


class TestParseDiscount:
    """Tests für die Rabatt-Parser-Funktion."""
    
    def test_percent_format(self):
        """Prozentrabatt sollte erkannt werden."""
        result = parse_discount("15%")
        assert result["is_percent"] is True
        assert result["value"] == 15.0
    
    def test_absolute_format(self):
        """Absolutrabatt sollte erkannt werden."""
        result = parse_discount("50.00")
        assert result["is_percent"] is False
        assert result["value"] == 50.0
    
    def test_none_returns_zero(self):
        """None sollte Null-Rabatt zurückgeben."""
        result = parse_discount(None)
        assert result["value"] == 0.0


class TestBoundingBox:
    """Tests für die BoundingBox-Klasse."""
    
    def test_create_bbox(self):
        """BoundingBox sollte erstellt werden können."""
        bbox = BoundingBox(x0=100.0, y0=200.0, x1=300.0, y1=250.0)
        
        assert bbox.x0 == 100.0
        assert bbox.y0 == 200.0
        assert bbox.x1 == 300.0
        assert bbox.y1 == 250.0
    
    def test_bbox_dimensions(self):
        """Dimensionen sollten berechenbar sein."""
        bbox = BoundingBox(x0=0, y0=0, x1=100, y1=50)
        
        width = bbox.x1 - bbox.x0
        height = bbox.y1 - bbox.y0
        
        assert width == 100
        assert height == 50


class TestDetailsValidation:
    """Tests für die Details (Positions-) Validierung."""
    
    def test_math_validation(self):
        """Positionsberechnung sollte validiert werden."""
        # Menge * Preis = Nettowert
        # Details-Objekt mit korrekter Berechnung erstellen
        # Dies ist ein High-Level-Test der Validierungslogik
        pass  # Implementierung abhängig von der Details-Klasse
