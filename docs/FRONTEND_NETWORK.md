# Frontend & Netzwerk Dokumentation

Dieses Dokument beschreibt die Benutzeroberfläche (Frontend) und die technische Infrastruktur (Netzwerk/Deployment) der OCR-Anwendung. Es erklärt, was der Benutzer sieht und wie die Systeme miteinander kommunizieren.

---

## 1. Das Frontend (Die Benutzeroberfläche)

Die Anwendung ist als moderne Web-Applikation (Single Page Application) konzipiert, sodass sie sich wie eine Desktop-Software anfühlt, aber im Browser läuft.
**Technologie:** Next.js (React Framework), TypeScript, TailwindCSS.

### A. Das Dashboard (Die Queue) - Ihr Cockpit

Das Dashboard ist der zentrale Einstiegspunkt (`/queue`). Hier haben Sie den Überblick über alle offenen und abgeschlossenen Aufgaben.

**Was sehe ich hier?**
Eine tabellarische Liste aller Dokumente, die folgende Daten live anzeigt:
1. **Status (Die Ampel)**: Zeigt farblich codiert den aktuellen Zustand.
   - `NEW` (Grau): Neu hochgeladen, wartet.
   - `OCR_RUNNING` (Blau blinkend): Die KI arbeitet gerade.
   - `NEEDS_REVIEW` (Gelb): KI ist unsicher (Score zu niedrig), bitte prüfen!
   - `VALID` (Grün): Erfolgreich erkannt, fertig für Export.
   - `ERROR` (Rot): Technischer Fehler.
2. **Qualitäts-Score**: Eine Zahl von 0-100.
   - **Grün (>85)**: Sehr sicher.
   - **Gelb (70-85)**: Unsicherheiten.
   - **Rot (<70)**: Kritisch prüfen.
3. **Metadaten**: Die wichtigsten Infos auf einen Blick (BA-Nummer, Lieferant, Summe).
4. **Bearbeiter (Claiming)**:
   - **Wichtig!** Um zu verhindern, dass zwei Kollegen gleichzeitig dasselbe Dokument bearbeiten, "sperrt" das System ein Dokument, sobald es jemand öffnet.
   - In der Spalte "Bearbeiter" sehen Sie, wer gerade daran arbeitet (oder ob es frei ist).

**Interaktionen:**
- **Upload**: Einfaches "Drop & Go" für neue PDFs.
- **OCR Starten**: Bei neuen Dokumenten kann die KI manuell gestartet werden.
- **Öffnen**: Ein Klick auf "Öffnen" sperrt das Dokument für andere und öffnet den Editor.

### B. Die Detailansicht (Der Editor)

Hier findet die eigentliche Arbeit statt, falls die KI unsicher war.

**Layout:**
- **Links (PDF Viewer)**: Das Original-Dokument wird angezeigt.
  - **Bounding Boxes**: Das System zeichnet farbige Rahmen um erkannte Texte (z.B. die BA-Nummer). So sehen Sie sofort, *wo* die KI den Wert gefunden hat.
- **Rechts (Formular)**: Die extrahierten Daten in Feldern.
  - Sie können falsche Werte korrigieren.
  - Das System speichert Ihre Korrekturen als "Annotationen" in der Datenbank. Dies hilft langfristig, das System zu trainieren (Self-Learning).

---

## 2. Netzwerk & Infrastruktur

Die Anwendung läuft in einer "Container-Umgebung" (Docker), was sie robust und leicht installierbar macht.

### Die Komponenten

Stellen Sie sich das System als drei getrennte Bausteine vor, die miteinander sprechen:

1. **Frontend Container (Port 3000)**:
   - Der Webserver, der die Benutzeroberfläche an Ihren Browser sendet.
   - Er kennt keine Datenbank, er fragt nur das Backend.

2. **Backend Container (Port 8000)**:
   - Das "Gehirn". Hier läuft die Python-Software mit der UnifiedPipeline.
   - Es hat exklusiven Zugriff auf die Datenbank und die Dateien.
   - Es kommuniziert mit der Außenwelt (Google Cloud AI).

3. **Datenbank (Intern)**:
   - Der "Aktenschrank". Hier liegen die Tabellen, die im ersten Dokument beschrieben wurden.
   - Sie ist von außen nicht direkt erreichbar (Sicherheit).

### Der Datenfluss (Netzwerk)

1. **Benutzer -> Frontend**: Sie öffnen `http://localhost:3000` im Browser.
2. **Frontend -> Backend (API)**: Wenn Sie die Seite laden, sendet das Frontend eine Anfrage an das Backend: `GET /api/documents`.
   - Das Backend antwortet mit JSON-Daten (Liste der Dokumente).
3. **Backend -> Google Cloud**: Wenn Sie "Start OCR" klicken:
   - Das Backend nimmt die PDF-Datei.
   - Es sendet eine verschlüsselte Anfrage an Google Gemini (Cloud).
   - Gemini "liest" das PDF und sendet das Ergebnis zurück.
4. **Backend -> Datenbank**: Das Ergebnis wird gespeichert.

### Deployment (Docker)

Die gesamte Anwendung wird mit einem einzigen Befehl gestartet: `docker-compose up`.
Dies erstellt ein virtuelles Netzwerk (`ocr-pipeline-network`), in dem Frontend und Backend sich gegenseitig unter ihren Namen (`frontend`, `backend`) finden können, ohne dass man IP-Adressen konfigurieren muss.

---

## 3. Zusammenfassung für Administratoren
- **Ports:** Frontend: 3000, Backend: 8000.
- **Volumes:** Daten werden persistent in `./backend/data` (Dateien) und `./backend/logs` gespeichert.
- **Sicherheit:** API-Keys (Google) liegen sicher in `.env` Dateien oder werden als Secrets gemountet. Das Backend validiert alle Eingaben (Input Gate).
