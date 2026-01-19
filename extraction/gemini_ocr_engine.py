import base64
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

PROJECT_ID = "ocr-pipeline-weinmannschanz" # Ihre Google Cloud Projekt-ID
LOCATION = "global" # Die Region
SYSTEM_PROMPT=""
USER_PROMPT=""" Du bist ein spezialisierter OCR-Agent für die Weinmann & Schanz GmbH. Deine Aufgabe: Extraktion von Daten aus Auftragsbestätigungen mit höchster Präzision (High-Fidelity).

Kontext: 
- Empfänger (Kunde) ist meist "Weinmann & Schanz".
- Absender ist der Lieferant.

BEFOLGE DIESE REGELN STRIKT:
1. **Layout-Treue:** Trenne Kopfdaten strikt von der Positionstabelle.
2. **Tabellen-Logik:** Fasse mehrzeilige Artikelbeschreibungen in einer Zelle zusammen.
3. **Nummern-Fokus:** Suche aggressiv nach Strings, die mit "BA", "BE" oder "100-" beginnen.Es werden die Artikelnummer vom Lieferanten und gelegentlich unsere Nummer angegeben bitte die Nummer unter "Ihre Artikelnummer" ausgeben. "BA-Nummern" sind unsere Referenznummern.
4. **Auftragssplit (WICHTIG):** Wenn eine Position mehrere Liefertermine/Teilmengen hat, erstelle für JEDE Teilmenge eine EIGENE Tabellenzeile. Kopiere Artikelnummer/Preis in die neue Zeile, aber setze das spezifische Lieferdatum und die Teilmenge. Nutze die selbe Positionsnummer für alle Teilmengen.
*Beispiel Input:*
   "Pos 10: Artikel XYZ, Gesamt 100 Stk.
    Lieferung: 40 Stk am 12.02.2026, 60 Stk am 20.02.2026."
   
   *Dein Output in der Tabelle:*
   | 10 | XYZ | Artikel XYZ (Teillieferung) | 40 | Stk | 12.02.2026 | ... |
   | 10 | XYZ | Artikel XYZ (Teillieferung) | 60 | Stk | 20.02.2026 | ... |

   -> WICHTIG: Wiederhole die Positionsnummer, Artikelnummer und Preise in der neuen Zeile.
5. **Mehrere Referenznummern:** Falls mehrere "BA-..." Nummern existieren, liste ALLE auf, getrennt durch Komma.
6. **Fehlerbehandlung:**
   - Feld leer? -> Schreibe "Nicht gefunden".
   - Unleserlich? -> Schreibe "Unsicher".
   - Erfinde KEINE Daten.
7. **Liefertermine:** Extrahiere das Lieferdatum pro Position, NICHT das Belegdatum. Oft wird die KW angegeben, rechne diese in ein konkretes Datum um (Montag der KW).
8. **Währung:** Währung immer in Euro.
9. **Preise:** Preise immer ohne Währungszeichen und ohne Tausendertrennzeichen (Punkt). Dezimaltrenner ist ein Komma.
10. **Einheit:** Einheit immer nur in "Stk". Auch wenn abweichende Einheiten im Beleg stehen.
11. **Rabatte:** Berechne die Rabatte nicht selbst aus. Der Endpreis nach Rabatt wird in der Regel angegeben bzw. der Rabattbetrag wird angegeben.
11. **Output:** Nur reines Markdown. Kein Intro oder Outro. KEINE ERKLÄRUNGEN ODER HINWEISE. HALTE DICH GENAU AN DAS FORMAT.

Strukturvorgabe:

## Kopfdaten
- **Belegnummer:** Vom Lieferanten vergebene Auftragsbestätigungsnummer
- **Datum:** [dd.mm.yyyy]
- **Lieferant:** [Name, Ort]
- **Kunde:** [Name, Ort]
- **Referenz:** [BA-Nummer(n)]

## Positionen
| Pos | Art-Nr. | Beschreibung | Menge | Einheit | Liefertermin | Einzelpreis | Gesamtpreis |
|---|---|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... | ... | ... |

## Beträge
- **Nettbetrag:**
- **Steuer (MwST. Betrag):**
- **Bruttobetrag:**
- **Währung:** 
- **Zahlungsbedingungen:**"""


#--- OCR Engine Klasse für Gemini über Google Cloud ---
class GeminiOCR:
    def __init__(self, service_account_json_path, project_id, location, model_name="gemini-3-pro-preview"):
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        if project_id:
            os.environ["PROJECT_ID"] = project_id
        # Falls ein expliziter Pfad übergeben wird, als GOOGLE_APPLICATION_CREDENTIALS setzen
        if service_account_json_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_json_path
        
        # Initialisierung des neuen Google Gen AI Clients
        try:
            self.client = genai.Client(
                vertexai=True, 
                project=project_id, 
                location=location
            )
            print(f"Google Gen AI Client (v1) erfolgreich konfiguriert für Projekt '{project_id}'.")
        except Exception as e:
            print(f"Fehler bei der Konfiguration: {e}")
            exit()

    def gemini_ocr_pdf_base64(self, file_bytes):
        # Die Verschachtelung folgt exakt deinem Dokumentations-Beispiel
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=USER_PROMPT),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="application/pdf",
                                data=file_bytes # Übergibt die Bytes direkt
                            ),
                        )
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
                ,thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.LOW)
                )
        )
       
        return response

    def gemini_ocr_image_base64(self, file_bytes):
        # Die Verschachtelung folgt exakt deinem Dokumentations-Beispiel
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=USER_PROMPT),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=file_bytes # Übergibt die Bytes direkt
                            ),
                        )
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
                ,thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.LOW)
                )
        )
       
        return response