import { useId, useState } from "react";
import { ApiError, apiDownload } from "../api/client";

// The PDF download (feature 008, tasks T005, T008). The backend makes the PDF, with the
// practitioner label and validation status on every page; this fetches it (the session cookie
// goes along) and saves it, says why it failed, or says why the result can't be exported.

export function DownloadPdfButton({
  url,
  disabledReason,
}: {
  /** Where the PDF comes from (built in src/api). */
  url: string;
  /** Why the result can't be exported (blocked, not ready, not approved), or null. */
  disabledReason: string | null;
}) {
  const reasonId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (disabledReason !== null) {
    return (
      <p className="pdf-download">
        <button type="button" aria-disabled="true" aria-describedby={reasonId}>
          Download PDF
        </button>{" "}
        <span id={reasonId} className="hint">
          {disabledReason}
        </span>
      </p>
    );
  }

  async function download() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const { blob, filename } = await apiDownload(url);
      save(blob, filename);
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Couldn't reach PakTaxFiler. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <p className="pdf-download">
      <button
        type="button"
        className="button"
        aria-disabled={busy}
        onClick={download}
      >
        Download PDF
      </button>{" "}
      {error !== null && (
        <span role="alert" className="hint">
          {error}
        </span>
      )}
    </p>
  );
}

/** Hand the file to the browser as a download under the server's name for it. */
function save(blob: Blob, filename: string) {
  const address = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = address;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  // Released once the browser has started the download.
  window.setTimeout(() => URL.revokeObjectURL(address), 1000);
}
