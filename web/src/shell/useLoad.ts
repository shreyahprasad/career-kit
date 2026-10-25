import { useCallback, useEffect, useState } from "react";

// A page's data as it loads: loading, an error to show (shell/LoadError), or ready. reload()
// fetches again after a change but keeps showing what is there until the new data arrives, so
// the page never blanks between a tap and its result. A change of key loads afresh.

export type Load<T> = { state: "loading" } | { state: "error"; error: Error } | { state: "ready"; data: T };

export function useLoad<T>(fetcher: (signal?: AbortSignal) => Promise<T>, key: string): { load: Load<T>; reload: () => Promise<void> } {
  const [load, setLoad] = useState<Load<T>>({ state: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    setLoad({ state: "loading" });
    fetcher(ctrl.signal)
      .then((data) => setLoad({ state: "ready", data }))
      .catch((error: Error) => {
        if (!ctrl.signal.aborted) setLoad({ state: "error", error });
      });
    return () => ctrl.abort();
  }, [key]); // the key names what is loaded; fetcher is a fresh closure on every render

  const reload = useCallback(async () => {
    try {
      setLoad({ state: "ready", data: await fetcher() });
    } catch (error) {
      setLoad({ state: "error", error: error as Error });
    }
  }, [key]);

  return { load, reload };
}
