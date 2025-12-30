import os
import json
import base64
from mistralai import Mistral


#--- OCR Engine Klasse für Mistral OCR ---
class MistralOCR:
    def __init__(self, MISTRAL_API_KEY):
        self.client = Mistral(api_key=MISTRAL_API_KEY)

    # File in Base64 kodieren
    def encode_bytes_to_base64(self,file_bytes):
        return base64.b64encode(file_bytes).decode('utf-8')
    
    # funktion um PDF als base64 zu verarbeiten
    def mistral_ocr_pdf_base64(self, file_bytes):
        base64_pdf =self.encode_bytes_to_base64(file_bytes)

        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}" 
            },
            table_format="html", # default is "markdown"
            extract_header=True, # default is False
            extract_footer=True, # default is False
            include_image_base64=True # falls gewünscht ist das Bilder extrahiert werden
        )
        return ocr_response

    def mistral_ocr_image_base64(self, file_bytes):
        
        base64_image =self.encode_bytes_to_base64(file_bytes)  

        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{base64_image}" 
            },
            # table_format="markdown",
            include_image_base64=True
            )
        return ocr_response
        