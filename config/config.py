import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Konfiguration laden
load_dotenv(override=True)

# === API Keys & Credentials ===

# Mistral AI Einstellungen
# MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# Google Gemini / Vertex AI Einstellungen
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID", "")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")
GEMINI_CREDENTIALS = os.getenv("GEMINI_APPLICATION_CREDENTIALS", "")

# === Ordner Pfade ===
# Basis Pfad (Root des Projekts)
# config.py liegt in /config, also zwei Ebenen hoch für Root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOLDERS = {
    "INPUT": os.path.join(PROJECT_ROOT, "01_Input_PDF"),
    "OUTPUT": r"J:\\TRANSFER\\RETARUS\\Test\\AIValidator\\XML\\Debug",
    "TRACE": os.path.join(PROJECT_ROOT, "03_Process_Trace"),
    "ERROR": os.path.join(PROJECT_ROOT, "98_Error_Quarantine"),
    "ARCHIVE": os.path.join(PROJECT_ROOT, "99_Archive_Success")
}

# === Modelle ===
GEMINI_OCR_MODEL = "gemini-3-flash-preview"
#GEMINI_OCR_MODEL = "gemini-3-pro-flash"
GEMINI_LLM_MODEL = "gemini-3-pro-preview"
OPENAI_MODEL = "gpt-5.1"
# MISTRAL_OCR_MODEL = "mistral-ocr-latest"

# === Judge Einstellung ===
JUDGE_PROVIDER = "Google"
JUDGE_MODEL = "gemini-3-pro-preview"


# === Processing Einstellungen ===
RETRY_WAIT_SECONDS = 60 # Wartezeit zwischen Retries bei temporären Fehlern in der Verarbeitung
MAX_RETRIES = 3 # Maximale Anzahl an Retries bei temporären Fehlern
POLLING_INTERVAL = 5 # Das ist dafür da dass der Batch Runner nicht permanent den Ordner scannt

# === Model Limits für InputGate ===
MODEL_LIMITS = {
    # "Mistral OCR": {"max_mb": 50, "max_pages": 1000},
    "Gemini OCR": {"max_mb": 50, "max_pages": None},
}

# === Logging Setup ===
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "processing.log")

def setup_logging(name="OCR_Pipeline"):
    """
    Konfiguriert das Logging mit Rotation und sauberem Format.
    """
    # Log Verzeichnis erstellen
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger = logging.getLogger() # Root Logger konfigurieren
    logger.setLevel(logging.INFO)

    # Verhindern dass Handler mehrfach hinzugefügt werden
    if logger.handlers:
        return logger

    # Formatierer
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | [%(name)s] | %(message)s'
    )

    # 1. Datei Handler mit Rotation (10 MB, 5 Backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 2. Konsolen Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    return logger
