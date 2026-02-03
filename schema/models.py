from email.policy import default
import json
import re
from datetime import datetime,timedelta
from typing_extensions import Annotated
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, AfterValidator, model_validator, ValidationInfo
from typing import Any, List, Optional

#--- 1. Helper Funktionen für Soft Validierung --- 

def parse_float(v: Any) -> float:
    """Macht aus Strings mit Zahlen einen sauberen Float ohne Dezimalpunkte."""
    if isinstance(v, float): return v
    if isinstance(v, int): return float(v)
    
    s = str(v).strip()
    
    if not s or s.lower() in ["nicht gefunden", "unsicher", "none", "null", "n/a"]:
        return 0.0
    
    # Entferne Tausendertrenner bsp 1.000,00 -> 1000,00 (DE Logic check)
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."): # Format 1.000,00
            s = s.replace(".", "").replace(",", ".")
        else: # Format 1,000.00
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return 0.0 

def parse_int(v: Any) -> int:
    """Macht aus Strings mit Zahlen einen sauberen Int."""
    if isinstance(v, int): return v
    if isinstance(v, float): return int(v)
    
    s = str(v).strip()
    if not s or s.lower() in ["nicht gefunden", "unsicher", "none", "null", "n/a"]:
        return 0 # FIX: Muss int sein, nicht 0.0

    s = s.replace(".","").replace(",","")
    s = re.sub(r'[^\d-]', '', s) # Nur Zahlen behalten
    
    try:
        return int(s)
    except ValueError:
        return 0
    
def parse_smart_date(v: Any) -> Optional[str]:
    """ Versteht 'dd.mm.yyyy', 'KW 40'. Gibt immer 'dd.mm.yyyy' zurück oder Fehler."""

    if not v or str(v).lower() in ["nicht gefunden", "none", "unsicher", "n/a"]:
        return None

    s = str(v).strip()

    # 1. Check auf Kalenderwoche
    kw_match = re.search(r'(?i)KW\s*(\d{1,2})', s)
    if kw_match:
        kw = int(kw_match.group(1))
        year_match = re.search(r'20\d{2}', s)
        year = int(year_match.group(0)) if year_match else datetime.now().year
        try:
            date_time = datetime.strptime(f"{year}-W{kw}-1", "%G-W%V-%u")
            return date_time.strftime("%d.%m.%Y")
        except ValueError:
            return None # Soft fail
        
    # 2. Standard Datum bereinigen
    s = s.replace('#', '.').replace('/', '.').replace('-', '.').strip()

    # FIX: Erst Deutsches Format versuchen!
    try: 
        dt = datetime.strptime(s, "%d.%m.%Y")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        pass

    # Fallback ISO Format
    try:
        dt = datetime.strptime(s, "%Y.%m.%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return None 
    
def clean_ba_number(v: Any, info:ValidationInfo) -> str:
    """Prüft gegen BA-Liste aus Context (falls vorhanden)."""
    s = str(v).strip()
    if not s or s.lower() in ["nicht gefunden", "none", "null"]:
        return "Nicht gefunden"
    
    s = s.replace("BA", "").strip()
    
    # Context Prüfung nur vorbereitet, keine Exception werfen für Soft-Validation
    if info.context: 
        valid_list = info.context.get('valid_ba_list')
        if valid_list:
            pass 
    
    return "BA" + s

def clean_currency(v: Any) -> str:
    """Bereinigt Währungen (z.B. 'EUR ' -> 'EUR')."""
    s = str(v).strip().upper()
    if "EUR" in s: return "EUR"
    if "USD" in s: return "USD"
    if len(s) == 3: return s
    return "EUR"

def round_price(v: float) -> float:
    return round(v, 2)

def parse_discount(v: Any) -> dict:
    """
    Parst Rabattwerte. Erkennt Prozent (z.B. '15%') oder Absolutbeträge.
    Gibt ein Dict zurück: {'is_percent': bool, 'value': float}
    """
    if v is None or v == "":
        return {'is_percent': False, 'value': 0.0}
    
    if isinstance(v, dict):
        # Bereits geparst
        return v
    
    if isinstance(v, (int, float)):
        return {'is_percent': False, 'value': float(v)}
    
    s = str(v).strip()
    
    if not s or s.lower() in ["nicht gefunden", "unsicher", "none", "null", "n/a", "0", "0.0"]:
        return {'is_percent': False, 'value': 0.0}
    
    # Check auf Prozent
    if '%' in s:
        # Extrahiere Zahl vor %
        percent_match = re.search(r'([\d,.]+)\s*%', s)
        if percent_match:
            percent_str = percent_match.group(1).replace(',', '.')
            try:
                return {'is_percent': True, 'value': float(percent_str)}
            except ValueError:
                return {'is_percent': False, 'value': 0.0}
    
    # Ansonsten als Absolutbetrag behandeln
    return {'is_percent': False, 'value': parse_float(s)}


# --- 2. Typ Definition ----

MoneyType = Annotated[
    float,
    BeforeValidator(parse_float),
    AfterValidator(round_price)
]

QuantityType = Annotated[
    int,
    BeforeValidator(parse_int),
]

CleanIntType = Annotated[
    int,
    BeforeValidator(parse_int)
]

DateType = Annotated[
    Optional[str], 
    BeforeValidator(parse_smart_date)
]

BAType = Annotated[
    str,
    BeforeValidator(clean_ba_number)
]

CurrencyType = Annotated[ # FIX: Tippfehler korrigiert
    str,
    BeforeValidator(clean_currency)
]

DiscountType = Annotated[
    dict,
    BeforeValidator(parse_discount)
]

# 3. --- Modelle ---

class Currency(BaseModel):
    isoCode: CurrencyType = Field(default="EUR", description="ISO Währungscode, z.B. 'EUR' für Euro.")

class GrossPrice(BaseModel):
    amount: MoneyType = Field(description="Der Brutto-Listenpreis pro Einheit vor Abzug von Rabatten. Falls im Dokument nur ein bereits rabattierter Netto-Einzelpreis steht, nimm diesen als Basiswert.")
    currency: Currency = Field(alias="Currency")

class DeliveryDate(BaseModel):
    specialValue: str = Field(default="NONE", description="Spezialwert für das Lieferdatum. Immer 'NONE' setzen.")
    date: DateType = Field(default=None, description="Liefertermin falls im Dokument vorhanden.")
    
class CorrespondenceDetail(BaseModel):
    number: Optional[str] = None
    
class Uom(BaseModel):
    code : str = Field(default= "Stk", description="Mengeneinheit. Setze diesen Wert immer auf 'Stk'.")

class TotalQuantity(BaseModel):
    amount: QuantityType = Field(description="Die extrahierte Menge der Artikel pro Position")
    uom: Uom = Field(alias="Uom") 

class Details(BaseModel):
    sequence: int = Field(default=0)
    number: CleanIntType = Field(description="Die Positionsnummer der Zeile im Dokument.")
    totalQuantity: TotalQuantity
    deliveryDate: DeliveryDate
    grossPrice: GrossPrice
    correspondenceDetail: CorrespondenceDetail = Field(alias="CorrespondenceDetail")

    # ---- Für Mathe Check ----
    lineTotalAmount: MoneyType = Field(description="Der finale Netto-Gesamtbetrag der Zeile. WICHTIG: Dies ist der Wert nach Abzug aller Rabatte (Menge * Einzelpreis - Rabatt). Dieser Wert wird für den Summen-Check im Footer verwendet.")
    math_status: str = Field(default="OK", description="Status der rechnerischen Prüfung")
    discount: DiscountType = Field(default={'is_percent': False, 'value': 0.0}, description="Der gewährte Rabatt auf die Position. Kann als Prozentsatz (z. B. '15%') oder als Absolutbetrag extrahiert werden. Falls kein Rabatt explizit ausgewiesen ist, setze 0.")

    @model_validator(mode='after')
    def fix_position_number(self):
        """Multipliziert die Positionsnummer mit 10."""
        raw_num = self.number
        if raw_num > 0:
            self.number = raw_num * 10
            if self.correspondenceDetail:
                self.correspondenceDetail.number = str(raw_num * 10)
        return self
    
    @model_validator(mode='after')
    def validate_math(self):
        qty = self.totalQuantity.amount
        price = self.grossPrice.amount
        total_extracted = self.lineTotalAmount
        
        # Rabatt auswerten
        discount_info = self.discount if isinstance(self.discount, dict) else {'is_percent': False, 'value': 0.0}
        is_percent = discount_info.get('is_percent', False)
        discount_value = discount_info.get('value', 0.0)
        
        # Leere Werte ignorieren (Warnung im Scoring)
        if qty == 0 or price == 0.0:
            self.math_status = "Warnung: Menge/Preis = 0"
            return self
        
        # Berechnung mit Rabatt
        if is_percent:
            # Prozentrabatt: Menge * Preis * (1 - Prozent/100)
            calculated = round(qty * price * (1 - discount_value / 100), 2)
            discount_desc = f"{discount_value}%"
        else:
            # Absolutrabatt: Menge * Preis - Rabattbetrag
            calculated = round(qty * price - discount_value, 2)
            discount_desc = f"{discount_value}€"
        
        # Toleranz von 5 Cent
        if abs(calculated - total_extracted) > 0.05:
            if discount_value > 0:
                self.math_status = f"FEHLER: [{qty} * {price} - Rabatt({discount_desc}) = {calculated}, jedoch im Dokument {total_extracted} extrahiert.]"
            else:
                self.math_status = f"FEHLER: [{qty} * {price} = {calculated}, jedoch im Dokument {total_extracted} extrahiert.]"
        else:
            self.math_status = "OK"
        return self

class Date(BaseModel):
    #Datetype parsed das Datum
    value: DateType = Field(description="Belegdatum im Format dd.mm.yyyy")

class SupplierConfirmationData(BaseModel):
    salesConfirmation : str = Field(default="Nicht gefunden", description="Fremdreferenznummer der Auftragsbestätigung, falls vorhanden. Nicht mit unserer BA-Nummer verwechseln!")
    date: Date
    documentType: str = Field(default="Auftragsbestätigung", description="Erkannter Typ (AB, Rechnung, Storno, Lieferschein)")

class SupplierPartner(BaseModel):
    number : CleanIntType = Field(default=0,description="Lieferantennummer des Lieferanten. Oft wird die unsere interne Nummer des Lieferanten im Dokumenten angegeben versuche es zu extrahieren")

class InvoiceSupplierData(BaseModel):
    supplierPartner : SupplierPartner = Field(alias="SupplierPartner")

class Correspondence(BaseModel):
    number: BAType = Field(default="Nicht gefunden", description="Beschaffungsauftragsnummer (BA-Nummer). Sehr wichtig bitte angeben ohne Präfix davor")

class Type(BaseModel):
    code : str = Field(default="100", description ="Präfix der Beschaffungsauftragsnummer. Wenn du unsicher bist auf '100' setzen.")

class InvoicingData(BaseModel):
    PaymentTerms: str = Field(default=None, description="Die Zahlungsbedinungen kann aber gerne leer bleiben.")

# --- ROOT MODEL---
class SupplierConfirmation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    reasoning: str = Field(alias="reasoning", description="WICHTIG: Nutze dieses Feld als Schmierblatt! " \
        "1. Prüfe den Dokumententyp (AB, Rechnung, etc.). " \
        "2. Suche BA- und AB-Nummer. " \
        "3. Berechne pro Zeile: (GrossPrice.amount - Rabatt) * Menge. Stimmt das mit lineTotalAmount überein? " \
        "4. Addiere alle lineTotalAmounts und vergleiche mit documentNetTotal. " \
        "5. Notiere Unstimmigkeiten und begründe deine Entscheidungen."
              )
    
    supplierConfirmationData: SupplierConfirmationData
    invoiceSupplierData: InvoiceSupplierData
    invoicingData: InvoicingData = Field(alias="invoicingData")
    correspondence: Correspondence = Field(alias="Correspondence")
    doc_type: Type = Field(alias="Type")
    details: List[Details] = Field(alias="Details")
    
    # Für Scoring und Validierung
    documentNetTotal: MoneyType = Field(description="Die finale Netto-Gesamtsumme aller Positionen laut Beleg-Footer. Dieser Wert muss der Summe aller lineTotalAmounts entsprechen.")
    date_plausibility_status: str = Field(default="OK", description="Status der Plausibilitätsprüfung")
    sum_validation_status: str = Field(default="OK", description="Status der Summenprüfung")
    doctype_status: str = Field(default="OK", description="Status der Dokumenttyp-Erkennung")

    # 1. Check: Dokumententyp 
    @model_validator(mode='after') # Wann dieser Check ausgeführt werden soll es ist ein Tag für die Funktion
    def check_document_type(self):
        doc_type = self.supplierConfirmationData.documentType.lower()
        forbidden_types = ["rechnung", "storno", "lieferschein", "gutschrift", "cancellation"]
        found = [t for t in forbidden_types if t in doc_type]
        if found:
            self.doctype_status = f"FEHLER: Dokumenttyp '{self.supplierConfirmationData.documentType}' enthält verbotene Typen: {', '.join(found)}."
        else: 
            self.doctype_status = "OK"
        return self
    

    # 2. Check: Datum Plausibilität
    @model_validator(mode='after')
    def check_dates_plausbility(self):
        header_date_str = self.supplierConfirmationData.date.value
        
        if not header_date_str:
            self.date_plausibility_status = "Warnung: Belegdatum fehlt."
            return self
        
        try:
            header_date = datetime.strptime(header_date_str, "%d.%m.%Y")
        except:
            self.date_plausibility_status = "Warnung: Belegdatum ungültig."
            return self 
        
        errors = []
        for position in self.details:
            if position.deliveryDate.date:
                try: 
                    del_date = datetime.strptime(position.deliveryDate.date, "%d.%m.%Y")
                    # Regel: Lieferdatum darf nicht vor Belegdatum sein
                    if del_date < header_date:
                        # FIX: Hier append statt raise ValueError, sonst stürzt es ab!
                        errors.append(f"Pos {position.number}: Lieferdatum {position.deliveryDate.date} vor Belegdatum")
                except ValueError:
                    pass
        if errors:
            self.date_plausibility_status = " ; ".join(errors)
        else:
            self.date_plausibility_status = "OK"

        return self
    
    #3. Check: Summen Validierung
    @model_validator(mode='after')
    def check_sum_validation(self):
        calculated_sum = sum(d.lineTotalAmount for d in self.details)
        footer_total = self.documentNetTotal

        if footer_total == 0.0:
            self.sum_validation_status = "Warnung: Footer-Summe 0.0"
            return self
        
        diff = abs(calculated_sum - footer_total)
        if diff > 1.00:
            self.sum_validation_status = f"Fehler: Summe Positionen ({calculated_sum}) != Footer ({footer_total}). Diff: {diff:.2f}"
        else:
            self.sum_validation_status = "OK"
        return self
    

class DocumentItem(BaseModel):
    supplierConfirmation: SupplierConfirmation = Field(alias="SupplierConfirmation", description="Eine extrahierte Auftragsbestätigung basierend der BA-Nummer (Beschaffungsauftragsnummer).")

class Document(BaseModel):
    documents: List[DocumentItem] = Field(description="Eine Liste aller erkannten Auftragsbestätigungen im Dokument.")


# --- Generierung des JSON Schemas ---

def generate_json_schema():
    schema_dict = Document.model_json_schema()
    
    filename = 'document_schema.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(schema_dict, f, indent=2, ensure_ascii=False)
        
    print(f"Schema erfolgreich in '{filename}' generiert.")

if __name__ == "__main__":
    generate_json_schema()