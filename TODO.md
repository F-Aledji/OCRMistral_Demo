# OCR Pipeline - Semiramis Lieferantenbestätigungen

## Projekt-Vision
**Use Case:** Lieferantenbestätigungen (PDF → JSON → Semiramis XML)  
**ERP-System:** Semiramis (`com.cisag.app.purchasing.obj.SupplierConfirmation`)  
**Ziel:** < 0,1% Fehlerrate bei automatischer Verarbeitung

---

# PIPELINE-ARCHITEKTUR

```
EBENE 0: INPUT           → File-Handling, Validierung
    ↓
EBENE 1: EXTRACTION      → Mistral OCR + Lieferanten-Prompts
    ↓
EBENE 2: PYDANTIC        → Strukturelle Typ-Validierung
    ↓
EBENE 3: BUSINESS LOGIC  → Schema-spezifische Regeln
    ↓
EBENE 4: GEMINI JUDGE    → PDF-native Korrektur & Verifikation
    ↓
EBENE 5: CONFIDENCE      → Score-Aggregation & Routing
    ↓
EBENE 6: OUTPUT          → XML-Generierung + Human Review
    ↓
EBENE 7: SELF-LEARNING   → Feedback-Loop für Verbesserung
```

---

# EBENE 0: INPUT & FILE HANDLING

## Das Problem
PDFs kommen aus verschiedenen Quellen: Scanner, Email-Attachments, manuelle Uploads. Nicht jede Datei mit `.pdf`-Endung ist ein valides PDF. Manipulierte oder korrupte Dateien können das System crashen oder Sicherheitslücken öffnen.

## Unsere Lösung
Ein File-Watcher überwacht einen Eingabe-Ordner. Jede neue Datei wird geprüft:
- **MIME-Type Check**: Ist es wirklich ein PDF (nicht nur umbenannte .exe)?
- **Größen-Limit**: PDFs > 50MB werden abgelehnt (API-Limits, Memory)
- **Seiten-Limit**: Auftragsbestätigungen haben selten > 10 Seiten

## Warum wichtig für uns?
Semiramis-Import crasht bei invaliden XMLs. Garbage-In = Garbage-Out. Wir filtern früh.

## Status
- [ ] Watchdog File-Monitor implementieren
- [ ] MIME-Type Validierung (python-magic)
- [ ] Error-Folder für abgelehnte Dateien
- [ ] Logging aller eingehenden Dateien

---

# EBENE 1: EXTRACTION (Mistral OCR + Lieferanten-Regeln)

## Das Problem
Jeder Lieferant hat ein anderes Dokument-Layout:
- Lieferant A: Bestellnummer steht oben rechts als "BA12345678"
- Lieferant B: Bestellnummer heißt "Order-No." und hat Präfix "100-"
- Lieferant C: Datum im Format "12/31/2026" statt "31.12.2026"

Ein generischer Prompt funktioniert nicht für alle. Das LLM muss wissen, WAS es bei DIESEM Lieferanten suchen soll.

## Unsere Lösung
**Lieferanten-spezifische Prompt-Injection** über `supplier_rules.json`:

```json
{
  "suppliers": {
    "LIEF_001": {
      "name": "Mustermann GmbH",
      "identifiers": ["Mustermann", "MU-"],
      "prompt_additions": "Bei diesem Lieferanten: Die BA-Nummer hat immer Präfix '100-' der entfernt werden muss. Datum ist im Format DD.MM.YYYY.",
      "field_mappings": {
        "salesConfirmation": "Auftragsbestätigung Nr.",
        "Correspondence.number": "Ihre Bestellung"
      }
    }
  }
}
```

## Schema-spezifische Extraktion
Aus deinem `schema.json` müssen folgende Felder extrahiert werden:

| Feld | Beschreibung | Spezialregeln |
|------|--------------|---------------|
| `salesConfirmation` | Fremdreferenznummer | NICHT BA/BE/100- Präfixe! |
| `date.value` | Belegdatum | Format: `dd#mm#yyyy` |
| `SupplierPartner.number` | Lieferantennummer | **EXTERN INJIZIERT** - nicht aus PDF! |
| `Correspondence.number` | BA-Nummer | Format: `BA` + 8 Ziffern |
| `Type.code` | 3-stelliger Code | Fallback: "100", "074"→"100" |
| `Details[].number` | Positionsnummer | Wird später ×10 multipliziert |
| `Details[].totalQuantity.amount` | Menge | Bei Dezimalstellen → 0 setzen |
| `Details[].deliveryDate.date` | Lieferdatum | Format: `dd#mm#yyyy` |
| `Details[].grossPrice.amount` | Einzelpreis | Float-Format |

## Warum wichtig für uns?
Das Schema hat sehr spezifische Formatierungsregeln (z.B. `dd#mm#yyyy` mit Hash statt Punkt). Ohne lieferantenspezifische Prompts ist die Fehlerrate zu hoch.

## Status
- [x] Mistral OCR Basis funktioniert
- [ ] `supplier_rules.json` erstellen
- [ ] Lieferanten-Erkennung aus Dokument
- [ ] Prompt-Injection implementieren
- [ ] Retry-Logik mit tenacity

---

# EBENE 2: STRUKTURELLE VALIDIERUNG (Pydantic)

## Das Problem
LLMs liefern manchmal:
- Falsche Typen: `"10,5"` statt `10.5` für Zahlen
- Fehlende Pflichtfelder: `Correspondence.number` ist leer
- Ungültige Formate: Datum als `2026-01-10` statt `10#01#2026`

## Unsere Lösung
Pydantic-Modelle die exakt dem `schema.json` entsprechen:

```python
class SupplierConfirmationData(BaseModel):
    salesConfirmation: str
    date: DateValue
    
    @field_validator('salesConfirmation')
    def no_ba_prefix(cls, v):
        if v.startswith(('BA', 'BE', '100-')):
            raise ValueError(f"salesConfirmation darf nicht mit BA/BE/100- beginnen: {v}")
        return v

class DateValue(BaseModel):
    value: str
    
    @field_validator('value')
    def validate_date_format(cls, v):
        # Muss dd#mm#yyyy sein
        if not re.match(r'\d{2}#\d{2}#\d{4}', v):
            raise ValueError(f"Datum muss dd#mm#yyyy sein: {v}")
        return v
```

## Warum wichtig für uns?
- **Schnell**: Pydantic validiert in Millisekunden, kostet nichts
- **Deterministisch**: Gleicher Input = Gleiches Ergebnis (LLMs variieren)
- **Frühe Fehler**: Kaputte Daten werden sofort erkannt, bevor teure Checks laufen

## Status
- [ ] Pydantic-Modelle für alle Schema-Felder
- [ ] Custom Validators für Semiramis-Formate
- [ ] Datumsformat-Konvertierung (dd.mm.yyyy → dd#mm#yyyy)

---

# EBENE 3: BUSINESS LOGIC VALIDIERUNG

## Das Problem
Selbst wenn alle Felder das richtige Format haben, können sie logisch falsch sein:
- BA-Nummer existiert nicht im ERP
- Positionsnummer × 10 ergibt ungültige Nummer
- Lieferdatum liegt vor Bestelldatum

## Schema-abgeleitete Business Rules

### Regel 1: salesConfirmation Filter
```python
def validate_sales_confirmation(value):
    """FILTER: Ignoriere Strings, die mit 'BA', 'BE' oder '100-' beginnen"""
    if value.startswith(('BA', 'BE', '100-')):
        return "Nicht gefunden"  # Fallback laut Schema
    return value
```

### Regel 2: BA-Nummer Format
```python
def validate_ba_number(value):
    """Format: Beginnt mit 'BA' + 8 Ziffern. Präfixe entfernen."""
    # Entferne Präfixe wie "100-"
    cleaned = re.sub(r'^100-', '', value)
    if not re.match(r'^BA\d{8}$', cleaned):
        raise ValueError(f"BA-Nummer ungültig: {cleaned}")
    return cleaned
```

### Regel 3: Type.code Mapping
```python
def validate_type_code(value):
    """3-stelliger Code. Fallback '100'. Ausnahme: '074' wird zu '100'."""
    if value == '074':
        return '100'
    if not value or len(value) != 3:
        return '100'  # Fallback
    return value
```

### Regel 4: Mengen-Dezimalstellen
```python
def validate_quantity(value):
    """Bei Dezimalstellen → 0 setzen (laut Schema-Kommentar)"""
    amount = float(value.replace(',', '.'))
    if amount != int(amount):  # Hat Dezimalstellen
        return "0"
    return str(int(amount))
```

### Regel 5: Positionsnummer × 10
```python
def transform_position_number(value):
    """Python multipliziert dies später mit 10 (laut Schema)"""
    return str(int(value) * 10)
```

### Regel 6: CorrespondenceDetail = Positionsnummer
```python
def validate_correspondence_detail(item):
    """CorrespondenceDetail.number soll identisch zur Positionsnummer sein"""
    if item['CorrespondenceDetail']['number'] != item['number']:
        raise ValueError("CorrespondenceDetail.number != Positionsnummer")
```

## Warum wichtig für uns?
Diese Regeln stehen direkt in deinem `schema.json` als Kommentare. Ohne sie würde Semiramis die XML ablehnen oder falsche Daten importieren.

## Status
- [ ] Alle Schema-Regeln als Python-Funktionen
- [ ] salesConfirmation Filter
- [ ] BA-Nummer Bereinigung
- [ ] Type.code Mapping (074→100)
- [ ] Mengen-Dezimalstellen-Check
- [ ] Position × 10 Transformation

---

# EBENE 4: GEMINI 3.0 JUDGE (PDF-Native Korrektur)

## Das Problem
Mistral OCR macht Fehler. Wir brauchen eine zweite Meinung. Aber GPT kann keine PDFs direkt lesen – man müsste erst in Bilder konvertieren.

## Unsere Lösung: Gemini 3.0
**Gemini 3.0** (Januar 2026) hat:
- **PDF-native Verarbeitung**: Kein Umweg über Bilder
- **2M Token Kontext**: Größtes Fenster aller Modelle
- **Multimodal**: Versteht Layout und Text gleichzeitig

### Workflow
```
1. Mistral extrahiert JSON aus PDF
2. Gemini 3.0 bekommt:
   - Das Original-PDF (nativ!)
   - Die extrahierte JSON
   - Frage: "Stimmt das überein?"
3. Gemini korrigiert ODER bestätigt
```

### Judge Prompt
```python
JUDGE_PROMPT = """
Du bist ein QA-Auditor für Semiramis Lieferantenbestätigungen.

AUFGABE:
1. Lies das PDF der Auftragsbestätigung
2. Vergleiche mit der extrahierten JSON
3. Prüfe besonders:
   - salesConfirmation: Ist es die Fremdreferenz (NICHT die BA-Nummer)?
   - date.value: Ist es das BELEGDATUM (nicht Lieferdatum)?
   - Correspondence.number: Beginnt mit BA + 8 Ziffern?
   - Alle Positionen: Stimmen Mengen und Preise?

EXTRAHIERTE JSON:
{json_data}

ANTWORT-FORMAT:
{
  "audit_score": 0-100,
  "corrections": [
    {"field": "...", "extracted": "...", "correct": "...", "reason": "..."}
  ],
  "confirmed_fields": ["salesConfirmation", "date.value", ...]
}
"""
```

## Warum wichtig für uns?
- **Halluzinations-Check**: Wenn Mistral etwas erfindet, findet Gemini es
- **Korrektur statt nur Fehler**: Gemini liefert den richtigen Wert zurück
- **Schema-Verständnis**: Gemini kennt unsere Semiramis-Regeln

## Status
- [ ] Gemini 3.0 API Integration
- [ ] PDF-Upload an Gemini
- [ ] Judge-Prompt mit Schema-Regeln
- [ ] Korrektur-Merge in JSON

---

# EBENE 5: CONFIDENCE SCORING & ROUTING

## Das Problem
Nicht jedes Dokument braucht menschliche Prüfung. Aber wie entscheiden wir automatisch?

## Score-Komponenten (aus unserem Schema abgeleitet)

### 1. Pflichtfeld-Score (25%)
Sind alle required Felder vorhanden?
```python
REQUIRED_FIELDS = [
    "salesConfirmation",
    "date.value",
    "SupplierPartner.number",
    "Correspondence.number",
    "Type.code",
    "Details"  # Mindestens 1 Position
]
score = (gefundene_felder / len(REQUIRED_FIELDS)) * 100
```

### 2. Format-Score (25%)
Entsprechen Werte den Schema-Formaten?
```python
FORMAT_RULES = {
    "date.value": r'\d{2}#\d{2}#\d{4}',
    "Correspondence.number": r'^BA\d{8}$',
    "Type.code": r'^\d{3}$'
}
```

### 3. Business-Logic-Score (25%)
Bestehen alle Regeln aus Ebene 3?
- salesConfirmation hat kein BA/BE/100- Präfix?
- Type.code 074→100 korrekt gemappt?
- Mengen-Dezimalstellen behandelt?

### 4. Gemini-Judge-Score (25%)
Audit-Score vom Gemini Judge (0-100)

### Routing-Entscheidung

| Gesamt-Score | Entscheidung | Aktion |
|--------------|--------------|--------|
| ≥ 95% | `AUTO_PROCESS` | Direkt XML generieren → Semiramis |
| 80-95% | `REVIEW_SAMPLE` | XML generieren, Stichprobe prüfen |
| < 80% | `HUMAN_REQUIRED` | In Review-Queue, keine XML |

## Status
- [ ] Score-Berechnung implementieren
- [ ] Gewichtung kalibrieren
- [ ] Thresholds mit echten Dokumenten testen

---

# EBENE 6: OUTPUT & HUMAN-IN-THE-LOOP

## Das Problem
Semiramis braucht exakt formatiertes XML. Bei unsicheren Dokumenten müssen Mitarbeiter korrigieren können.

## XML-Generierung
Wir haben bereits `template.xml.j2` - das Jinja2-Template für Semiramis-Import.

### Post-Processing vor XML
```python
def prepare_for_xml(data):
    """Wende alle Transformationen an bevor XML generiert wird"""
    
    # Position × 10
    for item in data['Details']:
        item['number'] = str(int(item['number']) * 10)
        item['CorrespondenceDetail']['number'] = item['number']
    
    # Mengen mit Dezimalstellen → 0
    for item in data['Details']:
        amount = float(item['totalQuantity']['amount'].replace(',', '.'))
        if amount != int(amount):
            item['totalQuantity']['amount'] = "0"
    
    # Datum-Format: dd.mm.yyyy → dd#mm#yyyy
    data['date']['value'] = data['date']['value'].replace('.', '#')
    
    return data
```

## Human Review UI
Für `HUMAN_REQUIRED` Dokumente:
- PDF-Ansicht links
- Editierbare JSON rechts
- Highlighting der unsicheren Felder
- "Übernehmen" → XML generieren

## Status
- [ ] Post-Processing Funktionen
- [ ] Streamlit Review-UI
- [ ] Korrektur-Workflow

---

# EBENE 7: SELF-LEARNING & FEEDBACK LOOP

## Das Problem
Das System wird nie perfekt starten. Aber es sollte besser werden.

## Feedback-Datensammlung
```python
class CorrectionLog(BaseModel):
    document_id: str
    supplier_id: str
    timestamp: datetime
    original_extraction: dict
    human_correction: dict
    changed_fields: list[str]
```

## Lern-Mechanismen

### 1. Lieferanten-Regel-Ableitung
Wenn Lieferant X immer das gleiche Feld falsch hat:
→ Automatisch neue Regel in `supplier_rules.json`

### 2. Prompt-Optimierung
Sammle erfolgreiche Korrekturen → Verbessere Base-Prompt

### 3. Schwellwert-Anpassung
Wenn zu viele AUTO_PROCESS Dokumente korrigiert werden müssen:
→ Threshold von 95% auf 97% erhöhen

### 4. Performance-Dashboard
- Fehlerrate pro Lieferant
- Häufigste Korrektur-Felder
- Trend über Zeit

## Status
- [ ] CorrectionLog Speicherung
- [ ] Analyse-Dashboard
- [ ] Automatische Regel-Vorschläge

---

# TECHNOLOGIE-STACK

| Komponente | Technologie | Version |
|------------|-------------|---------|
| OCR / Extraktion | Mistral OCR | latest |
| LLM Judge / Korrektur | **Gemini 3.0** | 2026 |
| Alternative LLM | GPT 5.2 | 2026 |
| Validierung | Pydantic | 2.5+ |
| Template Engine | Jinja2 | 3.1+ |
| File Watcher | Watchdog | 4.0+ |
| UI | Streamlit | 1.30+ |
| Retry-Logik | Tenacity | 8.2+ |

---

# PRIORISIERUNG

## Phase 1: Foundation (Diese Woche)
- [ ] `supplier_rules.json` Template
- [ ] Pydantic-Modelle für Schema
- [ ] Business Logic Funktionen

## Phase 2: Validation (Nächste Woche)
- [ ] Gemini 3.0 Judge Integration
- [ ] Confidence Score Berechnung
- [ ] Routing-Logik

## Phase 3: Production (Danach)
- [ ] File Watcher
- [ ] Human Review UI
- [ ] XML Post-Processing

## Phase 4: Learning (Zukunft)
- [ ] Feedback-Loop
- [ ] Performance-Dashboard
- [ ] Auto-Regel-Generierung
