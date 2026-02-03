import logging 
from dataclasses import dataclass, field
from typing import List, Optional
from schema.models import SupplierConfirmation

logger = logging.getLogger(__name__)


@dataclass
class ScoreCard:
    """Hält das Ergebnis der Bewertung fest."""
    total_score: int = 100
    penalties: List[str] = field(default_factory=list) # Liste von Strings und sorgt mittels field dass jedes Objekt seine eigene Liste hat
    signals: List[str] = field(default_factory=list)

    def add_penalty(self, points: int, reason:str):
        """Zieht Punkte ab und protokolliert den Grund."""
        self.total_score -= points
        self.penalties.append(f"-{points} Punkte: {reason}")

    def add_signal(self, signal: str):
        """Positives Signal (ohne Punkte nur Protokollierung)."""
        self.signals.append(f"INFO: {signal}")

    def add_bonus(self, points: int, signal: str):
        """Fügt Bonuspunkte hinzu und protokolliert das Signal."""
        self.total_score = min(100, self.total_score + points)  # Maximal 100 Punkte
        self.signals.append(f"+{points} Punkte: {signal}")

class ScoreEngine:
    """Analysiert die extrahierten Daten und vergibt einen Validationsscore."""
    def __init__(self):
        self.trusted_suppliers = []

    def evaluate(self, data: SupplierConfirmation) -> ScoreCard:
        card = ScoreCard()
    
    # 1. Technischer Check: Hat die KI Reasoning betrieben?
        self._check_reasoning(data, card)

    # 2. Null-Check: pflichtfelder
        self._check_mandatory_fields(data, card)

    # 3. Flag-Check: Pydantic Status Felder
        self._check_status_flags(data, card)

    # 4. Mathe-Check: Zeilenekalkulation
        self._check_line_math(data, card)
        
    # 5. Business Check (mit ERP Daten)
        self._check_erp_data(data, card)

        return card
    
    # Punkteabzug muss ich hier noch anpassen
    def _check_reasoning(self, data: SupplierConfirmation, card: ScoreCard):
        """Überprüft ob Reasoning durchgeführt wurde."""
        reasoning = getattr(data, "reasoning", None)
        if not reasoning or len(str(reasoning)) < 20:
            card.add_penalty(5, "Kein oder unzureichendes Reasoning im Feld 'reasoning' gefunden.")
        elif "nicht gefunden" in str(reasoning).lower() or "unsicher" in str(reasoning).lower():
            card.add_penalty(5, "Reasoning deutet auf Unsicherheiten hin.")

        else: 
            card.add_signal("Reasoning im Feld 'reasoning' erkannt.")

    def _check_mandatory_fields(self, data: SupplierConfirmation, card: ScoreCard):
         # Datum (Soft Validation in models.py setzt es auf None bei Fehler)
        if not data.supplierConfirmationData.date.value:
            card.add_penalty(20, "Belegdatum fehlt oder unlesbar")
            
        # BA-Nummer / Referenz
        ref_num = data.correspondence.number
        if not ref_num or "nicht gefunden" in ref_num.lower():
             card.add_penalty(25, "Bestellnummer (BA) fehlt")
        
        # Positions-Check
        if not data.details:
            card.add_penalty(50, "Keine Positionen gefunden (Leeres Array)")


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

    def _check_erp_data(self, data: SupplierConfirmation, card: ScoreCard):
        """Simuliert den Abgleich mit Stammdaten."""
        
        # Lieferantennummer Check
        supplier_num = data.invoiceSupplierData.supplierPartner.number
        
        if supplier_num == 0:
            card.add_penalty(10, "Lieferantennummer nicht gefunden")
        elif supplier_num in self.trusted_suppliers:
            card.add_bonus(5, f"Lieferant {supplier_num} ist bekannt & vertrauenswürdig")
        else:
            # Unbekannter Lieferant ist kein Fehler, aber auch kein Bonus
            card.add_signal(f"Lieferant {supplier_num} ist neu/unbekannt")