// =============================================================================
// API CLIENT
// =============================================================================
// Hier sind alle Funktionen für die Kommunikation mit dem Backend.
// Das Frontend ruft diese Funktionen auf, um Daten zu holen/speichern.
// =============================================================================

// Backend URL automatisch basierend auf der aktuellen Adresse im Browser ermitteln
// Falls lokal: localhost, falls im Netzwerk: die IP des Servers
const getApiBase = () => {
    if (typeof window !== "undefined") {
        const hostname = window.location.hostname;
        return `http://${hostname}:8000/api/v1`;
    }
    return "http://localhost:8000/api/v1";
};

const API_BASE = getApiBase();


// -----------------------------------------------------------------------------
// TYPEN (entsprechen den Python-Models im Backend)
// -----------------------------------------------------------------------------

export interface Document {
    id: string;
    status: string;
    ba_number: string | null;
    vendor_name: string | null;
    total_value: number | null;
    score: number | null;
    claimed_by_user_id: string | null;
    claim_expires_at: string | null;
    version: number;
    created_at: string;
    updated_at: string;
    filename?: string | null;
}

export interface BoundingBox {
    page: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
}

export interface FieldAnnotation {
    value: string | number;
    bbox?: BoundingBox;
}

export interface Annotations {
    version: number;
    fields: Record<string, FieldAnnotation>;
    source?: string;
    author?: string;
}


// -----------------------------------------------------------------------------
// QUEUE-FUNKTIONEN
// -----------------------------------------------------------------------------

/**
 * Holt alle Dokumente aus der Warteschlange.
 * 
 * Beispiel:
 *   const docs = await getDocuments();
 *   docs.forEach(d => console.log(d.ba_number));
 */
export async function getDocuments(status?: string): Promise<Document[]> {
    let url = `${API_BASE}/documents`;
    if (status) {
        url += `?status=${status}`;
    }

    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`Fehler beim Laden: ${res.status}`);
    }
    return res.json();
}


/**
 * Holt ein einzelnes Dokument.
 */
export async function getDocument(id: string): Promise<Document> {
    const res = await fetch(`${API_BASE}/documents/${id}`);
    if (!res.ok) {
        throw new Error(`Dokument nicht gefunden: ${res.status}`);
    }
    return res.json();
}


// -----------------------------------------------------------------------------
// UPLOAD
// -----------------------------------------------------------------------------

/**
 * Lädt eine PDF-Datei hoch.
 * 
 * Beispiel:
 *   const file = event.target.files[0];
 *   const doc = await uploadDocument(file);
 */
export async function uploadDocument(file: File): Promise<Document> {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/documents`, {
        method: "POST",
        body: formData,
    });

    if (!res.ok) {
        throw new Error(`Upload fehlgeschlagen: ${res.status}`);
    }
    return res.json();
}


// -----------------------------------------------------------------------------
// CLAIMING (Sperren/Freigeben)
// -----------------------------------------------------------------------------

/**
 * Markiert ein Dokument als "in Bearbeitung" durch dich.
 * Andere können es dann nicht mehr bearbeiten.
 */
export async function claimDocument(id: string, userId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}/claim?user_id=${userId}`, {
        method: "POST",
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Claiming fehlgeschlagen");
    }
}


/**
 * Gibt ein Dokument wieder frei.
 */
export async function releaseDocument(id: string, userId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}/release?user_id=${userId}`, {
        method: "POST",
    });

    if (!res.ok) {
        throw new Error("Freigabe fehlgeschlagen");
    }
}


// -----------------------------------------------------------------------------
// ANNOTATIONEN (Bounding Boxes)
// -----------------------------------------------------------------------------

/**
 * Holt die aktuellen Annotationen für ein Dokument.
 */
export async function getAnnotations(docId: string): Promise<Annotations> {
    const res = await fetch(`${API_BASE}/documents/${docId}/annotations`);
    if (!res.ok) {
        throw new Error("Annotationen nicht gefunden");
    }
    return res.json();
}


/**
 * Speichert neue Annotationen.
 * 
 * WICHTIG: Du musst die aktuelle Version mitsenden!
 * Wenn jemand anderes in der Zwischenzeit gespeichert hat,
 * bekommst du einen Fehler (409 Conflict).
 */
export async function saveAnnotations(
    docId: string,
    userId: string,
    currentVersion: number,
    fields: Record<string, FieldAnnotation>
): Promise<{ new_version: number }> {
    const res = await fetch(
        `${API_BASE}/documents/${docId}/annotations?user_id=${userId}&current_version=${currentVersion}`,
        {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fields }),
        }
    );

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Speichern fehlgeschlagen");
    }
    return res.json();
}


// -----------------------------------------------------------------------------
// PIPELINE: Dokument verarbeiten
// -----------------------------------------------------------------------------

/**
 * Startet die OCR-Pipeline für ein Dokument.
 * 
 * Das macht:
 * 1. OCR mit Gemini
 * 2. Pydantic-Validierung
 * 3. Score berechnen
 * 4. Annotations + Status aktualisieren
 */
export async function processDocument(docId: string): Promise<{
    success: boolean;
    score?: number;
    status?: string;
    error?: string;
}> {
    const res = await fetch(`${API_BASE}/documents/${docId}/process`, {
        method: "POST",
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Verarbeitung fehlgeschlagen");
    }
    return res.json();
}


// -----------------------------------------------------------------------------
// PDF URL
// -----------------------------------------------------------------------------

/**
 * Gibt die URL zum PDF zurück (für Anzeige im Viewer).
 */
export function getPdfUrl(docId: string): string {
    return `${API_BASE}/documents/${docId}/file`;
}
