import streamlit as st
import os
import shutil
import config.config as cfg

st.set_page_config(page_title="System Status", page_icon="⚙️")
st.title("⚙️ System & Konfiguration")

tab1, tab2 = st.tabs(["🩺 Health Check", "📋 Konfiguration"])

# =============================================================================
# TAB 1: HEALTH CHECK
# =============================================================================
with tab1:
    if st.button("🔄 Neu prüfen", use_container_width=True):
        st.rerun()
    
    # 1. Speicherplatz
    st.subheader("💾 Speicherplatz")
    try:
        total, used, free = shutil.disk_usage(cfg.PROJECT_ROOT)
        free_gb = free // (1024**3)
        col1, col2 = st.columns(2)
        col1.metric("Freier Speicher", f"{free_gb} GB")
        if free_gb > 5:
            col2.success("OK")
        elif free_gb > 1:
            col2.warning("Knapp")
        else:
            col2.error("Kritisch!")
    except Exception as e:
        st.error(f"Fehler: {e}")

    # 2. Ordner prüfen
    st.subheader("📁 Ordner")
    all_ok = True
    for name, path in cfg.FOLDERS.items():
        exists = os.path.exists(path)
        writable = os.access(path, os.W_OK) if exists else False
        if exists and writable:
            pass  # Kein Output für OK
        else:
            st.error(f"❌ {name}: `{path}`")
            all_ok = False
    if all_ok:
        st.success("✅ Alle Ordner OK")

    # 3. APIs
    st.subheader("🌐 API Credentials")
    if cfg.GEMINI_PROJECT_ID:
        st.success(f"✅ Gemini Project: `{cfg.GEMINI_PROJECT_ID}`")
        if cfg.GEMINI_CREDENTIALS and os.path.exists(cfg.GEMINI_CREDENTIALS):
            st.success("✅ Service Account gefunden")
        elif cfg.GEMINI_CREDENTIALS:
            st.error(f"❌ Service Account fehlt: `{cfg.GEMINI_CREDENTIALS}`")
        else:
            st.warning("⚠️ Kein Service Account (Default Credentials)")
    else:
        st.error("❌ GEMINI_PROJECT_ID fehlt")
    
    if cfg.MISTRAL_API_KEY:
        st.success("✅ Mistral API Key gesetzt")
    else:
        st.warning("⚠️ Mistral API Key nicht gesetzt (optional)")

    # 4. Schema
    st.subheader("📄 Schema Dateien")
    schema_ok = True
    for fname in ["schema.json", "template.xml.j2"]:
        path = os.path.join(cfg.PROJECT_ROOT, "schema", fname)
        if os.path.exists(path):
            st.markdown(f"✅ `{fname}`")
        else:
            st.error(f"❌ `{fname}` fehlt!")
            schema_ok = False

# =============================================================================
# TAB 2: KONFIGURATION
# =============================================================================
with tab2:
    st.info("Diese Werte werden aus `config/config.py` und `.env` geladen.")
    
    st.subheader("🔑 API Keys")
    st.code(f"GEMINI_PROJECT_ID: {cfg.GEMINI_PROJECT_ID or 'nicht gesetzt'}")
    st.code(f"GEMINI_LOCATION: {cfg.GEMINI_LOCATION}")
    st.code(f"MISTRAL_API_KEY: {'***' if cfg.MISTRAL_API_KEY else 'nicht gesetzt'}")
    
    st.subheader("📁 Ordner Pfade")
    for key, path in cfg.FOLDERS.items():
        st.code(f"{key}: {path}")
    
    st.subheader("🤖 Modelle")
    st.write(f"**OCR:** `{cfg.GEMINI_OCR_MODEL}`")
    st.write(f"**LLM:** `{cfg.GEMINI_LLM_MODEL}`")
    
    st.subheader("⚙️ Processing")
    st.write(f"Retry Wait: `{cfg.RETRY_WAIT_SECONDS}s`")
    st.write(f"Polling Interval: `{cfg.POLLING_INTERVAL}s`")
    st.write(f"Log File: `{cfg.LOG_FILE}`")
