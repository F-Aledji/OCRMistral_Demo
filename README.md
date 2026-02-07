# Mistral/Gemini OCR Demo (v2)

**Fortschrittliches System zur Verarbeitung von Lieferantenbestätigungen ("Semiramis")**

Dieses Repository enthält eine produktionsreife Full-Stack-Lösung zur Extraktion, Validierung und Verarbeitung von komplexen PDF-Dokumenten (speziell Lieferantenbestätigungen). Das System setzt auf einen hybriden KI-Ansatz mit **Mistral AI** (für die primäre Extraktion) und **Google Gemini 2.0 Flash** (als "The Judge" für Validierung und Selbstkorrektur).

---

## 🚀 Hauptfunktionen (Features)

### 1. Vereinheitlichte Verarbeitungspipeline (Unified Pipeline)
Das Herzstück des Systems (`core/pipeline/unified_pipeline.py`) steuert den gesamten Lebenszyklus eines Dokuments:
-   **Pre-Scan (Fast-Pass)**: Nutzt `PyMuPDF` für eine blitzschnelle Voranalyse (z.B. Identifikation von BA-Nummern), noch bevor teure KI-Modelle zum Einsatz kommen.
-   **Template-Injektion**: Basierend auf dem Pre-Scan werden dem KI-Modell automatisch räumliche Koordinaten und Kontextinformationen ("Templates") mitgegeben, was die Erkennungsrate bei bekannten Layouts massiv erhöht.
-   **Hybride Extraktion**: Flexibler Einsatz von Mistral oder Gemini zur Umwandlung unstrukturierter PDF-Daten in sauberes JSON.

### 2. "The Judge" (Intelligente Validierung & Selbstheilung)
Eine spezialisierte Korrekturebene, die die Datenintegrität sicherstellt:
-   **Validierung**: Prüft extrahierte Daten gegen strenge Pydantic-Schemata.
-   **Selbstkorrektur**: Scheitert die Validierung, erhält "The Judge" (Gemini 2.0) die Fehlermeldungen sowie den Rohkontext, um das defekte JSON automatisch zu "heilen".
-   **Confidence Scoring**: Jedes Dokument erhält einen Vertrauenswert (0-100%), basierend auf der Vollständigkeit der Felder und der Validierungstiefe.

### 3. Moderne Full-Stack Architektur
-   **Frontend**: Entwickelt mit **Next.js 16**, **TypeScript** und **Tailwind CSS**. Bietet ein modernes Dashboard zur Überwachung der Warteschlange (Queue), sowie einen Split-View-Editor zur manuellen Korrektur mit PDF-Annotationen (Canvas/Konva).
-   **Backend**: Leistungsstarkes **FastAPI**-Backend mit modularer Router-Struktur.
-   **Datenbank**: **SQLite** (via SQLAlchemy) für einfache Deployments, strukturierte Trennung von operativen Daten und Analyse-Logs (siehe `DATABASE_PRESENTATION.md`).
-   **Containerisierung**: Vollständig dockerisiert (Frontend + Backend) für konsistente Entwicklung und Deployment.

### 4. Nachverfolgbarkeit & Audit (Traceability)
-   **Full Trace**: Jeder Schritt (Upload, OCR, Validierung, Benutzerkorrektur) wird in der `trace_entries`-Tabelle protokolliert.
-   **Dateinamen-Persistenz**: Der ursprüngliche Dateiname bleibt über den gesamten Prozess erhalten – von `input/` bis zur Archivierung.

---

## 🏗 Systemarchitektur & Datenfluss

Der Datenfluss folgt einem klaren "Two Worlds"-Konzept (Trennung von Operativem Zustand und Prozess-Log):

1.  **Upload**: Dokumente landen in der `documents`-Tabelle (Status: `NEW`).
2.  **Verarbeitung**: Der **Batch-Runner** oder API-Trigger startet die Pipeline.
3.  **KI-Analyse**: Extraktion -> Validierung -> Scoring.
4.  **Datenbank**: Ergebnisse werden gespeichert.
    -   *Erfolg*: Status `VALID`.
    -   *Fehler/Unsicher*: Status `NEEDS_REVIEW` -> "The Judge" versucht Reparatur.
5.  **Human-in-the-Loop**: Mitarbeiter prüfen und korrigieren unsichere Dokumente im Frontend.

---

## 📂 Projektstruktur

```bash
Mistral_OCR_Demo/
├── backend/                # FastAPI Server
│   ├── app/
│   │   ├── core/           # Konfiguration & Utils
│   │   ├── db.py           # Datenbank-Verbindung
│   │   ├── db_models.py    # SQLAlchemy ORM Modelle
│   │   ├── main.py         # Einstiegspunkt (Entry Point)
│   │   ├── routers/        # API Endpunkte (documents, annotations)
│   │   ├── services/       # Geschäftslogik (PreScan, OCR, Pipeline)
│   │   └── trace_models.py # Audit-Logging Modelle
│   ├── tests/              # Pytest Test-Suite
│   └── data/               # Lokaler Speicher für PDFs
├── frontend/               # Next.js 16 Applikation
│   ├── src/
│   │   ├── app/            # Pages & Routing
│   │   ├── components/     # UI Komponenten (PDFViewer, Sidebar)
│   │   └── lib/            # Utilities (API Client)
│   └── public/             # Statische Assets
├── core/                   # Geteilte Pipeline-Logik
│   ├── pipeline/           # UnifiedPipeline Logik
│   └── prompts/            # System Prompts für LLMs
├── docker-compose.yml      # Docker Orchestrierung
└── requirements.txt        # Python Abhängigkeiten
```

---

## 🛠 Installation & Start

### Voraussetzungen
-   **Python 3.10+**
-   **Node.js 20+** (für lokale Frontend-Entwicklung)
-   **Docker** (optional, empfohlen für einfachen Start)
-   **API Keys**:
    -   Google Cloud Credentials (JSON) für Gemini
    -   Mistral API Key (falls Mistral genutzt wird)

### Konfiguration
Erstellen Sie eine `.env` Datei im Hauptverzeichnis:

```env
# AI Provider Keys
GOOGLE_APPLICATION_CREDENTIALS="pfad/zu/credentials/gcp-key.json"
GEMINI_PROJECT_ID="dein-projekt-id"
MISTRAL_API_KEY="dein-mistral-key"

# Datenbank (Optional, Standard ist lokale SQLite)
DATABASE_URL="sqlite:///./backend/demo.db"
```

---

### Option A: Start mit Docker (Empfohlen)

Der einfachste Weg, das gesamte System zu starten.

1.  **Bauen und Starten**
    ```bash
    docker-compose up --build
    ```
2.  **App Aufrufen**
    -   Frontend: [http://localhost:3000](http://localhost:3000)
    -   Backend API: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option B: Manuelle lokale Entwicklung

#### 1. Backend Einrichten
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt

# Server Starten
python -m uvicorn app.main:app --reload
```
*Das Backend läuft unter `http://localhost:8000`*

#### 2. Frontend Einrichten
```bash
cd frontend
npm install

# Dev Server Starten
npm run dev
```
*Das Frontend läuft unter `http://localhost:3000`*

---

## 🖥 Bedienung

### 1. Dokumenten-Upload
-   Navigieren Sie zum Dashboard.
-   Ziehen Sie PDF-Dateien in den Upload-Bereich.
-   Der **Pre-Scan** läuft sofort an.

### 2. Pipeline-Verarbeitung
-   Nutzen Sie das **"Batch Run"** Skript oder triggern Sie die Verarbeitung über die UI.
-   Manuell über Terminal:
    ```bash
    python batch_runner.py --input "data/input"
    ```

### 3. Review & Korrektur
-   Öffnen Sie die **"Review Queue"** im Frontend.
-   Klicken Sie auf ein Dokument für den **Split-View Editor**.
-   **Links**: PDF-Viewer mit Bounding-Boxes.
-   **Rechts**: Extrahiertes Daten-Formular.
-   Korrigieren Sie Fehler und klicken Sie auf **"Approve"**.

---

## 📚 API Dokumentation

Das Backend bietet eine interaktive Swagger-Dokumentation.
Sobald der Server läuft, besuchen Sie:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

### Wichtige Endpunkte
-   `POST /api/v1/documents/upload`: Upload neuer Dokumente.
-   `GET /api/v1/documents/queue`: Abruf der Warteschlange.
-   `GET /api/v1/documents/{id}`: Detailansicht eines Dokuments.
-   `POST /api/v1/documents/{id}/claim`: Dokument für Bearbeitung sperren ("Claiming").

---

## 🤝 Mitwirken (Contributing)

1.  Feature-Branch erstellen (`git checkout -b feature/tolle-funktion`)
2.  Änderungen committen (`git commit -m 'Add tolle funktion'`)
3.  Push auf den Branch (`git push origin feature/tolle-funktion`)
4.  Pull Request öffnen

---

## 📄 Lizenz

Proprietär - Nur für internen Gebrauch.
