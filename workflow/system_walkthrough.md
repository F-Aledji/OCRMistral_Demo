# System Walkthrough - Mistral OCR Demo (v2)

## 1. Architecture Overview

The system has evolved from a simple script-based tool into a robust **Service-Oriented Architecture (SOA)** featuring:

-   **Backend**: FastAPI (`backend/`) handling API requests, database interactions, and the core processing pipeline.
-   **Frontend**: Next.js (`frontend/`) for a modern, responsive user interface to upload, view, and manage documents.
-   **Core Pipeline**: A unified processing engine (`core/`) shared by both the API and the legacy batch runner.
-   **Dashboard**: Streamlit (`dashboard/`) for quick analytics and monitoring.

### Key Components

| Component | Directory | Description |
| :--- | :--- | :--- |
| **API Server** | `backend/app/` | `main.py` entry point, `routers/` for endpoints, `services/` for logic. |
| **Unified Pipeline** | `core/pipeline/` | The heart of the system. coordinates Pre-Scan, OCR, Validation, and Scoring. |
| **Pre-Scan Service** | `backend/app/services/prescan.py` | **NEW**: Fast-Pass layer using `PyMuPDF` to find BA-Numbers before OCR. |
| **Database** | `backend/demo.db` | SQLite database storing Documents, Annotations, and Templates. |
| **OCR Engines** | `extraction/` | Wrappers for Gemini 2.0 (Google) and Mistral (Mistral AI). |

---

## 2. The Processing Pipeline (Step-by-Step)

The document processing flow has been significant enhanced:

1.  **Ingestion & Pre-Scan (Fast-Pass)**
    -   Document is uploaded via Frontend or Batch Runner.
    -   **Pre-Scan**: `PreScanService` immediately scans the first 2 pages (using `fitz`) for a **BA-Number** (Regex: `45\d{8}`).
    -   **Template Lookup**: If a BA-Number is found, the system checks the DB for a matching `SupplierTemplate` (coordinates for Header/Footer/Table).

2.  **OCR Extraction (The "Brain")**
    -   **Engine**: Gemini 3 Flash (or Mistral).
    -   **Context Injection**: If a template was found, its coordinates are injected into the Prompt as "Hints".
    -   **Output**: Structured JSON based on `schema/ocr_schema.py`.

3.  **Validation & "Judge" Repair**
    -   **Pydantic**: Validates the JSON against strict types.
    -   **The Judge**: If validation fails, a second LLM call (The "Judge") attempts to fix the JSON using error messages and raw text.
    -   **Hybrid Logic**: The Judge also receives Template coordinates to better locate missing fields.

4.  **Scoring & Business Logic**
    -   **ScoreEngine**: Evaluates the quality of extraction (0-100 pkt).
    -   **Criteria**:
        -   Validation Success (Critical)
        -   Field Confidence (heuristics)
        -   **DB Match**: Does the extracted Supplier exist in our Master Data? (`ValidBANumber` table)
        -   **Template Match**: Did we use a template?

5.  **Persistence & Traceability**
    -   Results are saved to `backend/demo.db`.
    -   **Trace Service**: Logs every step (Pipeline Start, OCR, Judge, etc.) for debugging.
    -   **Annotations**: Bounding boxes are converted and saved for the Frontend viewer.

---

## 3. New Features & Improvements

### 🚀 Pre-Scan Template Injection
-   **Problem**: Providing coordinates improves OCR, but we need to know *which* template to use before we start.
-   **Solution**: Lightweight Regex scan (`PreScanService`) identifies the document type in milliseconds.

### 💾 Filename Persistence
-   Original filenames are now tracked from Upload -> DB -> Frontend.
-   Fixed "Unbekannt" display issue.

### 🛡️ Hybrid Validation (The "Judge")
-   Self-healing capability.
-   Can repair malformed JSON or infer missing data based on neighbor fields.

### 📊 Scoring System
-   Documents get a "Confidence Score".
-   < 85pkt -> "Needs Review".
-   Visual Scorecards in the Frontend.

---

## 4. How to Run

### Backend
```bash
cd backend
python -m uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm run dev
```

### Batch Runner (Legacy/Testing)
```bash
python batch_runner.py --input "input_folder/"
```

### Dashboard
```bash
streamlit run dashboard/app.py
```
