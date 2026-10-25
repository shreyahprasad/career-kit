// Sizing for PdfView. Kept apart from pdf.js, so it is tested without loading it.

/** The finest PdfView draws: past 3 the eye sees no difference, and iOS Safari refuses a canvas
 * much over 16 million pixels. */
export const MAX_PIXEL_RATIO = 3;

/** The pdf.js scale that fits a page pageWidth points wide to a box boxWidth CSS pixels wide, on a
 * screen with pixelRatio device pixels to each CSS pixel. */
export const pdfScale = (pageWidth: number, boxWidth: number, pixelRatio: number) =>
  (boxWidth / pageWidth) * Math.min(Math.max(pixelRatio, 1), MAX_PIXEL_RATIO);
