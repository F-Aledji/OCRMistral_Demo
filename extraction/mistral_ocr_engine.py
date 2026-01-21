import os
import json
from mistralai import Mistral
from extraction.base_ocr import BaseOCR


#--- OCR Engine Klasse für Mistral OCR ---
class MistralOCR(BaseOCR):
    def __init__(self, MISTRAL_API_KEY):
        super().__init__()
        self.client = Mistral(api_key=MISTRAL_API_KEY)

    # funktion um PDF als base64 zu verarbeiten
    def process_pdf(self, file_bytes, stream=False):
        """
        Impl für Mistral PDF OCR.
        Stream Parameter wird aktuell ignoriert/nicht unterstützt von Mistral OCR API Wrapper in dieser Form.
        """
        base64_pdf =self.encode_bytes_to_base64(file_bytes)

        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}" 
            },
            # table_format weggelassen = Tabellen werden inline im Text angezeigt
            extract_header=True,
            extract_footer=True,
            include_image_base64=True
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