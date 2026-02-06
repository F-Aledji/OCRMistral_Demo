# =============================================================================
# MISTRAL OCR ENGINE
# =============================================================================
#
# ZWECK:
# Wrapper für die Mistral OCR API. Nutzt Mistrals Vision-Modell für 
# Texterkennung in PDFs und Bildern.
#
# FUNKTIONSWEISE:
# 1. PDF/Bild wird zu Base64 konvertiert
# 2. Base64-String wird als Data-URL an die API gesendet
# 3. API liefert strukturierte OCR-Ergebnisse (Text, Tabellen, Bilder)
#
# VORTEILE VON MISTRAL OCR:
# - Sehr gute Tabellenerkennung
# - Schnelle Verarbeitung
# - Extraktion von Header/Footer möglich
#
# HINWEIS:
# Diese Engine wird aktuell nicht in der Hauptpipeline verwendet.
# Die Pipeline nutzt standardmäßig Gemini für Direct JSON Extraction.
# Mistral OCR ist verfügbar als Alternative für reinen OCR-Workflow.
#
# =============================================================================

import os
import json
from mistralai import Mistral
from extraction.base_ocr import BaseOCR


class MistralOCR(BaseOCR):
    """
    OCR-Engine für Mistral's Vision-API.
    
    Erbt von BaseOCR für gemeinsame Funktionen (Base64-Encoding).
    
    Beispiel:
        engine = MistralOCR(api_key="sk-...")
        result = engine.process_pdf(pdf_bytes)
        # result.pages enthält OCR-Ergebnisse pro Seite
    """
    
    def __init__(self, MISTRAL_API_KEY):
        """
        Initialisiert den Mistral-Client.
        
        Args:
            MISTRAL_API_KEY: API-Schlüssel von console.mistral.ai
        """
        super().__init__()
        self.client = Mistral(api_key=MISTRAL_API_KEY)

    def process_pdf(self, file_bytes, stream=False):
        """
        Verarbeitet ein PDF durch Mistral OCR.
        
        Args:
            file_bytes: PDF-Datei als Bytes
            stream: (Nicht unterstützt) Für Streaming-Responses
        
        Returns:
            OCRResponse-Objekt mit .pages[] Array
            Jede Seite enthält:
            - .markdown: Extrahierter Text als Markdown
            - .images: Extrahierte Bilder (Base64)
        
        API-Details:
            - model: "mistral-ocr-latest" (aktuellstes OCR-Modell)
            - extract_header/footer: Extrahiert Kopf-/Fußzeilen separat
            - include_image_base64: Bilder im Dokument werden zurückgegeben
        """
        # PDF zu Base64 konvertieren (Methode aus BaseOCR)
        base64_pdf = self.encode_bytes_to_base64(file_bytes)

        # API-Aufruf
        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                # Data-URL Format: data:<mime>;base64,<data>
                "document_url": f"data:application/pdf;base64,{base64_pdf}" 
            },
            # table_format weggelassen = Tabellen werden inline im Text angezeigt
            # Alternative: table_format="markdown" für separate Tabellen
            extract_header=True,   # Kopfzeilen separat extrahieren
            extract_footer=True,   # Fußzeilen separat extrahieren
            include_image_base64=True  # Bilder aus PDF extrahieren
        )
        return ocr_response

    # funktion um Bild als base64 zu verarbeiten
    def process_image(self, file_bytes, stream=False):
        """Impl für Mistral Image OCR."""
        
        base64_image =self.encode_bytes_to_base64(file_bytes)  

        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{base64_image}" 
            },
            # table_format weggelassen = Tabellen werden inline im Text angezeigt
            include_image_base64=True
            )
        return ocr_response

    # Legacy Aliases (für Abwärtskompatibilität, falls nötig)
    def mistral_ocr_pdf_base64(self, file_bytes):
        return self.process_pdf(file_bytes)
    
    def mistral_ocr_image_base64(self, file_bytes):
        return self.process_image(file_bytes)

    # =========================================================================
    # AUSKOMMENTIERT - Nicht in Verwendung
    # =========================================================================
    
    # # Funktion um API Anfragen als Batch zu verarbeiten   
    # def batch_mistral_ocr_pdf_base64(self, file_bytes):
    #     # Wir müssen self.client nutzen
    #     # In einem Dictionary nutzt man Doppelpunkte : statt Gleichheitszeichen =
    #     self.client.files.upload(
    #         file={
    #             "file_name": "test.jsonl", 
    #             "content": open("test.jsonl", "rb")
    #         },
    #         purpose="batch"
    #     )
    #     
    # # Funktion um den Inhalt des PDFs als Markdown zu extrahieren   
    # def get_markdown_content(self, ocr_response):
    #     # Da ocr_response ein Objekt des SDKs ist, greifen wir per .pages darauf zu
    #     markdown_text = ""
    #     for page in ocr_response.pages:
    #         markdown_text += page.markdown + "\n\n"
    #     return markdown_text.strip()