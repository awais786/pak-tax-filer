import { expect, test } from "vitest";
import { safeNext } from "./navigation";

// The open-redirect guard (frontend review H1, M1): `next` may only lead within this app.

test.each([
  [null, "/"],
  ["", "/"],
  ["/", "/"],
  ["/profile", "/profile"],
  ["/profile?x=1#part", "/profile?x=1#part"],
])("keeps in-app pages: %s → %s", (next, expected) => {
  expect(safeNext(next)).toBe(expected);
});

test.each([
  "//evil.example",
  "https://evil.example",
  "http://evil.example/login",
  "/\\evil.example",
  "/\t/evil.example",
  "javascript:alert(1)",
])("sends anything that would leave the app to the home page: %s", (next) => {
  expect(safeNext(next)).toBe("/");
});

test("never sends the user back to the login page itself", () => {
  expect(safeNext("/login")).toBe("/");
  expect(safeNext("/login?next=/profile")).toBe("/");
});

test("the login page is caught however it's written (PR #27 review, item 3)", () => {
  expect(safeNext("/Login")).toBe("/");
  expect(safeNext("/LOGIN?next=/profile")).toBe("/");
  expect(safeNext("/login/")).toBe("/");
});
