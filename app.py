import streamlit as st
import os
from extraction.mistral_ocr_engine import MistralOCR
from extraction.gemini_ocr_engine import GeminiOCR
import dotenv
# Import der neuen Funktion aus dem refactorten Modul

from llm.openai_test import extract_and_generate_xml

# API Keys und Konfiguration
dotenv.load_dotenv(override=True)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GEMINI_SERVICE_ACCOUNT_PATH = os.getenv("GEMINI_SERVICE_ACCOUNT_PATH", "")
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID", "")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")

st.set_page_config(page_title="OCR Demo", layout="wide")
st.title("OCR Demo")

# OCR Modell Auswahl in der Sidebar
st.sidebar.header("Einstellungen")
ocr_model = st.sidebar.selectbox(
    "OCR Modell auswählen",
    ["Mistral OCR", "Gemini OCR"],
    index=0,
    help="Wähle das Modell für die OCR-Verarbeitung"
)

# OCR Engine basierend auf Auswahl initialisieren
def get_ocr_engine(model_name):
    if model_name == "Mistral OCR":
        return MistralOCR(MISTRAL_API_KEY)
    elif model_name == "Gemini OCR":
        if not GEMINI_PROJECT_ID:
            st.sidebar.error("Gemini erfordert GEMINI_PROJECT_ID in .env")
            return None
        return GeminiOCR(GEMINI_SERVICE_ACCOUNT_PATH, GEMINI_PROJECT_ID, GEMINI_LOCATION)
    return None

# Engine bei Modellwechsel neu initialisieren
if "ocr_model" not in st.session_state or st.session_state.ocr_model != ocr_model:
    st.session_state.ocr_model = ocr_model
    st.session_state.ocr_engine = get_ocr_engine(ocr_model)

uploaded_file = st.file_uploader("Datei hochladen", type=["pdf", "jpg", "jpeg", "png"])

if uploaded_file and st.button("OCR starten"):
    if st.session_state.ocr_engine is None:
        st.error("OCR Engine konnte nicht initialisiert werden. Bitte Konfiguration prüfen.")
    else:
        st.info(f"Verarbeite Datei mit {st.session_state.ocr_model}...")

        try: 
            file_bytes = uploaded_file.getvalue()
            
            # Unterscheiden zwischen PDF und Bild je nach Engine
            if st.session_state.ocr_model == "Mistral OCR":
                if uploaded_file.type == "application/pdf":
                    ocr_result = st.session_state.ocr_engine.mistral_ocr_pdf_base64(file_bytes)
                else:
                    ocr_result = st.session_state.ocr_engine.mistral_ocr_image_base64(file_bytes)
                
                # Mistral gibt ein Objekt mit .pages zurück
                markdown_extracted = ""
                for page in ocr_result.pages:
                    markdown_extracted += page.markdown + "\n\n"
                    
            elif st.session_state.ocr_model == "Gemini OCR":
                if uploaded_file.type == "application/pdf":
                    response = st.session_state.ocr_engine.gemini_ocr_pdf_base64(file_bytes)
                else:
                    response = st.session_state.ocr_engine.gemini_ocr_image_base64(file_bytes)
                # Gemini gibt ein Response-Objekt zurück, Text extrahieren
                markdown_extracted = response.text
            
            st.success("OCR abgeschlossen! Starte LLM Extraktion...")
            
            # Hier rufen wir die LLM Pipeline auf
            try:
                json_data, xml_output = extract_and_generate_xml(markdown_extracted)
                st.success("LLM Verarbeitung erfolgreich!")
            except Exception as e:
                st.error(f"Fehler bei der LLM-Verarbeitung: {e}")
                json_data = {}
                xml_output = ""
        
            # Markdown separat anzeigen
            st.divider()
            st.subheader("Extrahierter Text")
            st.divider()

            st.markdown(markdown_extracted)
            
            st.divider()
            
            # JSON und XML in 2 Spalten
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("JSON")
                st.json(json_data)
            
            with col2:
                st.subheader("XML")
                st.code(xml_output, language='xml')
                
        except Exception as e:
            st.error(f"Fehler bei der OCR-Verarbeitung: {e}")