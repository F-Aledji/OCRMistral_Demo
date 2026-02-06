// =============================================================================
// DOCUMENT DETAIL PAGE
// =============================================================================
// Diese Seite zeigt ein einzelnes Dokument mit PDF-Viewer und Annotations.
// User können hier Felder markieren und Bounding Boxes speichern.
// =============================================================================

"use client"; //sagt dem System dass es sich um eine Client-Side Komponente handelt

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import {
    Document,
    getDocument,
    getAnnotations,
    saveAnnotations,
    releaseDocument,
    getPdfUrl,
    Annotations,
    FieldAnnotation,
    BoundingBox
} from "@/lib/api";


// PDFAnnotator dynamisch laden (wegen PDF.js und Canvas - braucht Browser)
const PDFAnnotator = dynamic(() => import("@/components/PDFAnnotator"), {
    ssr: false,  // Nicht auf dem Server rendern
    loading: () => (
        <div className="flex-1 flex items-center justify-center bg-slate-50">
            <div className="text-center text-slate-500">
                <div className="inline-block w-8 h-8 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
                <p className="font-medium">PDF-Viewer wird geladen...</p>
            </div>
        </div>
    ),
});


// -----------------------------------------------------------------------------
// HAUPT-KOMPONENTE
// -----------------------------------------------------------------------------

export default function DocumentPage() {
    // URL-Parameter: Die Dokument-ID
    const params = useParams();
    const router = useRouter();
    const docId = params.id as string;

    // Simulierter User
    const currentUserId = "demo-user";

    // State
    const [document, setDocument] = useState<Document | null>(null);
    const [annotations, setAnnotations] = useState<Annotations | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    // Aktuell gewähltes Feld für die Annotation
    const [selectedField, setSelectedField] = useState<string | null>(null);

    // Temporäre Werte für das aktuell bearbeitete Feld
    const [editValue, setEditValue] = useState<string>("");

    // Aktuelle Seite (1-basiert)
    const [currentPage, setCurrentPage] = useState(1);
    const [numPages, setNumPages] = useState(1);

    function handlePageChange(newPage: number) {
        if (newPage >= 1 && newPage <= numPages) {
            setCurrentPage(newPage);
        }
    }

    // Zoom State
    const [zoom, setZoom] = useState(1.0);

    function handleZoomIn() {
        setZoom(prev => Math.min(prev + 0.25, 3.0));
    }

    function handleZoomOut() {
        setZoom(prev => Math.max(prev - 0.25, 0.5));
    }

    const handleLoadSuccess = useCallback((pages: number) => {
        setNumPages(pages);
    }, []);

    // PDF URL
    const pdfUrl = docId ? getPdfUrl(docId) : "";

    // -----------------------------------------------------------------------------
    // DATEN LADEN
    // -----------------------------------------------------------------------------

    async function loadData() {
        try {
            setLoading(true);
            const [doc, annot] = await Promise.all([
                getDocument(docId),
                getAnnotations(docId),
            ]);
            setDocument(doc);
            setAnnotations(annot);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Fehler beim Laden");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        if (docId) {
            loadData();
        }
    }, [docId]);

    // -----------------------------------------------------------------------------
    // NAVIGATION: Zurück zur Queue
    // -----------------------------------------------------------------------------

    async function handleBack() {
        try {
            // Dokument freigeben
            await releaseDocument(docId, currentUserId);
        } catch {
            // Ignorieren - vielleicht war es schon freigegeben
        }
        router.push("/queue");
    }

    // -----------------------------------------------------------------------------
    // ANNOTATION SPEICHERN
    // -----------------------------------------------------------------------------

    async function handleSave() {
        if (!annotations) return;

        try {
            setSaving(true);
            const result = await saveAnnotations(
                docId,
                currentUserId,
                annotations.version,
                annotations.fields
            );

            // Version aktualisieren
            setAnnotations({ ...annotations, version: result.new_version });
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
        } finally {
            setSaving(false);
        }
    }

    // -----------------------------------------------------------------------------
    // FELD BEARBEITEN
    // -----------------------------------------------------------------------------

    function handleFieldClick(fieldName: string) {
        setSelectedField(fieldName);

        const field = annotations?.fields[fieldName];
        setEditValue(field?.value?.toString() || "");

        // Wenn das Feld eine Box auf einer bestimmten Seite hat, dorthin springen
        if (field?.bbox?.page !== undefined) {
            setCurrentPage(field.bbox.page + 1);
        }
    }

    function handleValueChange(value: string) {
        setEditValue(value);
        if (selectedField && annotations) {
            const updatedFields = { ...annotations.fields };
            updatedFields[selectedField] = {
                ...updatedFields[selectedField],
                value: value,
            };
            setAnnotations({ ...annotations, fields: updatedFields });
        }
    }

    // -----------------------------------------------------------------------------
    // BOX GEZEICHNET (vom PDFAnnotator)
    // -----------------------------------------------------------------------------

    function handleBoxDrawn(fieldName: string, bbox: BoundingBox) {
        if (!annotations) return;

        const updatedFields = { ...annotations.fields };
        updatedFields[fieldName] = {
            ...updatedFields[fieldName],
            bbox: bbox,
        };
        setAnnotations({ ...annotations, fields: updatedFields });

        // Erfolgs-Feedback
        console.log(`Box für ${fieldName} gesetzt:`, bbox);
    }

    // -----------------------------------------------------------------------------
    // BOX LÖSCHEN
    // -----------------------------------------------------------------------------

    function handleDeleteBox(fieldName: string) {
        if (!annotations) return;

        const updatedFields = { ...annotations.fields };
        if (updatedFields[fieldName]) {
            delete updatedFields[fieldName].bbox;
        }
        setAnnotations({ ...annotations, fields: updatedFields });
    }

    // -----------------------------------------------------------------------------
    // RENDER
    // -----------------------------------------------------------------------------

    // Felder die wir anzeigen wollen (aus deinem Pydantic-Schema)
    const fieldConfig = [
        { key: "ba_number", label: "BA-Nummer" },
        { key: "vendor_name", label: "Lieferant" },
        { key: "document_date", label: "Belegdatum" },
        { key: "total_value", label: "Gesamtsumme" },
        { key: "document_type", label: "Dokumenttyp" },
    ];

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin text-4xl mb-4 text-blue-600">⏳</div>
                    <p className="text-slate-500 font-medium">Lade Dokument...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 px-6 py-4 shadow-sm z-10 relative">
                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={handleBack}
                            className="text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-2 text-sm font-medium"
                        >
                            <span>&larr;</span> Zurück
                        </button>
                        <div className="h-6 w-px bg-slate-200"></div>
                        <h1 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                            <span className="font-normal text-slate-500">#{document?.ba_number || "Dokument"}</span>
                        </h1>

                        {/* Pagination Controls */}
                        {numPages >= 1 && (
                            <div className="flex items-center bg-slate-100 rounded-lg p-0.5 ml-4">
                                <button
                                    onClick={() => handlePageChange(currentPage - 1)}
                                    disabled={currentPage <= 1}
                                    className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 disabled:opacity-30 disabled:hover:text-slate-600 transition-colors"
                                >
                                    &larr;
                                </button>
                                <span className="px-3 text-xs font-medium text-slate-900 border-x border-slate-200">
                                    Seite {currentPage} / {numPages}
                                </span>
                                <button
                                    onClick={() => handlePageChange(currentPage + 1)}
                                    disabled={currentPage >= numPages}
                                    className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 disabled:opacity-30 disabled:hover:text-slate-600 transition-colors"
                                >
                                    &rarr;
                                </button>
                            </div>
                        )}

                        {/* Zoom Controls */}
                        <div className="flex items-center bg-slate-100 rounded-lg p-0.5 ml-3">
                            <button
                                onClick={handleZoomOut}
                                disabled={zoom <= 0.5}
                                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 disabled:opacity-30 disabled:hover:text-slate-600 transition-colors"
                                title="Zoom Out"
                            >
                                -
                            </button>
                            <span className="px-2 text-xs font-medium text-slate-900 border-x border-slate-200 w-[4.5rem] text-center">
                                {Math.round(zoom * 100)}%
                            </span>
                            <button
                                onClick={handleZoomIn}
                                disabled={zoom >= 3.0}
                                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 disabled:opacity-30 disabled:hover:text-slate-600 transition-colors"
                                title="Zoom In"
                            >
                                +
                            </button>
                        </div>

                        {selectedField && (
                            <span className="bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-xs font-medium border border-blue-100 animate-in fade-in zoom-in duration-200 ml-2">
                                Zeichne: {fieldConfig.find(f => f.key === selectedField)?.label || selectedField}
                            </span>
                        )}
                    </div>

                    <div className="flex gap-3">
                        {selectedField && (
                            <button
                                onClick={() => setSelectedField(null)}
                                className="text-slate-600 hover:bg-slate-100 px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-transparent hover:border-slate-200"
                            >
                                Abbrechen
                            </button>
                        )}
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg text-sm font-medium shadow-sm shadow-blue-200 hover:shadow-md transition-all disabled:opacity-50 disabled:shadow-none flex items-center gap-2"
                        >
                            {saving ? "Speichern..." : "Speichern & Schließen"}
                        </button>
                    </div>
                </div>
            </div>

            {/* Fehler-Anzeige */}
            {error && (
                <div className="bg-red-50 border-b border-red-200 text-red-700 px-6 py-3 flex justify-between items-center">
                    <span className="flex items-center gap-2">❌ {error}</span>
                    <button onClick={() => setError(null)} className="text-red-400 hover:text-red-700 font-bold">×</button>
                </div>
            )}

            {/* Hauptbereich: 2-Spalten-Layout */}
            <div className="flex h-[calc(100vh-73px)] overflow-hidden">

                {/* LINKE SPALTE: PDF Viewer mit Annotation Canvas */}
                <div className="flex-1 bg-slate-100/50 p-6 overflow-auto relative flex justify-center">
                    <div className="max-w-5xl w-full min-h-[500px]">
                        <PDFAnnotator
                            pdfUrl={pdfUrl}
                            boxes={annotations?.fields || {}}
                            selectedField={selectedField}
                            onBoxDrawn={handleBoxDrawn}
                            currentPage={currentPage}
                            onLoadSuccess={handleLoadSuccess}
                            zoom={zoom}
                        />
                    </div>
                </div>

                {/* RECHTE SPALTE: Annotations */}
                <div className="w-[400px] bg-white border-l border-slate-200 flex flex-col shadow-xl z-20">
                    <div className="p-5 border-b border-slate-100 bg-slate-50/50">
                        <h2 className="text-base font-semibold text-slate-800">Extrahierte Daten</h2>
                        <p className="text-slate-500 text-xs mt-1">
                            Überprüfe und korrigiere die erkannten Werte.
                        </p>
                    </div>

                    <div className="flex-1 overflow-y-auto p-5 space-y-4">
                        {fieldConfig.map((field) => {
                            const annotation = annotations?.fields[field.key];
                            const isSelected = selectedField === field.key;
                            const hasValue = !!annotation?.value;
                            const hasBox = !!annotation?.bbox;

                            return (
                                <div
                                    key={field.key}
                                    className={`
                                        group rounded-xl border transition-all duration-200
                                        ${isSelected
                                            ? "bg-blue-50 border-blue-200 ring-4 ring-blue-50/50 shadow-sm"
                                            : "bg-white border-slate-200 hover:border-slate-300 hover:shadow-sm"
                                        }
                                    `}
                                >
                                    <div className="p-3">
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="flex items-center gap-2">
                                                <div>
                                                    <span className={`block text-xs font-semibold uppercase tracking-wider ${isSelected ? "text-blue-700" : "text-slate-500"}`}>
                                                        {field.label}
                                                    </span>
                                                </div>
                                            </div>

                                            <button
                                                onClick={() => handleFieldClick(field.key)}
                                                className={`
                                                    text-xs px-2.5 py-1 rounded-md font-medium transition-colors
                                                    ${isSelected
                                                        ? "bg-blue-600 text-white shadow-sm"
                                                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                                                    }
                                                `}
                                            >
                                                {isSelected ? "Markieren..." : "Bearbeiten"}
                                            </button>
                                        </div>

                                        {isSelected ? (
                                            <div className="mt-2 animate-in fade-in slide-in-from-top-1 duration-200">
                                                <input
                                                    type="text"
                                                    value={editValue}
                                                    onChange={(e) => handleValueChange(e.target.value)}
                                                    className="w-full bg-white border border-blue-300 text-slate-800 px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 shadow-inner"
                                                    placeholder="Wert eingeben..."
                                                    autoFocus
                                                />
                                                <div className="text-xs text-blue-600 mt-2 flex items-center gap-1.5 bg-blue-100/50 p-2 rounded">
                                                    <span>Zeichne jetzt einen Rahmen im PDF</span>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="mt-1 pl-10">
                                                <div className={`text-sm font-medium ${hasValue ? "text-slate-800" : "text-slate-400 italic"}`}>
                                                    {annotation?.value || "Kein Wert"}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Footer / Status */}
                                    {(hasBox || isSelected) && (
                                        <div className={`
                                            px-3 py-2 rounded-b-xl text-xs flex justify-between items-center border-t
                                            ${isSelected ? "bg-blue-100/30 border-blue-100" : "bg-slate-50 border-slate-100"}
                                        `}>
                                            <div className="flex items-center gap-1.5">
                                                {hasBox ? (
                                                    <>
                                                        <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                                                        <span className="text-slate-600">Seite {annotation!.bbox!.page + 1}</span>
                                                    </>
                                                ) : (
                                                    <>
                                                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300"></span>
                                                        <span className="text-slate-400">Position fehlt</span>
                                                    </>
                                                )}
                                            </div>

                                            {hasBox && (
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); handleDeleteBox(field.key); }}
                                                    className="text-slate-400 hover:text-red-500 transition-colors p-1 text-[10px] font-medium uppercase tracking-wide"
                                                    title="Position löschen"
                                                >
                                                    Entfernen
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>


                    <div className="p-4 bg-slate-50 border-t border-slate-200 text-slate-400 text-xs text-center">
                        Version {annotations?.version || 0} • {annotations?.source || "Auto"}
                    </div>
                </div>
            </div>
        </div>
    );
}
