import google.generativeai as genai
import os

# WICHTIG: Die Umgebungsvariable GOOGLE_APPLICATION_CREDENTIALS muss weiterhin gesetzt sein!
# Beispiel (im Terminal ausgeführt, BEVOR Sie dieses Skript starten):
# export GOOGLE_APPLICATION_CREDENTIALS="./mein-dienstkonto-schluessel.json"
# oder
# set GOOGLE_APPLICATION_CREDENTIALS=".\mein-dienstkonto-schluessel.json"

# Projekt-ID und Region sind für das google-generativeai SDK nicht direkt im init() erforderlich,
# da es sich stärker auf die Umgebungsvariablen und die Standardkonfiguration verlässt.
# Die Region wird oft implizit über den Endpunkt oder die Umgebungsvariablen bestimmt.
# Für Gemini 3 Pro Preview ist die Region 'us-central1' üblich.
PROJECT_ID = "ocr-pipeline-weinmannschanz" # Ihre Google Cloud Projekt-ID
LOCATION = "global" # Die Region, in der Sie Vertex AI nutzen wollen

# Konfigurieren Sie das generative AI SDK.
# Die Authentifizierung erfolgt automatisch über GOOGLE_APPLICATION_CREDENTIALS.
# Die Angabe der Region ist hier wichtig, da Gemini-Modelle regional sind.
try:
    genai.configure(project=PROJECT_ID, location=LOCATION)
    print(f"Google Gen AI Client erfolgreich konfiguriert für Projekt '{PROJECT_ID}' in Region '{LOCATION}'.")
except Exception as e:
    print(f"Fehler bei der Konfiguration des Google Gen AI Clients: {e}")
    print("Stellen Sie sicher, dass die Umgebungsvariable 'GOOGLE_APPLICATION_CREDENTIALS' korrekt auf Ihre Dienstkonto-JSON-Datei zeigt.")
    exit() # Skript beenden, wenn Authentifizierung fehlschlägt

# Wählen Sie das gewünschte Gemini-Modell aus.
# Für Gemini 3 Pro Preview verwenden Sie die Ihnen mitgeteilte Modell-ID.
# Beispiel:
model_name = "gemini-3-pro-preview" # Dies ist ein Platzhalter. Verwenden Sie die exakte ID, die Sie erhalten haben.
model = genai.GenerativeModel(model_name)

print(f"Verwende Modell: {model_name}")

# Beispiel für eine Textgenerierung
try:
    prompt = "Was sind die größten Herausforderungen bei der Implementierung von KI in kleinen und mittleren Unternehmen?"
    print(f"\nSende Prompt: '{prompt}'")
    response = model.generate_content(prompt)

    print("\nGenerierte Antwort:")
    # Das response-Objekt kann sich leicht unterscheiden, aber .text ist oft verfügbar.
    print(response.text)

    # Beispiel für eine Konversation (Multi-Turn Chat)
    print("\nStarte Multi-Turn-Konversation...")
    chat = model.start_chat()

    user_message1 = "Erzähle mir etwas über die Geschichte der Computer."
    print(f"\nUser: {user_message1}")
    response1 = chat.send_message(user_message1)
    print(f"Gemini: {response1.text}")


except Exception as e:
    print(f"\nFehler beim Aufruf des Gemini-Modells: {e}")
    print("Mögliche Ursachen: falsche Modell-ID, Region, Berechtigungen oder API-Limit.")

