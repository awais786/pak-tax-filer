import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// React Testing Library only cleans up automatically when Vitest's globals are on; they aren't,
// so unmount whatever each test rendered here. Without this, a second test in a file sees the
// first test's page too.
afterEach(cleanup);
