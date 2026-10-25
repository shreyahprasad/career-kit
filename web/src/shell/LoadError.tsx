import { ApiError, START_API } from "./api";

// What a page shows when its data did not load. An answer from the API explains itself (its
// detail is in the message); no answer, or a proxy error, means the API is not running.

export function LoadError({ what, error, className = "" }: { what: string; error: Error; className?: string }) {
  const unreachable = !(error instanceof ApiError) || error.status >= 500;
  return (
    <div className={`flex flex-col gap-2 text-muted ${className}`}>
      <span className="text-fg">Could not load {what}.</span>
      <span className="num">{error.message}</span>
      {unreachable && (
        <span>
          Is the data server running? <code className="font-mono text-fg">{START_API}</code>
        </span>
      )}
    </div>
  );
}
