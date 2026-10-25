import { useEffect, useRef, useState } from "react";
import { pdfScale } from "./pdf";

// A PDF drawn page by page with pdf.js, each page a canvas the width of the box. Never an iframe:
// iOS Safari shows only the first page of an embedded PDF, or will not scroll it. The canvases are
// drawn once, at the box's width when it opens; CSS keeps them fitting if the box later changes.

export function PdfView({ url, label }: { url: string; label: string }) {
  const pages = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<{ state: "loading" | "ready" } | { state: "error"; error: string }>({ state: "loading" });

  useEffect(() => {
    const box = pages.current!;
    let stopped = false;
    let destroy = () => {};
    setState({ state: "loading" });
    (async () => {
      const { pdfjs } = await import("./pdfjs");
      if (stopped) return;
      const task = pdfjs.getDocument({ url });
      destroy = () => void task.destroy();
      const doc = await task.promise;
      for (let n = 1; n <= doc.numPages; n++) {
        const page = await doc.getPage(n);
        const viewport = page.getViewport({ scale: pdfScale(page.view[2] - page.view[0], box.clientWidth, window.devicePixelRatio) });
        const canvas = document.createElement("canvas");
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.className = "block h-auto w-full rounded-[var(--radius-control)] border border-line";
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", `${label}, page ${n} of ${doc.numPages}`);
        await page.render({ canvas, viewport }).promise;
        if (stopped) return;
        box.append(canvas);
      }
      setState({ state: "ready" });
    })().catch((e: Error) => {
      if (!stopped) setState({ state: "error", error: e.message });
    });
    return () => {
      stopped = true;
      destroy();
      box.replaceChildren();
    };
  }, [url, label]);

  return (
    <div className="flex flex-col gap-2">
      {state.state === "loading" && <p className="text-small text-muted">Loading the PDF</p>}
      {state.state === "error" && <p className="text-small text-negative">Could not show the PDF: {state.error}</p>}
      {/* Filled by the effect above, never by React. */}
      <div ref={pages} className="flex flex-col gap-2" />
    </div>
  );
}
