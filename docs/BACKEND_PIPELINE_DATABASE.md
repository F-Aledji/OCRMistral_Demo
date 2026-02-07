# Backend & Pipeline Dokumentation

Dieses Dokument beschreibt die technische Architektur und Funktionsweise des OCR-Backends und der Datenbank. Es richtet sich an Entwickler sowie technisch interessierte Anwender, die verstehen möchten, wie die "Magie" hinter den Kulissen funktioniert.

---

## 1. Einführung

Das System dient der automatischen Verarbeitung von eingehenden PDF-Dokumenten (primär Lieferantenbestätigungen / ABs). Ziel ist es, aus unstrukturierten PDFs strukturierte Daten (XML) für das ERP-System zu extrahieren, dabei Fehler automatisch zu erkennen und zu korrigieren.

Die Architektur ist in zwei Hauptbereiche unterteilt:
1. **Die Pipeline**: Der Prozess, der ein PDF einliest und Daten ausgibt.
2. **Die Datenbank**: Der Speicher für den aktuellen Status (Queue) und die historische Nachverfolgung (Traceability).

---

## 2. Die OCR-Pipeline (UnifiedPipeline)

Die Pipeline ist das Herzstück der Anwendung. Sie wird durch die Klasse `UnifiedPipeline` gesteuert und führt jedes Dokument durch einen mehrstufigen Prozess.

### Der Ablauf (Schritt-für-Schritt)

1. **Input Gate (Der Türsteher)**
   - **Was passiert?** Das Dokument wird auf Gültigkeit geprüft. Ist es eine PDF? Ist die Datei beschädigt?
   - **Technik:** Prüfung der Dateisignatur und Größe.

2. **Analyse & Pre-Scan (Der schnelle Blick)**
   - **Was passiert?** Das System prüft, ob das Dokument Text enthält oder ein reiner Scan (Bild) ist. Zusätzlich wird versucht, sehr schnell eine Bestellnummer (BA-Nummer) zu finden.
   - **Warum?** Wenn wir die BA-Nummer früh finden, können wir in der Datenbank nachsehen, ob wir diesen Lieferanten schon kennen und spezielle "Schablonen" (Templates) für ihn haben. Das verbessert die spätere Erkennung enorm.

3. **OCR & Extraktion (Das Lesen)**
   - **Was passiert?** Das Dokument wird an eine Hochleistungs-KI (aktuell Google Gemini 3.0 Flash) gesendet. Diese KI "liest" das Dokument und extrahiert alle relevanten Daten (Kopfdaten, Positionen, Summen) direkt in ein strukturiertes JSON-Format.
   - **Technik:** Nutzung von multimodalen LLMs (Large Language Models), die Text und Bild gleichzeitig verstehen.

4. **Validierung (Die Prüfung)**
   - **Was passiert?** Die extrahierten Daten werden gegen ein strenges Regelwerk geprüft.
     - Sind alle Pflichtfelder da?
     - Sind Datumsformate korrekt?
     - Stimmen die mathematischen Summen (Menge x Preis = Gesamt)?
   - **Technik:** Einsatz von `Pydantic`-Modellen in Python, die definieren, wie ein valides Dokument aussehen muss.

5. **Judge AI (Der Reparatur-Dienst)**
   - **Was passiert?** Wenn die Validierung Fehler findet (z.B. Summe falsch berechnet oder Datum unleserlich), wird eine zweite KI (der "Judge") eingeschaltet. Sie schaut sich den Fehler und das Original-Dokument an und versucht, den Fehler intelligent zu korrigieren.
   - **Besonderheit:** Dies ist ein "Self-Healing"-Mechanismus. Das System repariert sich selbst, bevor ein Mensch eingreifen muss.

6. **Scoring (Die Benotung)**
   - **Was passiert?** Jedes extrahierte Dokument erhält eine Schulnote (Score von 0-100).
   - **Kriterien:**
     - Lieferant bekannt? (+Punkte)
     - Mathe stimmt? (+Punkte)
     - Pflichtfelder fehlen? (-Punkte)
   - **Folge:** Dokumente mit hohem Score (z.B. >90) können vollautomatisch durchlaufen ("Dunkelverarbeitung"). Dokumente mit niedrigem Score landen zur Prüfung in der Queue.

7. **Business Repair (Die zweite Chance)**
   - **Was passiert?** Ist der Score zu niedrig (<85), darf der "Judge" noch einmal ran und versucht gezielt, die Schwachstellen zu verbessern, um den Score zu heben.

8. **Output (Das Ergebnis)**
   - **Erfolg:** Eine XML-Datei wird generiert, die vom ERP-System (z.B. SAP/Semiramis) eingelesen werden kann.
   - **Manuelle Prüfung:** Falls nötig, bleibt das Dokument in der Web-Oberfläche liegen, bis ein Mensch es freigibt.

---

## 3. Datenbank-Architektur

Die Datenbank speichert nicht nur Dokumente, sondern verfolgt den gesamten Lebenszyklus. Wir nutzen hierfür **SQLModel** (eine moderne Verbindung aus Python-Objekten und SQL-Datenbanken).

Es gibt zwei logische Bereiche in der Datenbank:

### A. Operative Daten (Für das Frontend / Queue)
Diese Tabellen steuern, was Sie aktuell auf dem Bildschirm sehen.

| Tabelle | Beschreibung |
| :--- | :--- |
| **`documents`** | Die Haupttabelle. Ein Eintrag pro hochgeladener PDF. Enthält Status (`NEW`, `OCR_DONE`, `ERROR`), Dateinamen, wer es gerade bearbeitet (`claimed_by`) und optional den verknüpften Lieferanten (`supplier_id`). |
| **`document_files`** | Verknüpft den Datenbank-Eintrag mit den echten Dateien auf der Festplatte (Original-PDF, XML). |
| **`annotations`** | Speichert die Ergebnisse der KI (wo steht was?) und Änderungen, die der Benutzer im Editor vornimmt. Jedes Speichern legt eine neue Version an (Historie). |

### B. Traceability & Analyse (Für die Langzeit-Auswertung)
Diese Tabellen speichern detaillierte Protokolle für jedes verarbeitete Dokument. Dies ist die Grundlage für Dashboards und Prozessoptimierung.

| Tabelle | Beschreibung |
| :--- | :--- |
| **`processing_run`** | Ein Protokoll-Eintrag für jeden Durchlauf einer Datei. Speichert Dauer, verwendete KI-Modelle, Fehler und ob eine "Reparatur" nötig war. |
| **`extracted_document`** | Da eine PDF mehrere Bestellungen enthalten kann, wird hier jede einzelne gefundene Bestellung (`BA-Nummer`) gespeichert. |
| **`score_penalty`** | Die "Sündenkartei". Hier wird genau gespeichert, *warum* Punkte abgezogen wurden (z.B. "-20 Punkte: Datum fehlt"). Das erlaubt Analysen wie "Welcher Fehler tritt am häufigsten auf?". |
| **`score_signal`** | Positive Signale (z.B. "Lieferant erkannt"). |

### C. Stammdaten & Konfiguration
| Tabelle | Beschreibung |
| :--- | :--- |
| **`suppliers`** | **(Neu)** Zentrale Verwaltung der Lieferanten. Speichert Name, ERP-ID und verknüpft Templates. |
| **`valid_ba_numbers`** | Simuliert die ERP-Datenbank. Verknüpft BA-Nummern mit der ERP-ID des Lieferanten. |
| **`supplier_templates`** | Speichert "Schablonen" (Koordinaten) für Lieferanten. Ist direkt mit der Tabelle `suppliers` verknüpft. |

---

## 4. Zusammenfassung für Entwickler
- **Stack:** Python 3.11+, FastAPI, SQLModel (SQLite/PostgreSQL), Pydantic.
- **Konzept:** Die `UnifiedPipeline` ist ein monolithischer Service, der modular aufgebaut ist. OCR, Validierung und Scoring sind getrennte Komponenten.
- **Datenfluss:** PDF -> Bytes -> OCR -> JSON -> Pydantic Model -> Score -> XML/DB.
