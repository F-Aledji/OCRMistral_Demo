"""
OCR Konsistenz-Test
Prüft wie konsistent Mistral OCR bei mehrfachen Aufrufen ist.
"""

import streamlit as st
import os
from difflib import SequenceMatcher, unified_diff
from extraction.mistral_ocr_engine import MistralOCR
import dotenv

dotenv.load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

st.set_page_config(
    page_title="OCR Konsistenz-Test", 
    layout="wide",
    page_icon="🔍"
)

st.title("🔍 OCR Konsistenz-Test")
st.markdown("**Prüft wie konsistent Mistral OCR bei mehrfachen API-Calls ist.**")

# Session State
if "ocr_engine" not in st.session_state:
    st.session_state.ocr_engine = MistralOCR(MISTRAL_API_KEY)

if "results" not in st.session_state:
    st.session_state.results = []

if "last_file_name" not in st.session_state:
    st.session_state.last_file_name = None


def calculate_similarity(text1: str, text2: str) -> float:
    """Berechnet Ähnlichkeit zwischen zwei Texten (0-100%)"""
    return SequenceMatcher(None, text1, text2).ratio() * 100


def get_diff_stats(text1: str, text2: str) -> dict:
    """Gibt detaillierte Diff-Statistiken zurück"""
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    
    diff = list(unified_diff(lines1, lines2, lineterm=''))
    
    added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
    removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    
    return {
        "added_lines": added,
        "removed_lines": removed,
        "total_changes": added + removed,
        "diff": '\n'.join(diff)
    }


def run_ocr(file_bytes, file_type: str, call_number: int) -> dict:
    """Führt OCR aus und gibt Markdown + Timestamp zurück"""
    import time
    
    start_time = time.time()
    
    if file_type == "application/pdf":
        result = st.session_state.ocr_engine.mistral_ocr_pdf_base64(file_bytes)
    else:
        result = st.session_state.ocr_engine.mistral_ocr_image_base64(file_bytes)
    
    end_time = time.time()
    duration = end_time - start_time
    
    markdown = ""
    for page in result.pages:
        markdown += page.markdown + "\n\n"
    
    return {
        "markdown": markdown.strip(),
        "duration_seconds": round(duration, 2),
        "timestamp": time.strftime("%H:%M:%S")
    }


# UI
col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader(
        "PDF oder Bild hochladen", 
        type=["pdf", "jpg", "jpeg", "png"]
    )
    
    num_calls = st.slider(
        "Anzahl API-Calls", 
        min_value=2, 
        max_value=5, 
        value=3,
        help="Wie oft soll Mistral OCR aufgerufen werden?"
    )
    
    run_test = st.button("🚀 Test starten", type="primary", use_container_width=True)

with col2:
    if uploaded_file:
        st.info(f"📄 Datei: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

st.divider()

# Test ausführen
if run_test and uploaded_file:
    # Reset wenn neue Datei
    if st.session_state.last_file_name != uploaded_file.name:
        st.session_state.results = []
        st.session_state.last_file_name = uploaded_file.name
    else:
        # Auch bei gleichem File resetten wenn Button geklickt
        st.session_state.results = []
    
    file_bytes = uploaded_file.getvalue()
    file_type = uploaded_file.type
    
    st.session_state.results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(num_calls):
        status_text.text(f"🔄 API-Call {i+1}/{num_calls}...")
        progress_bar.progress((i + 1) / num_calls)
        
        try:
            ocr_result = run_ocr(file_bytes, file_type, i + 1)
            st.session_state.results.append({
                "call_number": i + 1,
                "markdown": ocr_result["markdown"],
                "duration": ocr_result["duration_seconds"],
                "timestamp": ocr_result["timestamp"],
                "success": True
            })
        except Exception as e:
            st.session_state.results.append({
                "call_number": i + 1,
                "markdown": "",
                "duration": 0,
                "timestamp": "",
                "success": False,
                "error": str(e)
            })
    
    status_text.text("✅ Alle Calls abgeschlossen!")
    progress_bar.empty()

# Ergebnisse anzeigen
if st.session_state.results:
    st.subheader("📊 Ergebnisse")
    
    successful_results = [r for r in st.session_state.results if r["success"]]
    
    if len(successful_results) < 2:
        st.error("Mindestens 2 erfolgreiche Calls nötig für Vergleich!")
    else:
        # Referenz ist der erste Call
        reference = successful_results[0]["markdown"]
        
        # Similarity Scores berechnen
        similarities = []
        for i, result in enumerate(successful_results[1:], start=2):
            sim = calculate_similarity(reference, result["markdown"])
            similarities.append({
                "comparison": f"Call 1 vs Call {i}",
                "similarity": sim
            })
        
        # Durchschnittliche Konsistenz
        avg_similarity = sum(s["similarity"] for s in similarities) / len(similarities)
        
        # Score-Anzeige
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if avg_similarity >= 99:
                st.success(f"### 🟢 {avg_similarity:.1f}%")
                st.caption("Exzellente Konsistenz")
            elif avg_similarity >= 95:
                st.warning(f"### 🟡 {avg_similarity:.1f}%")
                st.caption("Gute Konsistenz")
            else:
                st.error(f"### 🔴 {avg_similarity:.1f}%")
                st.caption("Niedrige Konsistenz")
        
        with col2:
            st.metric("Erfolgreiche Calls", f"{len(successful_results)}/{len(st.session_state.results)}")
        
        with col3:
            # Zeilen-Unterschiede zum 2. Call
            if len(successful_results) >= 2:
                diff_stats = get_diff_stats(reference, successful_results[1]["markdown"])
                st.metric("Geänderte Zeilen (Call 1 vs 2)", diff_stats["total_changes"])
        
        # Timestamps anzeigen als Beweis für separate Calls
        st.divider()
        st.subheader("⏱️ API-Call Timestamps")
        timestamp_cols = st.columns(len(successful_results))
        for idx, col in enumerate(timestamp_cols):
            with col:
                r = successful_results[idx]
                st.metric(
                    f"Call {r['call_number']}", 
                    f"{r.get('timestamp', 'N/A')}",
                    f"{r.get('duration', 0)}s"
                )
        
        st.divider()
        
        # Detail-Vergleiche
        st.subheader("🔬 Detail-Vergleich")
        
        comparison_tabs = st.tabs([s["comparison"] for s in similarities])
        
        for idx, tab in enumerate(comparison_tabs):
            with tab:
                sim = similarities[idx]
                other_result = successful_results[idx + 1]
                
                st.metric("Ähnlichkeit", f"{sim['similarity']:.2f}%")
                
                if sim["similarity"] < 100:
                    diff_stats = get_diff_stats(reference, other_result["markdown"])
                    
                    st.caption(f"➕ Hinzugefügt: {diff_stats['added_lines']} Zeilen | ➖ Entfernt: {diff_stats['removed_lines']} Zeilen")
                    
                    with st.expander("📝 Diff anzeigen"):
                        st.code(diff_stats["diff"], language="diff")
                else:
                    st.success("✅ 100% identisch!")
        
        st.divider()
        
        # Alle Markdowns anzeigen
        st.subheader("📄 Alle Extraktionen")
        
        md_tabs = st.tabs([f"Call {r['call_number']}" for r in successful_results])
        
        for idx, tab in enumerate(md_tabs):
            with tab:
                st.text_area(
                    f"Markdown Call {successful_results[idx]['call_number']}", 
                    successful_results[idx]["markdown"],
                    height=400,
                    key=f"md_{idx}"
                )


# Footer
st.divider()
st.caption("💡 **Tipp**: Eine Konsistenz unter 99% deutet darauf hin, dass Mistral OCR bei diesem Dokument variiert. Mehrere Calls und Voting könnten helfen.")
