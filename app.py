import streamlit as st
import os
import inspect
import json
from extraction.mistral_ocr_engine import MistralOCR
from extraction.gemini_ocr_engine import GeminiOCR
from validation.input_gate import InputGate
from validation.post_processing import enforce_business_rules, generate_xml_from_data
from jinja2 import Environment, FileSystemLoader
import dotenv

# LLM Engines
from llm.openai_llm import OpenAILLM
from llm.gemini_llm import GeminiLLM

# API Keys und Konfiguration
dotenv.load_dotenv(override=True)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GEMINI_SERVICE_ACCOUNT_PATH = os.getenv("GEMINI_SERVICE_ACCOUNT_PATH", "")
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID", "")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")

st.set_page_config(page_title="OCR Demo", layout="wide")
st.title("OCR Demo")

# =============================================================================
# Input Gate initialisieren (Validierung vor OCR)
# =============================================================================
@st.cache_resource
def get_input_gate():
    return InputGate(quarantine_dir="_quarantine")

input_gate = get_input_gate()

# OCR Modell Auswahl in der Sidebar
st.sidebar.header("Einstellungen")
ocr_model = st.sidebar.selectbox(
    "OCR Modell auswählen",
    ["Mistral OCR", "Gemini OCR"],
    index=0,
    help="Wähle das Modell für die OCR-Verarbeitung"
)

# Pipeline Modus
pipeline_mode = st.sidebar.radio(
    "Pipeline Modus",
    ["Classic (OCR -> Markdown -> LLM)", "Direct JSON (Gemini OCR only)"],
    index=0
)

if pipeline_mode == "Classic (OCR -> Markdown -> LLM)":
    llm_choice = st.sidebar.selectbox(
        "LLM Modell auswählen",
        ["OpenAI GPT", "Gemini 3 Pro"],
        index=0,
        help="Wähle das Modell für die Daten-Extraktion (JSON/XML)"
    )

    # LLM Engine Factory
    def get_llm_engine(choice):
        if choice == "OpenAI GPT":
            return OpenAILLM(PROJECT_ROOT)
        elif choice == "Gemini 3 Pro":
            return GeminiLLM(PROJECT_ROOT)
        return None

    llm_engine = get_llm_engine(llm_choice)
else:
    llm_engine = None

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
        file_bytes = uploaded_file.getvalue()
        
        # =================================================================
        # INPUT GATE - Validierung VOR API-Aufruf
        # =================================================================
        with st.spinner("🔍 Validiere Datei..."):
            validation = input_gate.validate(
                file_bytes=file_bytes,
                filename=uploaded_file.name,
                target_model=st.session_state.ocr_model  # Direkt String übergeben
            )
        
        # Validierungs-Ergebnis prüfen
        if not validation.is_valid:
            st.error(f"❌ Datei abgelehnt: {validation.error_message}")
            st.stop()
        
        # Warnungen anzeigen
        if validation.warnings:
            for warning in validation.warnings:
                st.warning(f"⚠️ {warning}")
        
        # Info über bereinigte Datei
        if validation.removed_pages:
            st.info(f"🧹 {len(validation.removed_pages)} leere Seiten entfernt (Seiten: {validation.removed_pages})")
        
        # PDF-Typ Info anzeigen
        if validation.pdf_type != "unknown":
            type_labels = {
                "digital_born": "📄 Dokument wurde digital erstellt",
                "scanned": "📷 Gescanntes Dokument",
                "mixed": "📄📷 Gemischt (Text + Scan)",
            }
            st.caption(type_labels.get(validation.pdf_type, ""))
        
            # =================================================================
            # OCR Verarbeitung
            # =================================================================
            st.info(f"Verarbeite Datei mit {st.session_state.ocr_model}...")
            
            # Verwende die bereinigte Datei (ohne leere Seiten)
            processed_bytes = validation.processed_bytes or file_bytes

            # Direct JSON Schema Load
            ocr_json_schema = None
            if pipeline_mode == "Direct JSON (Gemini OCR only)":
                if st.session_state.ocr_model != "Gemini OCR":
                    st.error("Direct JSON Mode wird nur von Gemini OCR unterstützt.")
                    st.stop()
                
                # Load Schema
                schema_path = os.path.join(PROJECT_ROOT, 'schema', 'schema.json')
                with open(schema_path, 'r', encoding='utf-8') as f:
                    ocr_json_schema = json.load(f)

            try: 
                # Unterscheiden zwischen PDF und Bild je nach Engine
                if st.session_state.ocr_model == "Mistral OCR":
                    if uploaded_file.type == "application/pdf":
                        # Mistral unterstützt aktuell kein Direct JSON - hier würde man eine Exception werfen oder fallbacken
                        ocr_result = st.session_state.ocr_engine.process_pdf(processed_bytes)
                    else:
                        ocr_result = st.session_state.ocr_engine.process_image(processed_bytes)
                    
                    # Mistral gibt ein Objekt mit .pages zurück
                    markdown_extracted = ""
                    for page in ocr_result.pages:
                        markdown_extracted += page.markdown + "\n\n"
                        
                elif st.session_state.ocr_model == "Gemini OCR":
                    # Check for Code Updates (Live-Reload Fix)
                    sig = inspect.signature(st.session_state.ocr_engine.gemini_ocr_pdf_base64)
                    if 'stream' not in sig.parameters:
                        st.warning("OCR Engine aktualisiert (neue Version erkannt). Lade neu...")
                        st.session_state.ocr_engine = get_ocr_engine(ocr_model)

                    markdown_extracted = ""
                    
                    # Determine streaming: Only valid for standard Markdown mode
                    do_stream = (pipeline_mode == "Classic (OCR -> Markdown -> LLM)")
                    
                    if do_stream:
                        st.write("### Live Output:")
                        output_place = st.empty()

                    if uploaded_file.type == "application/pdf":
                        response = st.session_state.ocr_engine.process_pdf(processed_bytes, stream=do_stream, json_schema=ocr_json_schema)
                    else:
                        response = st.session_state.ocr_engine.process_image(processed_bytes, stream=do_stream, json_schema=ocr_json_schema)
                    
                    # Output Handling
                    if do_stream:
                        for chunk in response:
                            try:
                                if chunk.text:
                                    markdown_extracted += chunk.text
                                    output_place.markdown(markdown_extracted + "▌") 
                            except Exception:
                                pass
                        output_place.markdown(markdown_extracted)
                        st.caption("Stream beendet.")
                    else:
                        # Direct JSON or Non-Streaming
                        if ocr_json_schema:
                            # Parse JSON directly from response text
                            if response.text:
                                markdown_extracted = response.text # Raw JSON string
                                json_data = json.loads(response.text)
                            else:
                                st.error("Leere Antwort von Gemini OCR (Direct JSON).")
                                json_data = {}
                        else:
                            markdown_extracted = response.text

                st.success("OCR abgeschlossen!")
                
                # =================================================================
                # Post-Processing & LLM (if needed)
                # =================================================================
                json_data_final = {}
                xml_output_final = ""

                if pipeline_mode == "Direct JSON (Gemini OCR only)":
                     # Wir haben bereits JSON (hoffentlich) in json_data
                     # Führe nun Rules + XML Gen aus
                     try:
                        if 'json_data' in locals() and json_data:
                            json_data_final = enforce_business_rules(json_data)
                            
                            # Environment für Template laden
                            env = Environment(loader=FileSystemLoader(PROJECT_ROOT))
                            xml_output_final = generate_xml_from_data(json_data_final, env)
                            
                            st.success("Direct JSON & XML Generierung erfolgreich!")
                        else:
                            st.error("JSON Konvertierung fehlgeschlagen.")
                     except Exception as e:
                         st.error(f"Fehler bei JSON/XML Verarbeitung: {e}")

                else:
                    # Classic Mode: LLM Call
                    st.info("Starte LLM Extraktion...")
                    try:
                        if llm_engine:
                            json_data_final, xml_output_final = llm_engine.extract_and_generate_xml(markdown_extracted)
                            st.success(f"LLM Verarbeitung erfolgreich ({llm_choice})!")
                        else:
                            st.error("LLM Engine nicht initialisiert.")
                    except Exception as e:
                        st.error(f"Fehler bei der LLM-Verarbeitung: {e}")
            
                # Markdown nur anzeigen im Classic Mode
                if pipeline_mode == "Classic (OCR -> Markdown -> LLM)":
                    # Markdown separat anzeigen (nur für Mistral oder Gemini Standard)
                    if st.session_state.ocr_model != "Gemini OCR" or not do_stream:
                         # Falls es nicht gestreamed wurde (z.B. Mistral), hier anzeigen
                         # Bei Gemini wurde es oben schon gestreamed.
                         pass
                    
                    # Bei Mistral müssen wir es noch anzeigen, da wir oben nur gemerkt haben
                    if st.session_state.ocr_model == "Mistral OCR":
                         st.divider()
                         st.subheader("Extrahierter Text")
                         st.divider()
                         st.markdown(markdown_extracted)

                st.divider()
                
                # JSON und XML in 2 Spalten
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("JSON")
                    st.json(json_data_final)
                
                with col2:
                    st.subheader("XML")
                    st.code(xml_output_final, language='xml')
                    
            except Exception as e:
                st.error(f"Fehler bei der OCR-Verarbeitung: {e}")
                import traceback
                st.code(traceback.format_exc())