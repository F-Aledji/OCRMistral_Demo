import streamlit as st
import os
from extraction.mistral_ocr_engine import MistralOCR
import dotenv
# Import der neuen Funktion aus dem refactorten Modul
from llm.openai_test import extract_and_generate_xml

dotenv.load_dotenv()    

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

st.set_page_config(page_title="Mistral OCR Demo", layout="wide")
st.title("OCR Demo")

if "ocr_engine" not in st.session_state:
    st.session_state.ocr_engine = MistralOCR(MISTRAL_API_KEY)

uploaded_file = st.file_uploader("Datei hochladen", type=["pdf", "jpg", "jpeg", "png"])

if uploaded_file and st.button("OCR starten"):
    st.info("Verarbeite Datei mit Mistral AI OCR...")

    try: 
        file_bytes = uploaded_file.getvalue()
        
        # Unterscheiden zwischen PDF und Bild
        if uploaded_file.type == "application/pdf":
            ocr_result = st.session_state.ocr_engine.mistral_ocr_pdf_base64(file_bytes)
        else:
            ocr_result = st.session_state.ocr_engine.mistral_ocr_image_base64(file_bytes)
        
        st.success("OCR abgeschlossen! Starte LLM Extraktion...")
    
        markdown_extracted = ""
        for page in ocr_result.pages:
            markdown_extracted += page.markdown + "\n\n"
            
        # Hier rufen wir die LLM Pipeline auf
        try:
            json_data, xml_output = extract_and_generate_xml(markdown_extracted)
            st.success("LLM Verarbeitung erfolgreich!")
        except Exception as e:
            st.error(f"Fehler bei der LLM-Verarbeitung: {e}")
            json_data = {}
            xml_output = ""
    
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Extrahierter Text")
            st.markdown(markdown_extracted)

        with col2:
            st.subheader("JSON")
            st.json(json_data)
        
        with col3:
            st.subheader("XML")
            st.code(xml_output, language='xml')
            
    except Exception as e:
        st.error(f"Fehler bei der OCR-Verarbeitung: {e}")