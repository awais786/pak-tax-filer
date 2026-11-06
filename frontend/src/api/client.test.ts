import { afterEach, expect, test, vi } from "vitest";
import { apiFetch } from "./client";

// The API helper (frontend review L5).

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a successful reply that isn't JSON is an error, not an empty success", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response("<html>proxy error page</html>", { status: 200 }),
    ),
  );

  await expect(apiFetch("/api/auth/me")).rejects.toThrow();
});

test("a 422 shows which field failed and why, not just the status (PR #27 review, item 2)", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            detail: [
              {
                type: "extra_forbidden",
                loc: ["body", "cnic"],
                msg: "Extra inputs are not permitted",
              },
              {
                type: "bool_type",
                loc: ["body", "on_atl"],
                msg: "Input should be a valid boolean",
              },
            ],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
    ),
  );

  await expect(apiFetch("/api/profile", { method: "PUT" })).rejects.toThrow(
    "cnic: Extra inputs are not permitted; on_atl: Input should be a valid boolean",
  );
});
