import { describe, expect, it } from "vitest";
import { MAX_PIXEL_RATIO, pdfScale } from "./pdf";

describe("pdfScale", () => {
  it("fits a page to the box width, sharp on the screen's pixels", () => {
    // A US letter page is 612 points wide.
    expect(pdfScale(612, 306, 2)).toBe(1);
    expect(pdfScale(612, 612, 1)).toBe(1);
  });

  it("draws no finer than MAX_PIXEL_RATIO, so a big canvas stays under the phone's limit", () => {
    expect(pdfScale(612, 306, MAX_PIXEL_RATIO + 2)).toBe(pdfScale(612, 306, MAX_PIXEL_RATIO));
  });

  it("draws at least one pixel per pixel on an odd screen", () => {
    expect(pdfScale(612, 612, 0)).toBe(1);
  });
});
