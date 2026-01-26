import streamlit as st
import os
import time
import shutil
import json
from datetime import datetime
import config.config as cfg

st.set_page_config(page_title="Batch Dashboard", layout="wide", page_icon="📊")

# --- Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📊 Batch Runner Dashboard")
    st.caption(f"Überwachung für Projekt: `{cfg.PROJECT_ROOT}`")
with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# --- Helper Functions ---
def count_files(directory):
    if not os.path.exists(directory): return 0
    return len([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and not f.startswith('.')])

def get_daily_stats(folder):
    """Zählt Dateien, die heute modifiziert wurden."""
    if not os.path.exists(folder): return 0
    count = 0
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for f in os.listdir(folder):
        fp = os.path.join(folder, f)
        if os.path.isfile(fp):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime >= today_start:
                    count += 1
            except:
                pass
    return count

def get_recent_logs(lines=20):
    if not os.path.exists(cfg.LOG_FILE):
        return ["⚠️ Kein Log-File gefunden."]
    try:
        with open(cfg.LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        return [f"Fehler beim Lesen der Logs: {e}"]

# --- Metrics Section ---
st.subheader("Status Übersicht")
m1, m2, m3, m4 = st.columns(4)

input_count = count_files(cfg.FOLDERS["INPUT"])
archive_today = get_daily_stats(cfg.FOLDERS["ARCHIVE"])
error_count = count_files(cfg.FOLDERS["ERROR"])
output_count = count_files(cfg.FOLDERS["OUTPUT"])

m1.metric("📥 Warteschlange (Input)", input_count, help="Dateien in 01_Input_PDF")
m2.metric("✅ Archiviert (Heute)", archive_today, help="Dateien in 99_Archive_Success (Heute bearbeitet)")
m3.metric("❌ Fehler (Quarantäne)", error_count, delta_color="inverse", help="Dateien in 98_Error_Quarantine")
m4.metric("📤 Output XML Total", output_count, help="Dateien in 02_Output_XML")

# --- Quick Actions ---
st.subheader("Schnellzugriff")
ac1, ac2, ac3 = st.columns(3)

with ac1:
    if error_count > 0:
        if st.button(f"🚨 Alle ({error_count}) Fehler wiederholen", type="primary", use_container_width=True):
            count = 0
            for f in os.listdir(cfg.FOLDERS["ERROR"]):
                src = os.path.join(cfg.FOLDERS["ERROR"], f)
                dst = os.path.join(cfg.FOLDERS["INPUT"], f)
                try:
                    shutil.move(src, dst)
                    count += 1
                except Exception as e:
                    st.error(f"Fehler bei {f}: {e}")
            if count > 0:
                st.success(f"{count} Dateien zurück in Input verschoben!")
                time.sleep(1.5)
                st.rerun()
    else:
        st.button("✅ Keine Fehler zum Wiederholen", disabled=True, use_container_width=True)

with ac2:
    if st.button("🗑️ Logs leeren", use_container_width=True):
        try:
            with open(cfg.LOG_FILE, "w", encoding="utf-8") as f:
                f.write("")
            st.success("Log-Datei wurde geleert.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Konnte Logs nicht leeren: {e}")

# --- Live Log View ---
st.divider()
st.subheader("📜 Live Logs")

@st.fragment(run_every=2)
def show_live_logs():
    """Zeigt die Logs an und aktualisiert sich alle 2 Sekunden selbständig."""
    log_container = st.container(height=300)
    # Button zum manuellen Stoppen/Starten könnte hier hin, aber wir lassen es einfach laufen
    logs = get_recent_logs(30)
    log_text = "".join(logs)
    log_container.code(log_text, language="text")
    st.caption(f"Letztes Update: {time.strftime('%H:%M:%S')}")

show_live_logs()

# --- Tabs für Details ---
st.divider()
tab1, tab2, tab3 = st.tabs(["📝 Letzte Ergebnisse (Trace)", "📂 Output XML", "⚠️ Quarantäne Details"])

with tab1:
    st.caption("Zeigt die letzten 5 Verarbeitungschritte aus `03_Process_Trace`")
    if os.path.exists(cfg.FOLDERS["TRACE"]):
        # Ordner holen, nach Zeit sortieren
        try:
            folders = [os.path.join(cfg.FOLDERS["TRACE"], f) for f in os.listdir(cfg.FOLDERS["TRACE"]) if os.path.isdir(os.path.join(cfg.FOLDERS["TRACE"], f))]
            folders = sorted(folders, key=os.path.getmtime, reverse=True)[:5]
            
            if folders:
                for fp in folders:
                    fn = os.path.basename(fp)
                    date_str = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%H:%M:%S')
                    
                    with st.expander(f"🕒 {date_str} - {fn}"):
                        # JSON laden wenn vorhanden
                        json_path = os.path.join(fp, "2_extracted_data.json")
                        log_path = os.path.join(fp, "process_log.txt")
                        
                        c_log, c_json = st.columns([1, 2])
                        
                        with c_log:
                            st.write("**Prozess Log:**")
                            if os.path.exists(log_path):
                                with open(log_path, 'r', encoding='utf-8') as f:
                                    st.text(f.read())
                            else:
                                st.caption("Kein Log.")

                        with c_json:
                            st.write("**Extrahierte Daten:**")
                            if os.path.exists(json_path):
                                with open(json_path, 'r', encoding='utf-8') as f:
                                    st.json(json.load(f))
                            else:
                                st.caption("JSON Datei fehlt.")
            else:
                st.info("Keine Trace-Ordner gefunden.")
        except Exception as e:
            st.error(f"Fehler beim Laden der Traces: {e}")

with tab2:
    st.caption("Die 5 neuesten XML-Dateien")
    if os.path.exists(cfg.FOLDERS["OUTPUT"]):
        files = [os.path.join(cfg.FOLDERS["OUTPUT"], f) for f in os.listdir(cfg.FOLDERS["OUTPUT"]) if f.endswith(".xml")]
        files = sorted(files, key=os.path.getmtime, reverse=True)[:5]
        
        if files:
            for fp in files:
                fn = os.path.basename(fp)
                st.text(f"📄 {fn}")
        else:
            st.info("Kein XML Output vorhanden.")

with tab3:
    st.caption("Dateien im Fehler-Ordner")
    if os.path.exists(cfg.FOLDERS["ERROR"]):
        files = [f for f in os.listdir(cfg.FOLDERS["ERROR"]) if os.path.isfile(os.path.join(cfg.FOLDERS["ERROR"], f))]
        if files:
            for f in files:
                st.warning(f"⚠️ {f}")
        else:
            st.success("Quarantäne ist leer.")
