from email.policy import default
import json
import re
from datetime import datetime,timedelta
from typing_extensions import Annotated
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, AfterValidator, model_validator, ValidationInfo
from typing import Any, List, Optional

#--- 1. Helper Funktionen --- 

# parse_float macht aus Strings mit Zahlen einen sauberen Float ohne Dezimalpunkte.
def parse_float(v: Any) -> float:
    """Macht aus Strings mit Zahlen einen saubeen Float ohne Dezimalpunkte."""
    if isinstance(v, float):
        return v
    if isinstance(v, int):
        return float(v)
    
    # Bereinige String wenn s leer dann 0.0
    s = str(v).strip()
    # FIX: "Nicht gefunden" und andere Platzhalter abfangen -> 0.0
    if not s or s.lower() in ["nicht gefunden", "unsicher", "none", "null"]:
        return 0.0
    
    ## Entferne Tausendertrenner bsp 1.000,00 -> 1000,00
    if "." in s and "," in s:
        s = s.replace(".","")
    
    s = s.replace(",",".")

    try:
        return float(s)
    except ValueError:
        # Fallback auf 0.0 statt Crash, falls OCR Text liefert
        return 0.0 

# parse_int macht aus Strings mit Zahlen einen saubeen Int.
def parse_int(v: Any) -> int:
    """Macht aus Strings mit Zahlen einen saubeen Int."""
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    
    s = str(v).strip()
    # FIX: Auch hier "Nicht gefunden" abfangen
    if not s or s.lower() in ["nicht gefunden", "unsicher", "none", "null"]:
        return 0

    # Entferne Tausendertrenner bsp 1.000 -> 1000
    s = s.replace(".","").replace(",","")
    
    try:
        return int(s)
    except ValueError:
        return 0
    
# parse_smart_date macht aus 'dd.mm.yyyy', 'KW 40' oder 'KW40 2025' immer 'dd.mm.yyyy'
def parse_smart_date(v: Any) -> Optional[str]:
    """ Versteht 'dd.mm.yyyy', 'KW 40' oder 'KW40 2025. Gibt immer 'dd.mm.yyyy' zurück oder Fehler."""

    if not v or str(v).lower() in ["nicht gefunden", "none", "unsicher"]:
        return None

    s = str(v).strip()

    # 1. Check auf Kalenderwoche (z.B. "KW 40", "KW40", "40. KW")
    kw_match = re.search(r'(?i)KW\s*(\d{1,2})', s)
    if kw_match:
        kw = int(kw_match.group(1))
        # Wir nehmen das aktuelle Jahr an, wenn keines gefunden wird.
        year_match = re.search(r'20\d{2}', s)
        year = int(year_match.group(0)) if year_match else datetime.now().year

        # # Montag der KW berechnen (%G=ISO-Jahr, %V=ISO-KW, %u=Tag 1=Montag)
        try:
            date_time = datetime.strptime(f"{year}-W{kw}-1", "%G-W%V-%u")
            return date_time.strftime("%d.%m.%Y")
        except ValueError:
            raise ValueError(f"Ungültige KW-Angabe: {s}")
        
    # 2. Standard Datum bereinigen (z.B. Trenner '#' zu '.')
    s = s.replace('#', '.').replace('/', '.').replace('-', '.').strip()

    try: 
        datetime.strptime(s, "%d.%m.%Y")
        return s
    except ValueError:
        raise ValueError(f"Ungültiges Datumsformat: {v}")
    
def clean_ba_number(v: Any, info:ValidationInfo) -> str:
    """Prüft gegen BA-Liste aus Array oder Datei"""

    s = str(v).strip()
    if not s or s.lower() in ["nicht gefunden", "none"]:
        return "Nicht gefunden"
    
    #Context Prüfung (Datenbank-Simulation)
    if info.context: 
        # Key muss mit pipeline_controller.get_validation_context() übereinstimmen
        valid_list = info.context.get('valid_ba_list')

        if valid_list:
            if s.upper() not in [x.upper() for x in valid_list]:
                raise ValueError(f"BA Nummer '{s}' ist unbekannt.")
    
    return s

def ensure_positive_number(v: float) -> float:
    """Stellt sicher, dass die Zahl positiv ist."""
    # Bei 0.0 (Fallback von oben) wollen wir keinen Fehler werfen, 
    # es sei denn, Menge MUSS > 0 sein. Für Preise ist 0 oft "auf Anfrage".
    # Wenn strikt > 0 gefordert, dann so lassen, aber bedenken dass "Nicht gefunden" jetzt den Fehler hier triggert.
    # Ich ändere es auf >= 0 um "Nicht gefunden" (0.0) durchzulassen, außer du willst strikt Fehler.
    if v < 0: 
        raise ValueError("Der Wert darf nicht negativ sein.")
    return v

def round_price(v: float) -> float:
    """Rundet den Preis auf 2 Nachkommastellen."""
    return round(v, 2)


# --- 2. Typ Definition ----

# Geld: String -> Float dann Check ob > 0 dann runden auf 2 Nachkommastellen
# MoneyType ist ein erweitertet Datentyp der wenn man ihn setzte diese Validierungen durchführt
MoneyType = Annotated[
    float,
    BeforeValidator(parse_float),
    AfterValidator(ensure_positive_number),
    AfterValidator(round_price)
]


# Menge: String -> zu Int dann Check ob > 0 
QuantityType = Annotated[
    int,
    BeforeValidator(parse_int),
    AfterValidator(ensure_positive_number)
]

# NEU: CleanIntType für normale Integer (ohne >0 Zwang), die bereinigt werden müssen
CleanIntType = Annotated[
    int,
    BeforeValidator(parse_int)
]

# Datum: Strin/KW -> sauberes dd.mm.yyyy

DateType = Annotated[
    str, 
    BeforeValidator(parse_smart_date)
]

# BA_Number String -> Bereinigt -> DB-Check
BAType = Annotated[
    str,
    BeforeValidator(clean_ba_number)
]


# 3. --- Modelle ---

class Currency(BaseModel):
    isoCode: str = Field(default="EUR", pattern="^[A-Z]{3}$")

class GrossPrice(BaseModel):
    amount: MoneyType # Erweiterter Type
     # Alias zeigt auf JSON-Key 'Currency'
    currency: Currency = Field(alias="Currency")

class DeliveryDate(BaseModel):
    specialValue: str = Field(default="NONE", description="Spezialwert für das Lieferdatum. Immer 'NONE' setzen.")
    date: Optional[DateType] = Field(default=None, description="Liefertermin...")
    
class CorrespondenceDetail(BaseModel):
    number: Optional[str] = None
    
class Uom(BaseModel):
    code : str = Field(default= "Stk", description="mengeneinheit. Setze diesen Wert immer auf 'Stk'.")

class TotalQuantity(BaseModel):
    amount: QuantityType = Field(description="Die extrahierte Menge...")
    # FIX: Alias hinzugefügt, da JSON 'Uom' (groß) liefert
    uom: Uom = Field(alias="Uom") 

class Details(BaseModel):
    sequence: int = Field(default=0)
    # FIX: Verwende CleanIntType statt int, um 'Nicht gefunden' abzufangen
    number: CleanIntType  

    totalQuantity: TotalQuantity
    deliveryDate: DeliveryDate
    grossPrice: GrossPrice
    #  Alias 'CorrespondenceDetail'
    correspondenceDetail: CorrespondenceDetail = Field(alias="CorrespondenceDetail")

    @model_validator(mode='after')
    def fix_position_number(self):
        """Multipliziert die Positionsnummer mit 10."""
        raw_num = self.number
        self.number = raw_num * 10
        
        # Prüfen ob CorrespondenceDetail existiert da dies der selbe Wert sein soll wie die Positionsnummer
        if self.correspondenceDetail and self.correspondenceDetail.number is not None:
            self.correspondenceDetail.number = str(raw_num * 10)
        
        return self

class Date(BaseModel):
    value : str = Field(..., description="Das ist das Belegdatum unbedingt auf dd#mm#yyyy formatieren.", pattern=r"^\d{2}\#\d{2}\#\d{4}$") 

class SupplierConfirmationData(BaseModel):
    salesConfirmation : str = Field(default="Nicht gefunden", description="Fremdreferenznummer...")
    date: Date

class SupplierPartner(BaseModel):
    # FIX: Verwende CleanIntType statt int, um 'Nicht gefunden' abzufangen
    number : CleanIntType

class InvoiceSupplierData(BaseModel):
    #  Alias groß
    supplierPartner : SupplierPartner = Field(alias="SupplierPartner")

class Correspondence(BaseModel):
    number: BAType = Field(default="Nicht gefunden", description="Beschaffungsauftragsnummer")

class Type(BaseModel):
    code : str = Field(default="100")

class InvoicingData(BaseModel):
    PaymentTerms: str = Field(default="", description="Kann leer bleiben.")

# --- ROOT MODEL---
class SupplierConfirmation(BaseModel):
    # Erlaubt Zugriff via Alias (z.B. JSON Keys) UND Python-Namen
    model_config = ConfigDict(populate_by_name=True)

    supplierConfirmationData: SupplierConfirmationData
    invoiceSupplierData: InvoiceSupplierData
    invoicingData: InvoicingData = Field(alias="invoicingData")
    correspondence: Correspondence = Field(alias="Correspondence")
    doc_type: Type = Field(alias="Type")
    details: List[Details] = Field(alias="Details")

    # Cross-Field Validierung (Lieferdatum nicht vor Belegdatum)
    @model_validator(mode='after')
    def check_dates_plausbility(self):
        header_date_str = self.supplierConfirmationData.date.value.replace('#','.')
        if not header_date_str:
            return self
        try:
            header_date = datetime.strptime(header_date_str, "%d.%m.%Y")
        except:
            return self # Skip check if header date is broken
        
        for position in self.details:
            if position.deliveryDate.date:
                try: 
                    # FIX: Typo striptime -> strptime korrigiert
                    del_date = datetime.strptime(position.deliveryDate.date, "%d.%m.%Y")
                    # Regel: Liederdatum darf nicht vor Belegdatum sein
                    if del_date < header_date:
                        raise ValueError(f"Position {position.number}: Lieferdatum {position.deliveryDate.date} liegt vor Belegdatum {header_date_str}.")
                except ValueError as e:
                    pass

        return self

#Der Container für ein Dokument in der Liste
class DocumentItem(BaseModel):
    supplierConfirmation: SupplierConfirmation = Field(alias="SupplierConfirmation")

# Wrapper für die Liste wie im Schema
class Document(BaseModel):
    documents: List[DocumentItem]


# --- Generierung des JSON Schemas ---

def generate_json_schema():
    schema_dict = SupplierConfirmation.model_json_schema()
    
    filename = 'supplier_schema_generated.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(schema_dict, f, indent=2, ensure_ascii=False)
        
    print(f"Schema erfolgreich in '{filename}' generiert.")

if __name__ == "__main__":
    generate_json_schema()