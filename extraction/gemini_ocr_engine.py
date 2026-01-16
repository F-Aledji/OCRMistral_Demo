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
prompt=""

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
                        types.Part(text=prompt),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="application/pdf",
                                data=file_bytes # Übergibt die Bytes direkt
                            ),
                        )
                    ]
                )
            ]
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
                        types.Part(text=prompt),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=file_bytes # Übergibt die Bytes direkt
                            ),
                        )
                    ]
                )
            ]
        )
       
        return response