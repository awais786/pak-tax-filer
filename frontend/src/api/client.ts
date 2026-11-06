// The one place the frontend calls the backend (feature 002, task T025, research R9).
// JSON in and out, the session cookie sent along, and a 401 treated as "session ended".

/** An error reply from the API, carrying its status and the server's `detail` message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let onSessionEnded: () => void = () => {};

/** Register what happens when a request finds the session has ended (set by AuthContext). */
export function setSessionEndedHandler(handler: () => void): void {
  onSessionEnded = handler;
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Don't treat a 401 as "session ended" (login itself, and the first "who am I" check). */
  allowUnauthenticated?: boolean;
};

/** Call the backend; resolves to the parsed JSON body (or undefined for 204). */
export async function apiFetch<T>(
  path: string,
  options: Options = {},
): Promise<T> {
  const { method = "GET", body, allowUnauthenticated = false } = options;
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    // State-changing requests always send JSON (the backend refuses anything else).
    body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
  });

  if (response.status === 204) {
    return undefined as T;
  }
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    // A successful reply must be JSON: anything else (e.g. a proxy's HTML error page) is an
    // error, never an empty success. Error replies may lack JSON; their status still counts.
    if (response.ok) {
      throw new ApiError(
        response.status,
        "The server sent an unexpected reply.",
      );
    }
    data = {};
  }
  if (!response.ok) {
    if (response.status === 401 && !allowUnauthenticated) {
      onSessionEnded();
    }
    throw new ApiError(response.status, detailMessage(data, response.status));
  }
  return data as T;
}

/**
 * The server's message: `detail` as text, or FastAPI's list of field errors (a 422) as
 * "field: reason; field: reason" (PR #27 review, item 2). Rejected values are never sent back
 * by the server, so nothing typed is echoed here.
 */
function detailMessage(data: unknown, status: number): string {
  const detail =
    typeof data === "object" && data !== null && "detail" in data
      ? data.detail
      : undefined;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const reasons = detail.flatMap((error: unknown) => {
      if (typeof error !== "object" || error === null || !("msg" in error)) {
        return [];
      }
      const field =
        "loc" in error && Array.isArray(error.loc)
          ? error.loc.filter((part: unknown) => part !== "body").join(".")
          : "";
      return [field ? `${field}: ${String(error.msg)}` : String(error.msg)];
    });
    if (reasons.length > 0) {
      return reasons.join("; ");
    }
  }
  return `Request failed (${status}).`;
}
