# =============================================================================
# SCORE ENGINE - Qualitätsbewertung für OCR-Ergebnisse
# =============================================================================
#
# ZWECK:
# Dieses Modul bewertet die Qualität der extrahierten Daten aus OCR-Dokumenten.
# Jedes Dokument startet mit 100 Punkten, Fehler führen zu Punktabzug.
#
# PUNKTESYSTEM:
# - 100 Punkte = Perfekte Extraktion
# - 85+ Punkte = Automatisch verarbeitbar (Schwellenwert konfigurierbar)
# - <85 Punkte = Manuelle Prüfung erforderlich (Eskalation)
#
# ABLAUF:
# 1. ScoreCard wird erstellt (startet bei 100)
# 2. ScoreEngine führt 5 Prüfungen durch
# 3. Jede Prüfung kann Punkte abziehen (Penalties) oder Signale setzen
# 4. Endergebnis entscheidet ob Dokument eskaliert wird
#
# =============================================================================

import logging 
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from backend.schema.ocr_schema import SupplierConfirmation
except ImportError:
    from schema.ocr_schema import SupplierConfirmation

logger = logging.getLogger(__name__)


# =============================================================================
# SCORECARD - Hält das Bewertungsergebnis
# =============================================================================

@dataclass
class ScoreCard:
    """
    Sammelt alle Bewertungen für ein einzelnes Dokument.
    
    Attribute:
        total_score: Aktueller Punktestand (startet bei 100, min 0)
        penalties: Liste aller Abzüge mit Begründung (z.B. "-20 Punkte: BA fehlt")
        signals: Info-Meldungen ohne Punkteeinfluss (z.B. "Reasoning erkannt")
    
    Beispiel:
        card = ScoreCard()
        card.add_penalty(20, "Datum fehlt")
        card.add_signal("Lieferant bekannt")
        print(card.total_score)  # 80
    """
    total_score: int = 100
    # field(default_factory=list) stellt sicher, dass jede ScoreCard ihre EIGENE Liste hat
    # (sonst würden alle Instanzen dieselbe Liste teilen - Python-Gotcha!)
    penalties: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    template_match: bool = False

    def add_penalty(self, points: int, reason: str):
        """
        Zieht Punkte ab und protokolliert den Grund.
        
        Args:
            points: Anzahl abzuziehender Punkte
            reason: Begründung für den Abzug
        """
        self.total_score -= points
        self.penalties.append(f"-{points} Punkte: {reason}")

    def add_signal(self, signal: str):
        """
        Fügt eine Info-Meldung hinzu (kein Punkteeinfluss).
        
        Nützlich für: Positive Beobachtungen, Warnungen ohne Abzug
        """
        self.signals.append(f"INFO: {signal}")

    def add_bonus(self, points: int, signal: str):
        """
        Fügt Bonuspunkte hinzu (maximal bis 100).
        
        Wird genutzt wenn z.B. ein bekannter Lieferant erkannt wird.
        """
        self.total_score = min(100, self.total_score + points)  # Cap bei 100
        self.signals.append(f"+{points} Punkte: {signal}")

# =============================================================================
# SCORE ENGINE - Führt die 5-stufige Qualitätsprüfung durch
# =============================================================================

class ScoreEngine:
    """
    Führt eine mehrstufige Qualitätsprüfung der OCR-Ergebnisse durch.
    
    Die 5 Prüfungsschritte (in Reihenfolge):
    
    1. REASONING CHECK (-5 Punkte)
       → Hat die KI ihre Entscheidungen begründet?
       
    2. PFLICHTFELDER CHECK (-20 bis -50 Punkte)
       → Sind alle kritischen Felder vorhanden?
       → Datum (-20), BA-Nummer (-25), Positionen (-50)
       
    3. STATUS FLAGS CHECK (-100 bei falschem Dokumenttyp)
       → Pydantic-Validierungsflags aus dem Schema prüfen
       → Dokumenttyp, Datum-Plausibilität, Summen
       
    4. ZEILEN-MATHEMATIK CHECK (dynamisch, max -30)
       → Sind die Berechnungen in jeder Position korrekt?
       → Menge × Preis = Gesamtpreis?
       
    5. ERP/BUSINESS CHECK (-10 bis +5)
       → Ist der Lieferant bekannt?
       → Stammdaten-Abgleich (placeholder für Integration)
    """
    
    def __init__(self):
        self.config = self._load_scoring_config()
        self.penalties = self.config.get("penalties", {})
        self.bonuses = self.config.get("bonuses", {})
        
        # Liste bekannter Lieferanten (wird später dynamsich geladen)
        self.trusted_suppliers = []

    def _load_scoring_config(self) -> dict:
        """Lädt die Scoring-Konfiguration aus JSON."""
        import json
        import os
        # Config liegt in ../../config/scoring_config.json relativ zu validation/score.py
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "scoring_config.json")
        
        default_config = {
            "thresholds": {"auto_process": 85},
            "penalties": {
                "reasoning_missing": 5,
                "missing_ba": 25,
                "missing_date": 20,
                "missing_items": 50,
                "missing_net_total": 20,
                "unknown_supplier": 15
            },
            "bonuses": {"known_supplier": 10}
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden der Scoring-Config: {e}")
        else:
            logger.warning(f"Scoring-Config nicht gefunden unter: {config_path}")
        
        return default_config

    def evaluate(self, data: SupplierConfirmation, known_supplier: bool = False, template_match: bool = False) -> ScoreCard:
        """
        Hauptmethode: Führt alle 5 Prüfungen durch.
        
        Args:
            data: Validiertes SupplierConfirmation-Objekt aus OCR
            known_supplier: True wenn Lieferant in DB gefunden wurde
            template_match: True wenn ein Template für diesen Lieferanten existiert
            
        Returns:
            ScoreCard mit Punktestand und allen Penalties/Signals
        """
        card = ScoreCard()
        card.template_match = template_match
    
        # ===== SCHRITT 1: Reasoning Check =====
        # Hat die KI erklärt, warum sie bestimmte Entscheidungen getroffen hat?
        self._check_reasoning(data, card)

        # ===== SCHRITT 2: Pflichtfelder Check =====
        # Sind die wichtigsten Felder vorhanden und lesbar?
        self._check_mandatory_fields(data, card)

        # ===== SCHRITT 3: Status Flags Check =====
        # Prüft Flags die vom Pydantic-Model berechnet wurden
        self._check_status_flags(data, card)

        # ===== SCHRITT 4: Zeilen-Mathematik Check =====
        # Stimmen die Berechnungen in den einzelnen Positionen?
        self._check_line_math(data, card)
        
        # ===== SCHRITT 5: ERP/Business Check (Hybrid Logic) =====
        # Abgleich mit Stammdaten und Templates
        self._check_erp_data(data, card, known_supplier, template_match)

        return card
    
    # Punkteabzug muss ich hier noch anpassen
    def _check_reasoning(self, data: SupplierConfirmation, card: ScoreCard):
        """Überprüft ob Reasoning durchgeführt wurde."""
        reasoning = getattr(data, "reasoning", None)
        penalty = self.penalties.get("reasoning_missing", 5)
        
        if not reasoning or len(str(reasoning)) < 20:
            card.add_penalty(penalty, "Kein oder unzureichendes Reasoning im Feld 'reasoning' gefunden.")
        elif "nicht gefunden" in str(reasoning).lower() or "unsicher" in str(reasoning).lower():
            card.add_penalty(penalty, "Reasoning deutet auf Unsicherheiten hin.")

        else: 
            card.add_signal("Reasoning im Feld 'reasoning' erkannt.")

    def _check_mandatory_fields(self, data: SupplierConfirmation, card: ScoreCard):
         # Datum (Soft Validation in models.py setzt es auf None bei Fehler)
        if not data.supplierConfirmationData.date.value:
            card.add_penalty(self.penalties.get("missing_date", 20), "Belegdatum fehlt oder unlesbar")
            
        # BA-Nummer / Referenz
        ref_num = data.correspondence.number
        if not ref_num or "nicht gefunden" in ref_num.lower():
             card.add_penalty(self.penalties.get("missing_ba", 25), "Bestellnummer (BA) fehlt")
        
        # Positions-Check
        if not data.details:
            card.add_penalty(self.penalties.get("missing_items", 50), "Keine Positionen gefunden (Leeres Array)")


    def _check_status_flags(self, data: SupplierConfirmation, card: ScoreCard):
        """Prüft die Flags, die wir in models.py berechnet haben."""
        
        # Dokumententyp
        doctype_status = getattr(data, "doctype_status", None)
        if doctype_status and doctype_status != "OK":
            card.add_penalty(100, f"Falscher Dokumententyp: {doctype_status}") # Showstopper
            
        # Datum Plausibilität
        date_plausibility_status = getattr(data, "date_plausibility_status", None)
        if date_plausibility_status and date_plausibility_status != "OK":
            # Wenn Fehlertext mit Warnung beginnt -> weniger Abzug
            if "Warnung" in date_plausibility_status:
                card.add_penalty(10, f"Datums-Warnung: {date_plausibility_status}")
            else:
                card.add_penalty(15, f"Datums-Fehler: {date_plausibility_status}")

        # Summen-Check (Footer)
        sum_validation_status = getattr(data, "sum_validation_status", None)
        if sum_validation_status and sum_validation_status != "OK":
            if "Warnung" in sum_validation_status:
                 card.add_penalty(5, "Footer-Summe fehlt (kann nicht geprüft werden)")
            else:
                 card.add_penalty(20, f"Summen-Diskrepanz: {sum_validation_status}")
        else:
            card.add_signal("Gesamtsumme geprüft & korrekt")

    
    def _check_line_math(self, data: SupplierConfirmation, card: ScoreCard):
        """Prüft jede einzelne Position auf Rechenfehler."""
        math_errors = 0
        zero_warnings = 0
        
        for pos in data.details:
            status = getattr(pos, "math_status", "OK")
            if "FEHLER" in status:
                math_errors += 1
                # Wir loggen nicht jede Zeile einzeln in die Penalties, um die Liste nicht zu fluten
                # Aber wir merken uns den Fehler im Detail (ist ja im JSON Objekt gespeichert)
            elif "WARNUNG" in status: # z.B. Menge 0
                zero_warnings += 1
        
        if math_errors > 0:
            # Dynamischer Abzug: 10 Punkte Basis + 2 pro falscher Zeile (max 30)
            penalty = min(30, 10 + (math_errors * 2))
            card.add_penalty(penalty, f"Rechenfehler in {math_errors} Positionen")
        
        if zero_warnings > 0:
            card.add_penalty(5, f"{zero_warnings} Positionen haben Menge/Preis 0")

    def _check_erp_data(self, data: SupplierConfirmation, card: ScoreCard, known_supplier: bool, template_match: bool):
        """
        ERP-Abgleich mit Stammdaten und Templates.
        Verteilt Bonuspunkte oder Penalties basierend auf dem Abgleich-Ergebnis.
        """
        # 1. Lieferant bekannt?
        if known_supplier:
            bonus = self.bonuses.get("known_supplier", 10)
            card.add_bonus(bonus, "Lieferant in Datenbank verifiziert")
        else:
            penalty = self.penalties.get("unknown_supplier", 15)
            card.add_penalty(penalty, "Lieferant unbekannt (keine BA-Nummer in DB gefunden)")
            
        # 2. Template verfügbar? (Zusatz-Bonus)
        if template_match:
            bonus = self.bonuses.get("template_match", 15)
            card.add_bonus(bonus, "Passendes Koordinaten-Template vorhanden")
        
        # 3. Lieferantennummer Check (Legacy, optional noch prüfen)
        supplier_num = data.invoiceSupplierData.supplierPartner.number
        if supplier_num == 0 and not known_supplier:
            # Nur Warnung wenn auch sonst nicht bekannt
            card.add_signal("Keine Lieferantennummer im Dokument extrahiert")
            # Unbekannter Lieferant ist kein Fehler, aber auch kein Bonus
            card.add_signal(f"Lieferant {supplier_num} ist neu/unbekannt")