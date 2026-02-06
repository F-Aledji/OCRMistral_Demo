# Mistral/Gemini OCR Demo (v2)

**Advanced Supplier Confirmation Processing System**

This repository contains a full-stack document processing pipeline ("Semiramis") designed to extract structured data from supplier confirmations using state-of-the-art LLMs (Gemini 2.0 Flash / Mistral AI).

---

## Architecture

The system is built as a modular microservice-ready application:

-   **Frontend**: Next.js (React) + Tailwind CSS + Shadcn UI (`frontend/`)
-   **Backend**: Python FastAPI (`backend/`)
-   **Core Pipeline**: Shared Logic (`core/`)
-   **Database**: SQLite (`backend/demo.db`)
-   **Dashboard**: Streamlit (`dashboard/`)

---

## Features (v2 Update)

### 1. Unified Processing Pipeline
-   **Centralized Logic**: `core/pipeline/unified_pipeline.py` integrates all steps.
-   **Pre-Scan (Fast-Pass)**: Uses `PreScanService` (PyMuPDF) to identify BA-Numbers *before* OCR.
-   **Template Injection**: Automatically feeds template coordinates to the LLM based on Pre-Scan results.

### 2. Hybrid Validation ("The Judge")
-   If the primary extraction fails validation, a second specialized LLM ("The Judge") attempts to repair the JSON.
-   Uses validation errors and raw text context to "heal" the data.

### 3. Traceability & Scoring
-   **Confidence Score**: Every document receives a score (0-100%) based on validation and data completeness.
-   **Trace Service**: Detailed logging of every pipeline step for debugging.
-   **Filename Persistence**: Tracks original filenames throughout the entire lifecycle.

---

## Getting Started

### Prerequisites
-   Python 3.10+
-   Node.js 18+
-   Google Cloud Credentials (for Gemini) or Mistral API Key

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/StartBuying/Mistral_OCR_Demo.git
    cd Mistral_OCR_Demo
    ```

2.  **Backend Setup**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Frontend Setup**
    ```bash
    cd frontend
    npm install
    ```

### Running the App

1.  **Start Backend**
    ```bash
    # Open new terminal
    cd backend
    python -m uvicorn app.main:app --reload
    ```

2.  **Start Frontend**
    ```bash
    # Open new terminal
    cd frontend
    npm run dev
    ```

3.  **Run Pipeline (Batch Mode)**
    ```bash
    python batch_runner.py --input "data/input"
    ```

---

## Project Structure

```
Mistral_OCR_Demo/
├── backend/            # FastAPI Server
│   ├── app/
│   │   ├── routers/    # API Endpoints
│   │   ├── services/   # Business Logic (PreScan, Trace, Storage)
│   │   └── db_models.py
├── core/               # Shared Pipeline Logic
│   └── pipeline/       # UnifiedPipeline
├── extraction/         # OCR Engines (Gemini, Mistral)
├── frontend/           # Next.js Application
├── schema/             # Data Models (Pydantic)
└── validation/         # Validation & Scoring Logic
```

##  Configuration

Create a `.env` file in the root directory:

```env
GOOGLE_APPLICATION_CREDENTIALS="path/to/your/key.json"
GEMINI_PROJECT_ID="your-project-id"
MISTRAL_API_KEY="your-key"
```
