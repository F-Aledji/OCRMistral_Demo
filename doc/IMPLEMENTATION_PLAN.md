# OCR Pipeline Implementation Plan

## Ziel
Vollständige Implementierung der 7-Ebenen Pipeline für Semiramis Lieferantenbestätigungen.

---

## Proposed Changes

### Sprint 1: Data Layer

---

#### [NEW] validation/models.py

Pydantic-Modelle die exakt dem `schema.json` entsprechen:

```python
# Kernmodelle
class DateValue(BaseModel)
class Uom(BaseModel)  
class Currency(BaseModel)
class TotalQuantity(BaseModel)
class DeliveryDate(BaseModel)
class GrossPrice(BaseModel)
class CorrespondenceDetail(BaseModel)
class Detail(BaseModel)
class SupplierPartner(BaseModel)
class InvoiceSupplierData(BaseModel)
class InvoicingData(BaseModel)
class Correspondence(BaseModel)
class Type(BaseModel)
class SupplierConfirmationData(BaseModel)
class SupplierConfirmation(BaseModel)
class SupplierConfirmationRoot(BaseModel)
```

**Validatoren:**
- `date.value`: Regex `\d{2}#\d{2}#\d{4}`
- `salesConfirmation`: Darf nicht mit BA/BE/100- beginnen
- `Correspondence.number`: Regex `^BA\d{8}$`

---

#### [NEW] validation/business_rules.py

6 Funktionen aus TODO Ebene 3:

```python
def validate_sales_confirmation(value: str) -> str
def validate_ba_number(value: str) -> str
def validate_type_code(value: str) -> str
def validate_quantity(value: str) -> str
def transform_position_number(value: str) -> str
def apply_all_transformations(data: dict) -> dict
```

---

#### [NEW] config/supplier_rules.json

Template mit 2-3 Beispiel-Lieferanten:

```json
{
  "suppliers": {
    "LIEF_001": { ... },
    "LIEF_002": { ... }
  },
  "default": { "prompt_additions": "" }
}
```

---

### Sprint 2: Pipeline Core

---

#### [MODIFY] extraction/mistral_ocr_engine.py

- Lieferanten-Erkennung aus OCR-Text
- Prompt-Injection aus `supplier_rules.json`
- Retry-Logik mit `tenacity`

---

#### [NEW] pipeline/judge.py

Gemini 3.0 Integration:

```python
def judge_extraction(pdf_bytes: bytes, extracted_json: dict) -> JudgeResult
```

- PDF nativ an Gemini senden
- Vergleich mit extrahierter JSON
- Rückgabe: `audit_score`, `corrections[]`, `confirmed_fields[]`

---

#### [NEW] pipeline/confidence.py

Score-Berechnung:

```python
def calculate_confidence(
    pydantic_valid: bool,
    business_valid: bool,
    judge_result: JudgeResult
) -> ConfidenceReport
```

---

#### [NEW] pipeline/orchestrator.py

Hauptpipeline die alles verbindet:

```python
def process_document(pdf_path: str, supplier_id: str = None) -> PipelineResult
```

Durchläuft Ebene 1-6 sequentiell.

---

### Sprint 3: UI & Testing

---

#### [NEW] pages/pipeline_test.py

Streamlit-Seite für End-to-End Test:
- PDF Upload
- Zeigt jeden Pipeline-Schritt
- Confidence Score + Routing-Entscheidung

---

#### [NEW] pages/human_review.py

Review UI für `HUMAN_REQUIRED` Dokumente:
- PDF-Viewer links
- Editierbare JSON rechts
- "Übernehmen" → XML generieren

---

### Sprint 4: Production

---

#### [NEW] file_watcher.py

Watchdog-basierter File Monitor:
- Überwacht Input-Ordner
- MIME-Type Validierung
- Ruft `orchestrator.process_document()` auf

---

## Verification Plan

### Manuelle Tests

**Test 1: Pydantic Validierung**
1. Starte Python REPL: `python`
2. Importiere: `from validation.models import SupplierConfirmationRoot`
3. Lade `schema.json` und teste mit echten Daten
4. Erwartung: Valide Daten passieren, invalide werfen `ValidationError`

**Test 2: Business Rules**
1. Starte Python REPL
2. Teste jede Regel einzeln:
   - `validate_ba_number("100-BA12345678")` → `"BA12345678"`
   - `validate_type_code("074")` → `"100"`
   - `validate_quantity("10,5")` → `"0"`

**Test 3: End-to-End Pipeline**
1. Starte: `streamlit run pages/pipeline_test.py`
2. Lade eine echte Auftragsbestätigungs-PDF hoch
3. Prüfe:
   - Markdown-Extraktion korrekt?
   - JSON validiert?
   - Business Rules angewandt?
   - Confidence Score plausibel?

> [!IMPORTANT]
> Ich brauche von dir **2-3 echte PDF-Testdokumente** um die Thresholds zu kalibrieren.

---

## Projektstruktur nach Implementation

```
Mistral_OCR_Demo/
├── app.py                    # Bestehende Haupt-App
├── ocr_consistency_test.py   # Gerade erstellt
├── schema.json               # Bestehendes Schema
├── template.xml.j2           # Bestehendes Template
│
├── config/
│   └── supplier_rules.json   # [NEU] Lieferanten-Regeln
│
├── validation/
│   ├── __init__.py
│   ├── models.py             # [NEU] Pydantic-Modelle
│   └── business_rules.py     # [NEU] Transformationen
│
├── pipeline/
│   ├── __init__.py
│   ├── judge.py              # [NEU] Gemini 3.0
│   ├── confidence.py         # [NEU] Score-Berechnung
│   └── orchestrator.py       # [NEU] Hauptpipeline
│
├── pages/
│   ├── pipeline_test.py      # [NEU] Test UI
│   └── human_review.py       # [NEU] Review UI
│
├── extraction/
│   └── mistral_ocr_engine.py # [MODIFY] + Prompt-Injection
│
└── llm/
    ├── openai_test.py        # Bestehend
    └── gemini.py             # Bestehend
```

---

## Reihenfolge der Implementierung

| # | Task | Abhängigkeit |
|---|------|--------------|
| 1 | `validation/models.py` | schema.json |
| 2 | `validation/business_rules.py` | models.py |
| 3 | `config/supplier_rules.json` | - |
| 4 | Prompt-Injection in extraction | supplier_rules.json |
| 5 | `pipeline/judge.py` | Gemini API Key |
| 6 | `pipeline/confidence.py` | judge.py |
| 7 | `pipeline/orchestrator.py` | alles vorher |
| 8 | `pages/pipeline_test.py` | orchestrator |
| 9 | `pages/human_review.py` | orchestrator |
| 10 | `file_watcher.py` | orchestrator |
