import streamlit as st
import os
from mistral_ocr_engine import MistralOCR

MISTRAL_API_KEY = "wfm9q1Wc8hUbA7CukYsD4wk3VdKwzBV1"

st.set_page_config(page_title="Mistral OCR Demo", layout="centered")
st.title("OCR Demo")

if "ocr_engine" not in st.session_state:
     st.session_state.ocr_engine = MistralOCR(MISTRAL_API_KEY)

uploaded_file = st.file_uploader("Upload a PDF or Image file", type=["pdf", "jpg", "jpeg", "png"])

    
if uploaded_file and st.button("OCR starten"):
    st.info("Verarbeite Datei mit Mistral AI OCR...")

    try: 
         file_bytes = uploaded_file.getvalue()
         
         #unterscheiden zwischen PDF und Bild
        if uploaded_file.type == "application/pdf":
            ocr_result = st.session_state.ocr_engine.mistral_ocr_pdf_base64(file_bytes) # funktionen aus der mistral_ocr_engine.py
        else:
            ocr_result = st.session_state.ocr_engine.mistral_ocr_image_base64(file_bytes) # funktionen aus der mistral_ocr_engine.py
        st.success("OCR abgeschlossen!")
    
        markdown_extracted = ""
        for page in ocr_result:
            markdown_extracted += page.markdown + "\n\n"
    
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("### Extrahierter Text (Markdown)")
            st.markdown(markdown_extracted)

        with col2:
            st.markdown("### JSON Antwort")
            st.json(ocr_result.model_dump())
            
    except Exception as e:
        st.error(f"Fehler bei der OCR-Verarbeitung: {e}")


    
        