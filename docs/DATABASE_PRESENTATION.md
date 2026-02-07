# 🏗️ Datenbank-Architektur & Datenfluss

## 1. Das Konzept: "Zwei Welten"

Wir haben die Datenbank bewusst in zwei spezialisierte Bereiche geteilt. Das ist ein **Modernes Architektur-Pattern** (CQRS-ähnlich), das Robusheit garantiert.

### 🌍 Welt 1: Operational State (Der "Live"-Zustand)
*Hier schaut das Frontend drauf. Schnell, aktuell, reaktiv.*

| Tabelle | Funktion |
|:---|:---|
| **`documents`** | Das Herzstück. Ein Eintrag pro Vorgang. Enthält den aktuellen Status (`NEW`, `OCR_DONE`, `VALID`). |
| **`document_files`** | Das Archiv. Wo liegen die physischen Dateien? (Original PDF, XML, Annotiertes PDF). |
| **`annotations`** | Das Gedächtnis. Speichert Bounding-Boxes (Koordinaten) und Werte. Versioniert! |

### 📊 Welt 2: Process Trace (Der "Blackbox"-Recorder)
*Hier schreibt das Backend rein. Detailliert, analytisch, unveränderbar.*

| Tabelle | Funktion |
|:---|:---|
| **`processing_run`** | Ein technischer Lauf. "Batch-Verarbeitung am 07.02. um 18:00 Uhr". |
| **`extracted_document`** | Was hat die KI gefunden? (Rohdaten vor Validierung). |
| **`score_penalty`** | Warum ist der Score schlecht? (z.B. "Datum fehlt", "Summe falsch"). |
| **`score_signal`** | Was war gut? (z.B. "Lieferant im Stammbaum gefunden"). |

---

## 2. Beispiel: "Die Reise einer Rechnung" 🚀

Stellen Sie sich vor, wir laden eine Rechnung von **"Müller GmbH"** hoch. So fließen die Daten:

### Schritt 1: Der Upload (Frontend)
Der User lädt `rechnung_müller.pdf` hoch.
*   **INSERT `documents`**:
    *   `id`: `a1b2-c3d4` (Neue UUID)
    *   `status`: `NEW`
    *   `filename`: "rechnung_müller.pdf"
*   **INSERT `document_files`**:
    *   `document_id`: `a1b2-c3d4`
    *   `path`: "/data/rechnung_müller.pdf"
    *   `kind`: `ORIGINAL_PDF`

### Schritt 2: Die Analyse (Backend AI)
Der Hintergrund-Worker wacht auf.
*   **INSERT `processing_run`**:
    *   `id`: `run-99`
    *   `started_at`: 18:05:00
*   **KI arbeitet...** und findet "Müller GmbH" und Summe "500€", aber **kein Datum**.
*   **INSERT `extracted_document`**:
    *   `run_id`: `run-99`
    *   `vendor_name`: "Müller GmbH"
    *   `net_total`: 500.00
    *   `score`: 70 (Niedrig!)
    *   `frontend_document_id`: `a1b2-c3d4` (Link zurück zum Frontend-Dokument!)

### Schritt 3: Die Bewertung (Scoring)
Warum nur Score 70?
*   **INSERT `score_penalty`**:
    *   `document_id`: (ID vom extracted_document)
    *   `points`: 30
    *   `reason`: "Rechnungsdatum nicht gefunden"
    *   `category`: `MISSING_FIELD`

### Schritt 4: Die Synchronisation
Das Backend meldet dem Frontend: "Achtung, Problem!"
*   **UPDATE `documents`** (ID: `a1b2-c3d4`):
    *   `status`: `NEEDS_REVIEW`
    *   `score`: 70
    *   `vendor_name`: "Müller GmbH"

### Schritt 5: Der Mensch greift ein (Human-in-the-Loop)
Userin "Anna" sieht das Dokument in der Liste ("Needs Review").
*   **UPDATE `documents`**:
    *   `claimed_by_user_id`: "Anna" (Damit Kollege Bob es nicht auch öffnet)
*   Anna zeichnet mit der Maus einen Kasten um das Datum.
*   **INSERT `annotations`**:
    *   `document_id`: `a1b2-c3d4`
    *   `fields`: `{ "date": { "value": "07.02.2025", "bbox": [...] } }`
    *   `source`: "user"
*   **UPDATE `documents`**:
    *   `status`: `VALID` (Jetzt ist alles da!)

---

## 3. Pitch: Wie Sie die Datenbank präsentieren 🎤

Nutzen Sie diese Punkte, um Stakeholder oder Entwickler zu überzeugen:

### 💎 "Audit-Trail & Sicherheit"
> *"Wir speichern nicht nur das Endergebnis. Durch die `processing_run` und `annotations` Historie können wir jeden Entscheidungsschritt der KI und jede Korrektur des Menschen lückenlos nachvollziehen. Wir wissen genau, wer wann was geändert hat."*

### 🚀 "Skalierbarkeit durch Trennung"
> *"Wir haben operative Daten (Live-Queue) strikt von Analyse-Daten (KI-Logs) getrennt. Das bedeutet: Auch wenn wir Millonen von KI-Logs analysieren, bleibt die Benutzeroberfläche für den Sachbearbeiter blitzschnell."*

### 🛡️ "Team-Collaboration Built-in"
> *"Die Datenbank verhindert Daten-Chaos auf Code-Ebene. Durch 'Optimistic Locking' und 'Claiming' können mehrere Buchhalter gleichzeitig arbeiten, ohne sich gegenseitig Dateien wegzuschnappen oder zu überschreiben."*

### 🧠 "Explainable AI (XAI)"
> *"Wenn die KI 'Nein' sagt, wissen wir warum. Die `score_penalty` Tabelle liefert uns harte Fakten für die Statistik: Fallen 80% der Dokumente durch, weil das Datum fehlt oder weil die Qualität schlecht ist? Unsere Datenbank gibt die Antwort."*
