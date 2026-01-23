import json
from pydantic import BaseModel, Field, ConfigDict
from typing import List

# --- Modelle ---

class Currency(BaseModel):
    isoCode: str = Field(default="EUR", max_length=3, pattern="^[A-Z]{3}$")

class GrossPrice(BaseModel):
    amount: float 
    # Alias zeigt auf JSON-Key 'Currency'
    currency: Currency = Field(alias="Currency")

class DeliveryDate(BaseModel):
    specialValue: str = Field(default="NONE", description="Spezialwert für das Lieferdatum. Immer 'NONE' setzen.")
    date: str = Field(description="Liefertermin...", pattern=r"^\d{2}\.\d{2}\.\d{4}$")
    
class CorrespondenceDetail(BaseModel):
    number: int = Field(description="Referenz auf die Bestellposition.")
    
class Uom(BaseModel):
    code : str = Field(default= "Stk", description="mengeneinheit. Setze diesen Wert immer auf 'Stk'.")

class TotalQuantity(BaseModel):
    amount: int = Field(description="Die extrahierte Menge...")
    uom: Uom

class Details(BaseModel):
    sequence: int = Field(default=0)
    number: int 
    totalQuantity: TotalQuantity
    deliveryDate: DeliveryDate
    grossPrice: GrossPrice
    #  Alias 'CorrespondenceDetail'
    correspondenceDetail: CorrespondenceDetail = Field(alias="CorrespondenceDetail")

class Date(BaseModel):
    value : str = Field(..., description="Belegdatum...", pattern=r"^\d{2}\.\d{2}\.\d{4}$") 

class SupplierConfirmationData(BaseModel):
    salesConfirmation : str = Field(default="Nicht gefunden", description="Fremdreferenznummer...")
    date : Date

class SupplierPartner(BaseModel):
    number : int

class InvoiceSupplierData(BaseModel):
    #  Alias groß
    supplierPartner : SupplierPartner = Field(alias="SupplierPartner")

class Correspondence(BaseModel):
    number: str = Field(default="Nicht gefunden", pattern=r"^BA\d{8}$", description="Bestellnummer...")

class Type(BaseModel):
    code : str = Field(default="100", min_length=3)

class InvoicingData(BaseModel):
    PaymentTerms: str = Field(default="", description="Muss leer bleiben.")

# --- ROOT ---
class SupplierConfirmation(BaseModel):
    # Erlaubt Zugriff via Alias (z.B. JSON Keys) UND Python-Namen
    model_config = ConfigDict(populate_by_name=True)

    supplierConfirmationData: SupplierConfirmationData
    invoiceSupplierData: InvoiceSupplierData
    
    # FIX: Feldname klein 'invoicingData', Mapping auf JSON Key 'invoicingData' (oder 'InvoicingData' falls nötig)
    # Hier war im Schema 'invoicingData' (klein) gefordert
    invoicingData: InvoicingData = Field(alias="invoicingData")
    
    # FIX: Feldname 'correspondence', Alias 'Correspondence'
    correspondence: Correspondence = Field(alias="Correspondence")
    
    # FIX: 'Type' ist ein Keyword und Klassenname -> Umbenannt in 'doc_type'
    doc_type: Type = Field(alias="Type")
    
    # FIX: Feldname 'details', Alias 'Details' -> LÖST DEN CRASH
    details: List[Details] = Field(alias="Details")


# --- Generierung des JSON Schemas ---

def generate_json_schema():
    schema_dict = SupplierConfirmation.model_json_schema()
    
    filename = 'supplier_schema_generated.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(schema_dict, f, indent=2, ensure_ascii=False)
        
    print(f"Schema erfolgreich in '{filename}' generiert.")
    # print(json.dumps(schema_dict, indent=2))

if __name__ == "__main__":
    generate_json_schema()