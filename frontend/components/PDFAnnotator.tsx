// =============================================================================
// PDF ANNOTATOR KOMPONENTE
// =============================================================================
// Diese Komponente zeigt ein PDF mit einem Canvas-Overlay, auf dem man
// Bounding Boxes zeichnen kann.
//
// Technologien:
// - PDF.js: Rendert das PDF auf ein Canvas
// - Konva: Zeichnet interaktive Boxen auf ein zweites Canvas
// =============================================================================

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Stage, Layer, Rect, Text } from "react-konva";
import type Konva from "konva";
import { BoundingBox, FieldAnnotation } from "@/lib/api";


// -----------------------------------------------------------------------------
// TYPEN
// -----------------------------------------------------------------------------

interface PDFAnnotatorProps {
    // URL zum PDF (wird vom Backend geholt)
    pdfUrl: string;

    // Aktuell gezeichnete Boxen (von den Annotations)
    boxes: Record<string, FieldAnnotation>;

    // Aktuell gewähltes Feld (für neue Box)
    selectedField: string | null;

    // Callback wenn eine Box gezeichnet wurde
    onBoxDrawn: (fieldName: string, bbox: BoundingBox) => void;

    // Aktuelle Seite
    currentPage?: number;

    // Callback wenn PDF geladen wurde (z.B. für Seitenanzahl)
    onLoadSuccess?: (numPages: number) => void;

    // Zoom Level (1.0 = Fit Width)
    zoom?: number;
}


// Farben für verschiedene Feldtypen
const FIELD_COLORS: Record<string, string> = {
    ba_number: "#22c55e",      // Grün
    vendor_name: "#3b82f6",    // Blau
    document_date: "#eab308",  // Gelb
    total_value: "#ef4444",    // Rot
    document_type: "#8b5cf6",  // Lila
    default: "#94a3b8",        // Grau
};


// -----------------------------------------------------------------------------
// HAUPTKOMPONENTE
// -----------------------------------------------------------------------------

export default function PDFAnnotator({
    pdfUrl,
    boxes,
    selectedField,
    onBoxDrawn,
    currentPage = 1,
    onLoadSuccess,
    zoom = 1.0,
}: PDFAnnotatorProps) {

    // =========================================================================
    // REFS
    // =========================================================================
    // Refs werden genutzt um direkten Zugriff auf DOM-Elemente zu bekommen

    const containerRef = useRef<HTMLDivElement>(null);  // Der äußere Container (für Breitenberechnung)
    const canvasRef = useRef<HTMLCanvasElement>(null);  // Das Canvas auf dem das PDF gerendert wird

    // =========================================================================
    // STATE
    // =========================================================================

    // ----- Dimensionen -----
    // Speichert die aktuelle Größe des PDF-Canvas nach dem Rendern
    // Wird auch für die Konva-Stage verwendet (muss gleich groß sein)
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    // Das Verhältnis zwischen Canvas-Pixeln und PDF-Punkten
    // Beispiel: pdfScale = 2 bedeutet 1 PDF-Punkt = 2 Canvas-Pixel
    // Wichtig für die Umrechnung der Bounding Box Koordinaten
    const [pdfScale, setPdfScale] = useState(1);

    // ----- Lade-Status -----
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // ----- Zeichnen-State -----
    // Diese States verwalten das Zeichnen einer neuen Box
    const [isDrawing, setIsDrawing] = useState(false);           // Maus gedrückt?
    const [drawStart, setDrawStart] = useState({ x: 0, y: 0 });  // Startpunkt der Box
    const [currentRect, setCurrentRect] = useState<{              // Aktuelle Box während des Zeichnens
        x: number,
        y: number,
        width: number,
        height: number
    } | null>(null);

    // Ref für aktive Render-Task (verhindert Race-Condition bei schnellem Zoom)
    // Wenn ein neuer Render startet während ein alter noch läuft, 
    // wird der alte abgebrochen
    const renderTaskRef = useRef<any>(null);

    // -----------------------------------------------------------------------------
    // PDF LADEN UND RENDERN
    // -----------------------------------------------------------------------------

    const renderPdf = useCallback(async () => {
        if (!canvasRef.current || !containerRef.current) return;

        // Vorherige Render-Operation abbrechen
        if (renderTaskRef.current) {
            try {
                renderTaskRef.current.cancel();
            } catch (e) {
                // Ignorieren falls bereits beendet
            }
            renderTaskRef.current = null;
        }

        try {
            setLoading(true);
            setError(null);

            // PDF.js dynamisch laden (wegen Next.js SSR)
            const pdfjsLib = await import("pdfjs-dist");

            // Worker konfigurieren (unpkg hat neue Versionen schneller als cdnjs)
            pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

            // PDF laden
            const loadingTask = pdfjsLib.getDocument(pdfUrl);
            const pdf = await loadingTask.promise;

            // Callback für Seitenanzahl
            if (onLoadSuccess) {
                onLoadSuccess(pdf.numPages);
            }

            // Seite holen (1-basiert)
            const page = await pdf.getPage(currentPage);

            // Viewport berechnen
            // Wir skalieren so, dass das PDF in den Container passt (Base Scale)
            // Dann multiplizieren wir mit dem Zoom Faktor
            const containerWidth = containerRef.current.clientWidth;
            const unscaledViewport = page.getViewport({ scale: 1 });
            const baseScale = containerWidth / unscaledViewport.width;
            const finalScale = baseScale * zoom;

            const viewport = page.getViewport({ scale: finalScale });

            // Canvas vorbereiten (komplett zurücksetzen für neuen Render)
            const canvas = canvasRef.current;
            const context = canvas.getContext("2d", { willReadFrequently: true });
            if (!context) return;

            // Alten Inhalt löschen bevor neue Dimensionen gesetzt werden
            context.clearRect(0, 0, canvas.width, canvas.height);

            // Canvas-Größe setzen (muss nach clearRect passieren)
            canvas.width = viewport.width;
            canvas.height = viewport.height;

            // Dimensionen für Konva-Stage speichern
            setDimensions({ width: viewport.width, height: viewport.height });
            setPdfScale(finalScale);

            // PDF rendern (Task speichern für möglichen Abbruch)
            const renderTask = page.render({
                canvasContext: context,
                viewport: viewport,
            } as any);
            renderTaskRef.current = renderTask;

            await renderTask.promise;
            renderTaskRef.current = null;

            setLoading(false);
        } catch (e: any) {
            // RenderingCancelledException ignorieren (normaler Ablauf bei Abbruch)
            if (e?.name === "RenderingCancelledException") {
                return;
            }
            // Canvas-Konflikt bei StrictMode ignorieren (PDF rendert trotzdem)
            if (e?.message?.includes("multiple render()")) {
                console.warn("PDF Render Race (ignoriert):", e.message);
                setLoading(false);
                return;
            }
            console.error("PDF Render Error:", e);
            setError(e instanceof Error ? e.message : "PDF konnte nicht geladen werden");
            setLoading(false);
        }
    }, [pdfUrl, currentPage, onLoadSuccess, zoom]);

    // PDF rendern wenn URL oder Seite sich ändert
    useEffect(() => {
        renderPdf();
    }, [renderPdf]);

    // Bei Fenstergrößenänderung neu rendern
    useEffect(() => {
        const handleResize = () => renderPdf();
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, [renderPdf]);

    // -----------------------------------------------------------------------------
    // ZEICHNEN-LOGIK
    // -----------------------------------------------------------------------------

    function handleMouseDown(e: Konva.KonvaEventObject<MouseEvent>) {
        if (!selectedField) return;  // Kein Feld ausgewählt

        const stage = e.target.getStage();
        if (!stage) return;

        const pos = stage.getPointerPosition();
        if (!pos) return;

        setIsDrawing(true);
        setDrawStart({ x: pos.x, y: pos.y });
        setCurrentRect({ x: pos.x, y: pos.y, width: 0, height: 0 });
    }

    function handleMouseMove(e: Konva.KonvaEventObject<MouseEvent>) {
        if (!isDrawing) return;

        const stage = e.target.getStage();
        if (!stage) return;

        const pos = stage.getPointerPosition();
        if (!pos) return;

        setCurrentRect({
            x: Math.min(drawStart.x, pos.x),
            y: Math.min(drawStart.y, pos.y),
            width: Math.abs(pos.x - drawStart.x),
            height: Math.abs(pos.y - drawStart.y),
        });
    }

    function handleMouseUp() {
        if (!isDrawing || !currentRect || !selectedField) {
            setIsDrawing(false);
            return;
        }

        // Mindestgröße prüfen (10x10 Pixel)
        if (currentRect.width < 10 || currentRect.height < 10) {
            setIsDrawing(false);
            setCurrentRect(null);
            return;
        }

        // Canvas-Koordinaten in PDF-Koordinaten umrechnen
        const bbox: BoundingBox = {
            page: currentPage - 1,  // 0-basiert
            x0: currentRect.x / pdfScale,
            y0: currentRect.y / pdfScale,
            x1: (currentRect.x + currentRect.width) / pdfScale,
            y1: (currentRect.y + currentRect.height) / pdfScale,
        };

        // Callback aufrufen
        onBoxDrawn(selectedField, bbox);

        // Reset
        setIsDrawing(false);
        setCurrentRect(null);
    }

    // -----------------------------------------------------------------------------
    // RENDER
    // -----------------------------------------------------------------------------

    return (
        <div
            ref={containerRef}
            className="w-full relative flex justify-center min-h-[600px]"
        >
            <div
                className="relative bg-white shadow-lg rounded-sm border border-slate-200 transaction-none"
                style={{
                    height: loading ? "600px" : dimensions.height,
                    width: loading ? "100%" : dimensions.width,
                }}
            >
                {/* Lade-Anzeige */}
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10 backdrop-blur-sm">
                        <div className="text-center text-slate-800">
                            <div className="inline-block w-8 h-8 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin mb-3"></div>
                            <p className="font-medium">PDF wird geladen...</p>
                        </div>
                    </div>
                )}

                {/* Fehler-Anzeige */}
                {error && (
                    <div className="absolute inset-0 flex items-center justify-center bg-white/90 z-10">
                        <div className="bg-red-50 p-6 rounded-xl border border-red-200 text-red-600 shadow-lg text-center max-w-sm">
                            <div className="font-bold text-lg mb-1">Fehler beim Laden</div>
                            <div className="text-sm">{error}</div>
                        </div>
                    </div>
                )}

                {/* PDF Canvas (im Hintergrund) */}
                <canvas
                    ref={canvasRef}
                    className="absolute top-0 left-0"
                    style={{ display: loading ? "none" : "block" }}
                />

                {/* Konva Stage (Overlay für Boxen) */}
                {!loading && dimensions.width > 0 && (
                    <Stage
                        width={dimensions.width}
                        height={dimensions.height}
                        className="absolute top-0 left-0"
                        style={{ cursor: selectedField ? "crosshair" : "default" }}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                    >
                        <Layer>
                            {/* Existierende Boxen zeichnen */}
                            {Object.entries(boxes).map(([fieldName, annotation]) => {
                                if (!annotation.bbox || annotation.bbox.page !== currentPage - 1) return null;

                                const color = FIELD_COLORS[fieldName] || FIELD_COLORS.default;
                                const bbox = annotation.bbox;

                                // PDF-Koordinaten in Canvas-Koordinaten umrechnen
                                const x = bbox.x0 * pdfScale;
                                const y = bbox.y0 * pdfScale;
                                const width = (bbox.x1 - bbox.x0) * pdfScale;
                                const height = (bbox.y1 - bbox.y0) * pdfScale;

                                return (
                                    <React.Fragment key={fieldName}>
                                        {/* Box */}
                                        <Rect
                                            x={x}
                                            y={y}
                                            width={width}
                                            height={height}
                                            stroke={color}
                                            strokeWidth={2}
                                            fill={`${color}20`}  // 20 = 12% Opacity
                                        />
                                        {/* Label */}
                                        <Text
                                            x={x}
                                            y={y - 16}
                                            text={fieldName}
                                            fontSize={12}
                                            fill={color}
                                            fontStyle="bold"
                                        />
                                    </React.Fragment>
                                );
                            })}

                            {/* Aktuelle Zeichnung (während des Ziehens) */}
                            {currentRect && selectedField && (
                                <Rect
                                    x={currentRect.x}
                                    y={currentRect.y}
                                    width={currentRect.width}
                                    height={currentRect.height}
                                    stroke={FIELD_COLORS[selectedField] || FIELD_COLORS.default}
                                    strokeWidth={2}
                                    dash={[5, 5]}
                                    fill={`${FIELD_COLORS[selectedField] || FIELD_COLORS.default}30`}
                                />
                            )}
                        </Layer>
                    </Stage>
                )}

                {/* Hilfe-Text */}
                {selectedField && !loading && (
                    <div className="absolute bottom-4 left-4 bg-slate-900/90 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-lg backdrop-blur-sm">
                        Ziehe ein Rechteck um <strong>{selectedField}</strong> zu markieren
                    </div>
                )}
            </div>
        </div>
    );
}

// React muss importiert werden für Fragment
import React from "react";
