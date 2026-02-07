// =============================================================================
// QUEUE PAGE (Warteschlange)
// =============================================================================
// Diese Seite zeigt alle Dokumente in der Warteschlange.
// User können hier PDFs hochladen und Dokumente zur Bearbeitung öffnen.
// =============================================================================

"use client";  // <-- WICHTIG: Sagt Next.js, dass dies eine Client-Komponente ist

import { useEffect, useState } from "react";
import { Document, getDocuments, uploadDocument, claimDocument, processDocument } from "@/lib/api";


// -----------------------------------------------------------------------------
// STATUS-BADGE KOMPONENTE
// -----------------------------------------------------------------------------
// Zeigt den Status farbcodiert an (wie eine Ampel)
// -----------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
    const colors: Record<string, string> = {
        NEW: "bg-gray-500",
        OCR_RUNNING: "bg-blue-500 animate-pulse",
        OCR_DONE: "bg-green-500",
        NEEDS_REVIEW: "bg-yellow-500",
        NEEDS_REVIEW_BA: "bg-orange-500",
        HEALED: "bg-teal-500",
        VALID: "bg-green-600",
        ERROR: "bg-red-500",
        EXPORTED: "bg-purple-500",
    };

    return (
        <span className={`${colors[status] || "bg-gray-400"} text-white text-xs px-2 py-1 rounded`}>
            {status}
        </span>
    );
}


// -----------------------------------------------------------------------------
// SCORE-BADGE KOMPONENTE
// -----------------------------------------------------------------------------
// Zeigt den Score als Zahl mit Farbe (rot/gelb/grün)
// -----------------------------------------------------------------------------

function ScoreBadge({ score }: { score: number | null }) {
    if (score === null) return <span className="text-gray-400">—</span>;

    let color = "text-green-600";
    if (score < 70) color = "text-red-600";
    else if (score < 85) color = "text-yellow-600";

    return <span className={`${color} font-bold`}>{score}</span>;
}


// -----------------------------------------------------------------------------
// HAUPTKOMPONENTE: QUEUE PAGE
// -----------------------------------------------------------------------------

export default function QueuePage() {
    // State: Liste der Dokumente
    const [documents, setDocuments] = useState<Document[]>([]);

    // State: Lade-Status
    const [loading, setLoading] = useState(true);

    // State: Fehler-Nachricht
    const [error, setError] = useState<string | null>(null);

    // State: Upload läuft
    const [uploading, setUploading] = useState(false);

    // State: OCR läuft für welche Dokument-IDs
    const [processing, setProcessing] = useState<Set<string>>(new Set());

    // Simulierter User (später durch echte Auth ersetzen)
    const currentUserId = "demo-user";

    // -----------------------------------------------------------------------------
    // DATEN LADEN
    // -----------------------------------------------------------------------------

    async function loadDocuments() {
        try {
            setLoading(true);
            const docs = await getDocuments();
            setDocuments(docs);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unbekannter Fehler");
        } finally {
            setLoading(false);
        }
    }

    // Beim ersten Laden der Seite: Dokumente holen
    useEffect(() => {
        loadDocuments();
    }, []);

    // -----------------------------------------------------------------------------
    // UPLOAD HANDLER
    // -----------------------------------------------------------------------------

    async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            setUploading(true);
            await uploadDocument(file);
            await loadDocuments();  // Liste neu laden
        } catch (e) {
            setError(e instanceof Error ? e.message : "Upload fehlgeschlagen");
        } finally {
            setUploading(false);
            // Input zurücksetzen (sonst kann man dieselbe Datei nicht nochmal hochladen)
            event.target.value = "";
        }
    }

    // -----------------------------------------------------------------------------
    // CLAIM UND ÖFFNEN
    // -----------------------------------------------------------------------------

    async function handleOpenDocument(doc: Document) {
        try {
            // Erst claimen, dann öffnen
            await claimDocument(doc.id, currentUserId);
            window.location.href = `/documents/${doc.id}`;
        } catch (e) {
            setError(e instanceof Error ? e.message : "Claiming fehlgeschlagen");
        }
    }

    // -----------------------------------------------------------------------------
    // OCR STARTEN
    // -----------------------------------------------------------------------------

    async function handleProcess(doc: Document) {
        try {
            setProcessing(prev => new Set(prev).add(doc.id));
            await processDocument(doc.id);
            await loadDocuments();  // Liste neu laden
        } catch (e) {
            setError(e instanceof Error ? e.message : "OCR fehlgeschlagen");
        } finally {
            setProcessing(prev => {
                const next = new Set(prev);
                next.delete(doc.id);
                return next;
            });
        }
    }

    // -----------------------------------------------------------------------------
    // RENDER
    // -----------------------------------------------------------------------------

    // Prüfen ob Dokument von anderem User gesperrt ist
    function isLockedByOther(doc: Document): boolean {
        if (!doc.claimed_by_user_id) return false;
        if (doc.claimed_by_user_id === currentUserId) return false;
        if (!doc.claim_expires_at) return false;
        return new Date(doc.claim_expires_at) > new Date();
    }

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-sans p-8">
            {/* Header */}
            <div className="max-w-6xl mx-auto">
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-2xl font-bold text-slate-800 tracking-tight">Dokument-Warteschlange</h1>

                    {/* Upload Button */}
                    <label className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg cursor-pointer shadow-sm shadow-blue-200 transition-all font-medium text-sm flex items-center gap-2">
                        {uploading ? (
                            <span className="flex items-center gap-2">
                                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Uploading...
                            </span>
                        ) : "PDF hochladen"}
                        <input
                            type="file"
                            accept=".pdf"
                            onChange={handleUpload}
                            className="hidden"
                            disabled={uploading}
                        />
                    </label>
                </div>

                {/* Fehler-Anzeige */}
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex justify-between items-center shadow-sm">
                        <span className="font-medium">{error}</span>
                        <button onClick={() => setError(null)} className="text-red-400 hover:text-red-700">✕</button>
                    </div>
                )}

                {/* Lade-Anzeige */}
                {loading && (
                    <div className="text-center py-12">
                        <div className="inline-block w-8 h-8 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
                        <p className="text-slate-500 text-sm font-medium">Lade Dokumente...</p>
                    </div>
                )}

                {/* Dokument-Tabelle */}
                {!loading && (
                    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-slate-50 border-b border-slate-200">
                                <tr>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Dateiname</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">BA-Nummer</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Lieferant</th>
                                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Summe</th>
                                    <th className="px-6 py-4 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">Score</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Bearbeiter</th>
                                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Erstellt</th>
                                    <th className="px-6 py-4 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">Aktion</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {documents.length === 0 && (
                                    <tr>
                                        <td colSpan={9} className="px-6 py-12 text-center text-slate-500">
                                            Keine Dokumente vorhanden.
                                        </td>
                                    </tr>
                                )}

                                {documents.map((doc) => (
                                    <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                                        <td className="px-6 py-4">
                                            <StatusBadge status={doc.status} />
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-700 font-medium truncate max-w-[200px]" title={doc.filename || ""}>
                                            {doc.filename || <span className="text-slate-400 italic">Unbekannt</span>}
                                        </td>
                                        <td className="px-6 py-4 font-mono text-sm text-slate-700">
                                            {doc.ba_number || <span className="text-slate-400">—</span>}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-700">
                                            {doc.vendor_name || <span className="text-slate-400">—</span>}
                                        </td>
                                        <td className="px-6 py-4 text-right font-mono text-sm text-slate-700">
                                            {doc.total_value ? `€ ${doc.total_value.toFixed(2)}` : <span className="text-slate-400">—</span>}
                                        </td>
                                        <td className="px-6 py-4 text-center text-sm">
                                            <ScoreBadge score={doc.score} />
                                        </td>
                                        <td className="px-6 py-4 text-sm">
                                            {isLockedByOther(doc) ? (
                                                <span className="text-red-500 font-medium flex items-center gap-1">
                                                    <span className="w-2 h-2 rounded-full bg-red-500" />
                                                    {doc.claimed_by_user_id}
                                                </span>
                                            ) : doc.claimed_by_user_id === currentUserId ? (
                                                <span className="text-green-600 font-medium flex items-center gap-1">
                                                    <span className="w-2 h-2 rounded-full bg-green-500" />
                                                    Du
                                                </span>
                                            ) : (
                                                <span className="text-slate-400">—</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-right text-slate-400 text-xs tabular-nums">
                                            {new Date(doc.created_at).toLocaleString("de-DE")}
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <div className="flex items-center justify-center gap-2">
                                                {isLockedByOther(doc) ? (
                                                    <span className="text-slate-400 text-xs italic">Gesperrt</span>
                                                ) : (
                                                    <>
                                                        {doc.status === "NEW" && (
                                                            <button
                                                                onClick={() => handleProcess(doc)}
                                                                disabled={processing.has(doc.id)}
                                                                className="bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50 transition-colors"
                                                            >
                                                                {processing.has(doc.id) ? "Verarbeite..." : "Start OCR"}
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleOpenDocument(doc)}
                                                            className="bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 hover:border-slate-400 px-3 py-1.5 rounded-md text-xs font-medium transition-colors shadow-sm"
                                                        >
                                                            Öffnen
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* Refresh Button */}
                <div className="mt-6 text-center">
                    <button
                        onClick={loadDocuments}
                        disabled={loading}
                        className="text-slate-500 hover:text-blue-600 text-sm font-medium transition-colors flex items-center justify-center gap-2 mx-auto"
                    >
                        Aktualisieren
                    </button>
                </div>
            </div>
        </div>
    );
}
