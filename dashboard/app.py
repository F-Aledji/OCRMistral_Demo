import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
import plotly.graph_objects as go

# HACK: Fix für pysqlite3 issues in manchen Environments
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# Seite konfigurieren
st.set_page_config(
    page_title="Mistral OCR Analytics",
    page_icon="📈",
    layout="wide"
)

# === DATENBANK VERBINDUNG ===

def get_db_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "..", "backend", "demo.db")
    return os.path.abspath(db_path)

DB_PATH = get_db_path()

def migrate_db(conn):
    """Fügt fehlende Spalten hinzu (Lazy Migration)."""
    cursor = conn.cursor()
    
    # Prüfe ob Spalten existieren
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(processing_run)")]
    
    if "is_scanned" not in columns:
        try:
            cursor.execute("ALTER TABLE processing_run ADD COLUMN is_scanned BOOLEAN DEFAULT 0")
            cursor.execute("ALTER TABLE processing_run ADD COLUMN file_size_bytes INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE processing_run ADD COLUMN page_count INTEGER DEFAULT 0")
            conn.commit()
            st.toast("Datenbank-Schema aktualisiert (neue Metriken)", icon="🛠️")
        except Exception as e:
            st.error(f"Migration fehlgeschlagen: {e}")
            
    # Prüfe extracted_document (has_template)
    doc_cols = [row[1] for row in cursor.execute("PRAGMA table_info(extracted_document)")]
    if "has_template" not in doc_cols:
        try:
            cursor.execute("ALTER TABLE extracted_document ADD COLUMN has_template BOOLEAN DEFAULT 0")
            conn.commit()
            st.toast("Schema aktualisiert: has_template", icon="✅")
        except:
            pass

@st.cache_data(ttl=30)
def load_data():
    if not os.path.exists(DB_PATH):
        return None, None
        
    conn = sqlite3.connect(DB_PATH)
    migrate_db(conn) # Migration prüfen
    
    # 1. Runs laden
    runs_query = """
    SELECT * FROM processing_run ORDER BY started_at DESC LIMIT 1000
    """
    df_runs = pd.read_sql_query(runs_query, conn)
    if not df_runs.empty:
        df_runs["started_at"] = pd.to_datetime(df_runs["started_at"])
        df_runs["date"] = df_runs["started_at"].dt.date
    
    # 2. Docs laden
    docs_query = """
    SELECT 
        d.id, d.run_id, d.ba_number, d.vendor_name, d.score, d.needs_review, d.net_total, d.has_template,
        r.started_at
    FROM extracted_document d
    JOIN processing_run r ON d.run_id = r.id
    ORDER BY r.started_at DESC
    LIMIT 1000
    """
    df_docs = pd.read_sql_query(docs_query, conn)
    
    conn.close()
    return df_runs, df_docs

# === UI ===

st.title("📈 OCR Analytics & KPI Dashboard")

df_runs, df_docs = load_data()

if df_runs is None or df_runs.empty:
    st.warning("Keine Daten gefunden.")
    st.stop()

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["Übersicht", "Qualität & Trefferquoten", "Fehler-Analyse", "Dokumente"])

# === TAB 1: ÜBERSICHT ===
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    
    total_runs = len(df_runs)
    success_rate = (df_runs["success"].sum() / total_runs) * 100
    
    # Scanned Ratio
    scanned_count = df_runs["is_scanned"].sum() if "is_scanned" in df_runs.columns else 0
    digital_born_count = total_runs - scanned_count
    
    with col1:
        st.metric("Verarbeitete Dateien", total_runs)
    with col2:
        st.metric("Erfolgsrate", f"{success_rate:.1f}%")
    with col3:
        st.metric("Digital Born", digital_born_count)
    with col4:
        st.metric("Gescannte Scans", scanned_count)
    
    st.markdown("### Verlauf")
    # Daily Volume
    daily_volume = df_runs.groupby("date").size().reset_index(name="count")
    fig_vol = px.bar(daily_volume, x="date", y="count", title="Verarbeitungsvolumen pro Tag")
    st.plotly_chart(fig_vol, use_container_width=True)

# === TAB 2: TREFFERQUOTEN ===
with tab2:
    col1, col2, col3 = st.columns(3)
    
    # Trefferquoten berechnen
    total_docs = len(df_docs) if not df_docs.empty else 1
    ba_hits = df_docs["ba_number"].notna().sum()
    vendor_hits = df_docs["vendor_name"].notna().sum()
    avg_score = df_docs["score"].mean()
    
    with col1:
        st.metric("Ø Score", f"{avg_score:.1f}")
    with col2:
        st.metric("BA-Nummer erkannt", f"{(ba_hits/total_docs)*100:.1f}%", help="Anteil Dokumente mit extrahierter BA")
    with col3:
        tmpl_count = df_docs["has_template"].sum() if "has_template" in df_docs.columns else 0
        st.metric("Lieferant (Template)", f"{tmpl_count} / {total_docs}", help="Anzahl Dokumente mit bekanntem Template")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Score Verteilung")
        fig_hist = px.histogram(df_docs, x="score", nbins=20, title="Score Histogramm")
        st.plotly_chart(fig_hist, use_container_width=True)
        
    with col_chart2:
        st.subheader("Manuelle Prüfung")
        review_counts = df_docs["needs_review"].value_counts().reset_index()
        review_counts.columns = ["needs_review", "count"]
        review_counts["label"] = review_counts["needs_review"].map({True: "Prüfung nötig", False: "Auto-Dunkelverarbeitung"})
        fig_pie = px.pie(review_counts, values="count", names="label", title="Automation Rate")
        st.plotly_chart(fig_pie, use_container_width=True)

# === TAB 3: FEHLER-ANALYSE ===
with tab3:
    st.subheader("API Fehler & Eskalationen")
    
    failed_runs = df_runs[df_runs["success"] == False]
    
    if not failed_runs.empty:
        # Fehler pro Tag
        fails_daily = failed_runs.groupby(["date", "error_message"]).size().reset_index(name="count")
        fig_fails = px.bar(fails_daily, x="date", y="count", color="error_message", title="Fehlertypen pro Tag")
        st.plotly_chart(fig_fails, use_container_width=True)
        
        st.dataframe(failed_runs[["filename", "started_at", "error_message"]])
    else:
        st.success("Keine API-Fehler protokolliert! 🎉")

# === TAB 4: DOKUMENTE & GRÖSSE ===
with tab4:
    st.subheader("Dokumenten-Statistik")
    
    # Scatter Plot Size vs Time
    if "file_size_bytes" in df_runs.columns:
        df_runs["size_mb"] = df_runs["file_size_bytes"] / (1024 * 1024)
        
        fig_scatter = px.scatter(
            df_runs, 
            x="duration_ms", 
            y="size_mb", 
            color="is_scanned",
            hover_data=["filename", "page_count"],
            title="Dateigröße vs. Verarbeitungsdauer"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.markdown("### Top 10 Größte Dateien")
        top_size = df_runs.sort_values("file_size_bytes", ascending=False).head(10)
        st.dataframe(
            top_size[["filename", "size_mb", "page_count", "is_scanned", "success"]],
            column_config={
                "size_mb": st.column_config.NumberColumn("Größe (MB)", format="%.2f"),
                "is_scanned": st.column_config.CheckboxColumn("Gescannt?")
            }
        )
