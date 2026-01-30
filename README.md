# OCR Pipeline - Concept of Proof

Automatisierte Verarbeitung von Lieferantenbestätigungen (PDFs) zu strukturierten XML-Dateien mittels KI-gestützter OCR und Validierung.

## Voraussetzungen

- Python 3.11+
- Google Cloud Projekt mit Vertex AI API aktiviert
- Service Account JSON mit Vertex AI Berechtigungen

## Installation

```bash
# Virtual Environment erstellen
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# oder: .venv\Scripts\activate  # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Konfiguration

Erstelle eine `.env` Datei im Projektroot (siehe `.env.example`):

```env
# Google Cloud / Vertex AI
GEMINI_PROJECT_ID=dein-projekt-id
GEMINI_LOCATION=global
GEMINI_APPLICATION_CREDENTIALS=pfad/zum/service-account.json

# Optional: Output-Pfad überschreiben
OUTPUT_PATH=/pfad/zum/output/ordner
```

## Starten

### Batch-Runner (Hauptanwendung)
Überwacht den Input-Ordner und verarbeitet PDFs automatisch:

```bash
python batch_runner.py
```

### Dashboard (Monitoring)
Streamlit-Dashboard zur Überwachung:

```bash
streamlit run app.py
```

## Ordnerstruktur

| Ordner | Beschreibung |
|--------|--------------|
| `01_Input_PDF/` | PDFs hier ablegen zur Verarbeitung |
| `03_Process_Trace/` | Debug-Daten (Markdown, JSON, XML pro Datei) |
| `98_Error_Quarantine/` | Fehlgeschlagene Dateien |
| `99_Archive_Success/` | Erfolgreich verarbeitete PDFs |

Der Output-Ordner für XMLs wird über `OUTPUT_PATH` konfiguriert.

## Pipeline-Modi

Der `PipelineController` unterstützt zwei Modi:

| Modus | Ablauf | Verwendung |
|-------|--------|------------|
| **Direct JSON** | PDF → OCR → Structured JSON Output → Validierung → XML | Standard, schneller |
| **Classic** | PDF → OCR → Markdown → LLM → JSON → Validierung → XML | Fallback bei komplexen Dokumenten |

Konfiguration in `batch_runner.py`:
```python
result = controller.process_document(file_path, pipeline_mode="Direct JSON")
```

## Architektur

```
┌─────────────────┐
│   Input PDF     │
└────────┬────────┘
         ▼
┌─────────────────┐
│   InputGate     │  Validierung (Größe, Format, Verschlüsselung)
└────────┬────────┘
         ▼
┌─────────────────┐
│   Gemini OCR    │  Extraktion mit Structured Output
└────────┬────────┘
         ▼
┌─────────────────┐
│   Pydantic      │  Schema-Validierung
└────────┬────────┘
         ▼
┌─────────────────┐
│     Judge       │  KI-gestützte Fehlerkorrektur (bei Validierungsfehlern)
└────────┬────────┘
         ▼
┌─────────────────┐
│   XML Output    │
└─────────────────┘
```

## Prompts anpassen

Komplexe System-Prompts liegen in `prompts/`:
- `ocr_extraction.txt` - OCR-Anweisungen für Gemini
- `judge_repair.txt` - Anweisungen für JSON-Reparatur

## Lizenz

Intern - Weinmann & Schanz GmbH
