// Reads from the data API (api/main.py), proxied at /api by vite.config.ts. Every plugin's
// data.ts fetches through getJSON, so a failed load carries its status and the API's own
// explanation (FastAPI's `detail`, e.g. "career.db not found. Run ...").

/** How to start the API, for error messages: start.sh knows the ports, moved in .env or not. */
export const START_API = "./start.sh";

export class ApiError extends Error {
  status: number;

  constructor(path: string, status: number, detail: string | null) {
    super(`${path} returned ${status}${detail ? `: ${detail}` : ""}`);
    this.status = status;
  }
}

export async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(path, res.status, typeof body?.detail === "string" ? body.detail : null);
  }
  return res.json();
}

// ── Writes ───────────────────────────────────────────────────────────────────
// Changes go to the writers in tools/ (built on tools/writekit, see docs/writers.md), never to
// the read-only API. Each writer refuses a change without this header (writekit/app.py).

export const WRITE_HEADER = "X-Career-Kit-Write";

/** Each change goes with a fresh key; sent again with it, the writer makes it once and answers the
 * same (writekit/app.py). */
export const IDEMPOTENCY_HEADER = "Idempotency-Key";

/** The waits before each try again, when the change may not have arrived: the network dropped it,
 * or tailscale serve could not reach the writer. About 10s in all, since the phone's Tailscale can
 * take a few seconds to come back when Safari reopens the page. Its key makes trying again safe. */
export const RETRY_DELAYS_MS = [500, 1500, 3000, 5000];
const RETRY_STATUSES = new Set([502, 503, 504]);

/** A change a writer did not make. message is the writer's reason, in your words, ready to show. */
export class Refusal extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** FastAPI's `detail`: a sentence from a writer, or for a 422 the fields that were wrong. */
function reason(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join("."), d.msg?.replace(/^Value error, /, "")].filter(Boolean).join(": "),
      )
      .join("; ");
  return null;
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Sends one change to a writer and returns its JSON. A refusal throws a Refusal with the reason.
 * A change that may not have arrived is tried again with the same key (RETRY_DELAYS_MS).
 * keepalive lets it finish after the page is gone, for a last change sent as the page hides
 * (sendBeacon cannot carry WRITE_HEADER). */
export async function send<T>(
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  body?: unknown,
  { keepalive = false }: { keepalive?: boolean } = {},
): Promise<T> {
  const init: RequestInit = {
    method,
    ...(keepalive ? { keepalive } : {}),
    headers: {
      [WRITE_HEADER]: "1",
      [IDEMPOTENCY_HEADER]: crypto.randomUUID(),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
  let res: Response | null = null;
  for (const delay of [0, ...RETRY_DELAYS_MS]) {
    if (delay) await wait(delay);
    res = await fetch(path, init).catch(() => null);
    if (res && !RETRY_STATUSES.has(res.status)) break;
  }
  if (!res) throw new Refusal(0, "Could not reach the writer. Check your connection and try again.");
  if (!res.ok) {
    const detail = await res.json().then((j) => j.detail, () => null);
    throw new Refusal(res.status, reason(detail) ?? `${path} returned ${res.status}`);
  }
  return res.json();
}
