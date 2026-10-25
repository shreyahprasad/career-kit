import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getJSON, IDEMPOTENCY_HEADER, Refusal, RETRY_DELAYS_MS, send, WRITE_HEADER } from "./api";

const respond = (body: string, status: number) => vi.stubGlobal("fetch", async () => new Response(body, { status }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

// Every change carries a fresh key (the tests below match it with KEY).
const KEY = { [IDEMPOTENCY_HEADER]: expect.stringMatching(/^[0-9a-f-]{36}$/) };

describe("getJSON", () => {
  it("returns the body", async () => {
    respond('{"a":1}', 200);
    await expect(getJSON("/api/x")).resolves.toEqual({ a: 1 });
  });

  it("carries the status and the API's detail on failure", async () => {
    respond('{"detail":"x.db not found. Run seed.py."}', 404);
    const error = await getJSON("/api/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, message: "/api/x returned 404: x.db not found. Run seed.py." });
  });

  it("copes with a failure that is not JSON", async () => {
    respond("Bad Gateway", 502);
    await expect(getJSON("/api/x")).rejects.toThrow("/api/x returned 502");
  });
});

describe("send", () => {
  it("sends the write header and the body as JSON, and returns the reply", async () => {
    const fetch = vi.fn(async () => new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await expect(send("/api/x/write", "POST", { a: 1 })).resolves.toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledWith("/api/x/write", {
      method: "POST",
      headers: { [WRITE_HEADER]: "1", ...KEY, "Content-Type": "application/json" },
      body: '{"a":1}',
    });
  });

  it("sends no body or content type when there is nothing to send", async () => {
    const fetch = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await send("/api/x/write/1/commit", "POST");
    expect(fetch).toHaveBeenCalledWith("/api/x/write/1/commit", { method: "POST", headers: { [WRITE_HEADER]: "1", ...KEY }, body: undefined });
  });

  it("sends a DELETE with the header and no body", async () => {
    const fetch = vi.fn(async () => new Response('{"deleted":true}', { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await expect(send("/api/x/write/things/1", "DELETE")).resolves.toEqual({ deleted: true });
    expect(fetch).toHaveBeenCalledWith("/api/x/write/things/1", { method: "DELETE", headers: { [WRITE_HEADER]: "1", ...KEY }, body: undefined });
  });

  it("throws the writer's reason as is", async () => {
    respond('{"detail":"Upload 1 is discarded."}', 409);
    const error = await send("/api/x/write", "POST").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(Refusal);
    expect(error).toMatchObject({ status: 409, message: "Upload 1 is discarded." });
  });

  it("names the fields a 422 found wrong", async () => {
    respond('{"detail":[{"loc":["body","person","name"],"msg":"Field required"},{"loc":["body","kind"],"msg":"Input should be \'call\'"}]}', 422);
    await expect(send("/api/x/write", "POST", {})).rejects.toThrow("person.name: Field required; kind: Input should be 'call'");
  });

  it("copes with a failure that is not JSON", async () => {
    respond("Internal Server Error", 500); // a 502 is tried again, below
    await expect(send("/api/x/write", "POST")).rejects.toThrow("/api/x/write returned 500");
  });

  it("asks the browser to finish a keepalive change after the page is gone", async () => {
    const fetch = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await send("/api/x/write", "POST", { a: 1 }, { keepalive: true });
    expect(fetch).toHaveBeenCalledWith("/api/x/write", expect.objectContaining({ keepalive: true }));
  });

  it("sends each change with its own key", async () => {
    const fetch = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await send("/api/x/write", "POST");
    await send("/api/x/write", "POST");
    const keys = fetch.mock.calls.map((c) => (c as unknown as [string, RequestInit])[1].headers as Record<string, string>).map((h) => h[IDEMPOTENCY_HEADER]);
    expect(new Set(keys).size).toBe(2);
  });

  it("tries again with the same key when the network drops it, so it is saved once", async () => {
    vi.useFakeTimers();
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Load failed"))
      .mockResolvedValueOnce(new Response("", { status: 502 }))
      .mockResolvedValueOnce(new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const sent = send("/api/x/write", "POST", { a: 1 });
    await vi.advanceTimersByTimeAsync(RETRY_DELAYS_MS.reduce((a, b) => a + b, 0));
    await expect(sent).resolves.toEqual({ ok: true });
    const keys = fetch.mock.calls.map((c) => (c[1] as RequestInit).headers as Record<string, string>).map((h) => h[IDEMPOTENCY_HEADER]);
    expect(keys).toHaveLength(3);
    expect(new Set(keys).size).toBe(1);
  });

  it("gives up after its last try with what went wrong", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Load failed")));
    const sent = send("/api/x/write", "POST").catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(RETRY_DELAYS_MS.reduce((a, b) => a + b, 0));
    expect(await sent).toMatchObject({ message: "Could not reach the writer. Check your connection and try again." });
  });

  it("does not try a refusal again", async () => {
    const fetch = vi.fn(async () => new Response('{"detail":"no"}', { status: 409 }));
    vi.stubGlobal("fetch", fetch);
    await expect(send("/api/x/write", "POST")).rejects.toThrow("no");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
