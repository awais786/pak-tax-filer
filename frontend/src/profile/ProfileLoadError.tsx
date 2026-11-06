import { useProfile } from "./ProfileContext";

/** Shown when the profile couldn't be loaded: the reason, and a way to try again (review M2). */
export function ProfileLoadError() {
  const { error, retry } = useProfile();
  return (
    <main>
      <p role="alert">{error}</p>
      <button type="button" onClick={retry}>
        Try again
      </button>
    </main>
  );
}
