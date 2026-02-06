import sqlite3
import os

DB_PATH = "backend/demo.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Datenbank nicht gefunden: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Prüfen ob Spalte schon existiert
        cursor.execute("PRAGMA table_info(document)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "filename" in columns:
            print("Spalte 'filename' existiert bereits.")
        else:
            print("Füge Spalte 'filename' hinzu...")
            cursor.execute("ALTER TABLE document ADD COLUMN filename TEXT")
            conn.commit()
            print("Erfolgreich hinzugefügt.")
            
    except Exception as e:
        print(f"Fehler bei Migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
