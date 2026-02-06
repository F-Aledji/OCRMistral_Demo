import os
import shutil
import sqlite3
import sys

# Konfiguration
DB_PATH = "backend/demo.db"
DATA_DIR = "backend/data"

def list_documents(cursor):
    """Listet alle Dokumente auf."""
    try:
        cursor.execute("SELECT id, ba_number, filename, created_at FROM document ORDER BY created_at DESC")
        documents = cursor.fetchall()
        return documents
    except sqlite3.OperationalError:
        return []

def delete_document(doc_id, conn, cursor):
    """Löscht ein spezifisches Dokument."""
    print(f"Deleting document {doc_id}...")
    
    try:
        # 1. DB Einträge löschen
        cursor.execute("DELETE FROM annotations WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM document_files WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM document WHERE id = ?", (doc_id,))
        conn.commit()
        print("  - Database entries deleted.")
        
        # 2. Ordner löschen
        doc_dir = os.path.join(DATA_DIR, doc_id)
        if os.path.exists(doc_dir):
            shutil.rmtree(doc_dir)
            print(f"  - Directory {doc_dir} deleted.")
        else:
            print(f"  - Directory not found (skipped).")
            
        print("Success.")
    except Exception as e:
        print(f"Error deleting document: {e}")

def wipe_all(conn, cursor):
    """Löscht ALLES."""
    print("Wiping EVERYTHING...")
    tables = ["annotations", "document_files", "document"]
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  - Deleted entries from '{table}'")
        except sqlite3.OperationalError:
            print(f"  - Table '{table}' not found (skipping)")
    conn.commit()
    
    if os.path.exists(DATA_DIR):
        print(f"Cleaning data directory: {DATA_DIR}...")
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if item == ".gitkeep": continue
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception as e:
                print(f"  - Error deleting {item}: {e}")
    print("All done.")

def main():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n--- QUEUE MANAGER ---")
    documents = list_documents(cursor)
    
    if not documents:
        print("Queue is empty.")
        conn.close()
        return

    print(f"\nFound {len(documents)} documents:")
    for idx, doc in enumerate(documents):
        # doc = (id, ba, filename, created)
        doc_id, ba, fname, created = doc
        display_name = fname or "Unbekannt"
        ba_display = f" (BA: {ba})" if ba else ""
        print(f"[{idx+1}] {display_name}{ba_display} -- ID: {doc_id}")

    print("\nOptions:")
    print(" [A] Delete ALL")
    print(" [1-N] Delete specific document number")
    print(" [Q] Quit")
    
    choice = input("\nYour choice: ").strip().upper()
    
    if choice == 'Q':
        print("Bye.")
    elif choice == 'A':
        confirm = input("Are you sure you want to delete EVERYTHING? (y/n): ")
        if confirm.lower() == 'y':
            wipe_all(conn, cursor)
        else:
            print("Aborted.")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(documents):
                target_doc = documents[idx]
                doc_id = target_doc[0]
                confirm = input(f"Delete '{target_doc[2] or 'Unbekannt'}'? (y/n): ")
                if confirm.lower() == 'y':
                    delete_document(doc_id, conn, cursor)
                else:
                    print("Aborted.")
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid input.")

    conn.close()

if __name__ == "__main__":
    main()
