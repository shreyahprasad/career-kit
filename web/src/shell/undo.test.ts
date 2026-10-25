import { afterEach, describe, expect, it, vi } from "vitest";
import { currentUndo, dismissUndo, offerUndo, undo, UNDO_MS } from "./undo";

afterEach(() => {
  dismissUndo();
  vi.useRealTimers();
});

describe("undo", () => {
  it("is offered for UNDO_MS after a delete, then gone", () => {
    vi.useFakeTimers();
    offerUndo({ what: "Acme FDE", restore: async () => {} });
    vi.advanceTimersByTime(UNDO_MS - 1);
    expect(currentUndo()?.what).toBe("Acme FDE");
    vi.advanceTimersByTime(1);
    expect(currentUndo()).toBeNull();
  });

  it("a newer delete replaces the offer, with its own full time", () => {
    vi.useFakeTimers();
    offerUndo({ what: "first", restore: async () => {} });
    vi.advanceTimersByTime(UNDO_MS - 1);
    offerUndo({ what: "second", restore: async () => {} });
    vi.advanceTimersByTime(UNDO_MS - 1);
    expect(currentUndo()?.what).toBe("second");
  });

  it("undoing restores, clears the offer, then runs after", async () => {
    const order: string[] = [];
    const offer = { what: "x", restore: async () => void order.push("restore"), after: () => void order.push("after") };
    offerUndo(offer);
    await undo(offer);
    expect(order).toEqual(["restore", "after"]);
    expect(currentUndo()).toBeNull();
  });

  it("a refused restore keeps the offer up and throws the reason", async () => {
    const offer = { what: "x", restore: async () => Promise.reject(new Error("No role x.")) };
    offerUndo(offer);
    await expect(undo(offer)).rejects.toThrow("No role x.");
    expect(currentUndo()).toBe(offer);
  });
});
