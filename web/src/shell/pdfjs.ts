// pdf.js and its worker, set up once. Loaded only by PdfView's import(), so pages without a PDF
// never download it.
//
// The legacy build, not the default one: the default build reads a PDF's fonts with browser
// features only months old (Math.sumPrecise), and where they are missing it draws the page in a
// stand-in font that loses letters ("Airfow" for "Airflow"). The legacy build brings its own.

import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import workerSrc from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

export { pdfjs };
