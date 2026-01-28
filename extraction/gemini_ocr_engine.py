import base64
import os
import json
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from extraction.base_ocr import BaseOCR

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

PROJECT_ID = "ocr-pipeline-weinmannschanz" # Ihre Google Cloud Projekt-ID
LOCATION = "global" # Die Region
SYSTEM_PROMPT="""Du bist ein spezialisierter OCR-Agent für die Weinmann & Schanz GmbH. Deine Aufgabe: Extraktion von Daten aus Auftragsbestätigungen mit höchster Präzision (High-Fidelity).

Kontext:

- Empfänger (Kunde) ist meist "Weinmann & Schanz".
- Absender ist der Lieferant.

BEFOLGE DIESE REGELN STRIKT:
0. **Anzahl Positionen**: Zähle alle Positionen auch Splitteile damit du einen Überblick gewinnst wie viele Positionen auf jeden Fall extrahiert werden müssen.

1. **Dokumenten-Treue:** Identifiziere und trenne die Kopfdaten strikt von den Positionsdaten.
2. **Nummern-Fokus:** Suche aggressiv nach Strings, die mit "BA", "BE" oder "100-" beginnen. "BA-Nummern" sind unsere Referenznummern zu Beschaffungsaufträge.
3. **Auftragssplit (WICHTIG):** Wenn eine Position mehrere Liefertermine/Teilmengen hat, erstelle für JEDE Teilmenge eine EIGENE Position im JSON. - Wiederhole alle Positionsdaten (Artikelnummer, Preis, Pos-Nr) in jedem Block. - Setze nur das spezifische Lieferdatum und die Teilmenge neu. - Nutze die selbe Positionsnummer (z.B. "10") für alle Teil-Blöcke.
4. **BA-Zuordnungs-Logik**: Wenn mehrere BA-Nummern vorhanden sind, nutze folgende Logik zur Zuordnung der Positionen:
- **Direkter Verweis:** Die BA steht direkt in der Positionszeile/Beschreibung.
- **Block-Trennung:** Eine BA-Nummer steht als Überschrift, gefolgt von Positionen (bis zur nächsten BA-Überschrift oder Linie).
- **Summen-Logik:** Positionen werden erst aufgezählt, und am Ende steht "zu Ihrer Bestellung BA...". In diesem Fall gehören alle darüber liegenden Positionen (bis zur vorherigen BA-Gruppe) dazu.
5. **Fehlerbehandlung:** - Feld leer? -> Schreibe "Nicht gefunden".- Unleserlich? -> Schreibe "Unsicher". - Erfinde KEINE Daten.
6. **Liefertermine:** Extrahiere das Lieferdatum pro Position. Wandle KW (Kalenderwoche) in ein konkretes Datum (Montag der KW) um.
7. **Währung:** Immer Euro.
8. **Preise:** Ohne Währungssymbol. Dezimaltrenner ist ein Komma (z.B. "12,50").
9. **Einheit:** Immer "Stk" auch wenn im Dokument andere Einheiten verwendet werden.
10. **Artikelnummern-Erkennung:** Nutze die folgende Präfix-Liste, um unsere Artikelnummern sicher zu identifizieren (Muster: PRÄFIX xxx xxx): [15, 93, 90, 80, 62, 94, 84, 83, 33, 97, 92, 70, 91, 89, 24, 98, 81, 73, 99, 72, 14, 53, 31, 82, 32, 60, 29, 85, 59, 96, 13, 45, 17, 46, 40, 20, 47, 51, 26, 63, 16, 86, 28, 61, 58, 55, 88, 95, 30, 23, 50, 54, STS, DEB, DEW, DEA, 77, FIS, FIH, DAS, STH, DAB, 10, 27, DAH, 25, MOR, 56, BA3, HFD, MOP, SFD, MON, DASR, BA4, STQ, DANHR, DASLE, DAHLE, 11, FLB, FLA, MOBPS, 52, KB3, MOH, DEE, DANLE, DALN, DALNLE, DAN, VTB, 34, 19, 79, 12]
11. **Positionsnummern-Logik:** Falls keine Nummer vorhanden, zähle selbstständig hoch (1, 2, 3...).
---
Bevor du das finale JSON erstellst, führe folgende Analyse durch:
1. Scanne das Layout: Wo stehen die BA-Nummern? (Kopfbereich vs. Positionszeilen)
2. Identifiziere Blöcke: Gibt es visuelle Trenner zwischen Positionen verschiedener Aufträge?
3. Mapping-Strategie: Für jede Position, erkläre dir selbst, warum sie zu BA-Nummer X gehört (z.B. "Steht unter Überschrift X").
4. Positions-Check: Überprüfe, ob Sequenznummern (1, 2, 3...) logisch aufeinander folgen oder ob Sprünge auf einen neuen Auftrag hindeuten."""

USER_PROMPT="Achte auf die Einhaltung der Geschäftsregeln. Extrahiere alle relevanten Daten aus dem Dokument."


#--- OCR Engine Klasse für Gemini über Google Cloud ---
class GeminiOCR(BaseOCR):
    def __init__(self, service_account_json_path, project_id, location, model_name="gemini-3-flash-preview"):
        super().__init__()
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
            logger.info(f"Google Gen AI Client (v1) erfolgreich konfiguriert für Projekt '{project_id}'.")
        except Exception as e:
            logger.error(f"Fehler bei der Konfiguration: {e}")
            raise RuntimeError(f"Google Gen AI Client konnte nicht initialisiert werden: {e}")

    def process_pdf(self, file_bytes, stream=False, json_schema=None):
        return self._process_content(file_bytes, "application/pdf", stream, json_schema)

    def process_image(self, file_bytes, stream=False, json_schema=None):
        return self._process_content(file_bytes, "image/jpeg", stream, json_schema)

    def _process_content(self, file_bytes, mime_type, stream=False, json_schema=None):
        """Interner interner Helfer zur Verarbeitung von Inhalten mit optionaler JSON-Durchsetzung"""
        
        # Config Setup
        config_args = {
            "system_instruction": SYSTEM_PROMPT,
            "thinking_config": types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
        }

        # Wenn json_schema übergeben wird, Structured Output erzwingen
        if json_schema:
            # Clean Schema similar to LLM implementation
            qs = json_schema.copy()
            if '$schema' in qs:
                del qs['$schema']
            
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = qs
            # Bei Structured Output macht Streaming oft weniger Sinn oder ist anders, 
            # aber wir lassen den Parameter durch, falls unterstützt.
        
        # Method selection
        method = self.client.models.generate_content_stream if stream else self.client.models.generate_content
        
        response = method(
            model=self.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=USER_PROMPT),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=mime_type,
                                data=file_bytes
                            ),
                        )
                    ]
                )
            ],
            config=types.GenerateContentConfig(**config_args)
        )
       
        return response

    # Legacy Aliases
    def gemini_ocr_pdf_base64(self, file_bytes, stream=False):
        return self.process_pdf(file_bytes, stream)

    def gemini_ocr_image_base64(self, file_bytes, stream=False):
        return self.process_image(file_bytes, stream)