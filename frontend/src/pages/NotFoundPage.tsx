import { Link } from "react-router";

/** Any address the app doesn't have, instead of a blank page (PR #27 review, item 5). */
export function NotFoundPage() {
  return (
    <main>
      <h1>Page not found</h1>
      <p>There's no page at this address.</p>
      <p>
        <Link to="/">Go to the home page</Link>
      </p>
    </main>
  );
}
