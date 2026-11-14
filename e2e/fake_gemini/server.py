"""A stand-in for Google's Gemini API, for the end-to-end tests only (e2e/README.md).

The app's real Gemini clients talk to it because the e2e stack sets GOOGLE_GEMINI_BASE_URL
(read by the google-genai SDK), so no test switch exists in the app and tests never call the real
AI. It tells requests apart by their structure (the response schema, tools, the endpoint), never
by prompt wording, and answers with fixed synthetic data:

- embeddings: fixed 768-number vectors;
- extraction of a salary certificate (`gross_salary` in the response schema): taxable salary
  Rs 1,800,000 and Rs 75,000 deducted (salary tax Rs 72,000, so Rs 3,000 over-deducted); a file
  containing E2E-GOOGLE-TIMEOUT gets Google's 504 instead;
- the guided run's agents (tools in the request): a short reply with no numbers;
- anything else (the summaries): a sentence with no numbers.

Only what a test needs is faked: anything else gets an error, so a new kind of request is added
here together with the test that needs it (e2e/README.md).

Standard library only. Run: python server.py (port 8080).
"""

import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = 8080
DIMENSIONS = 768
TIMEOUT_MARKER = b"E2E-GOOGLE-TIMEOUT"


def value(printed: str, label: str) -> dict[str, Any]:
    """One extracted figure, as Gemini reports it."""
    return {"value": printed, "confidence": "high", "page": 1, "label": label}


SALARY = {
    "document_type": "salary_certificate",
    "tax_year": value("2025-26", "Tax Year"),
    "gross_salary": value("Rs. 2,000,000/-", "Gross Salary"),
    "taxable_salary": value("Rs. 1,800,000/-", "Taxable Salary"),
    "tax_deducted": value("75,000", "Income Tax Deducted"),
}
SUMMARY = "Your result and how it was worked out are shown above."


def text_reply(text: str) -> dict[str, Any]:
    """A generateContent reply with one text part."""
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        "modelVersion": "fake-gemini-e2e",
    }


def schema_fields(request: dict[str, Any]) -> set[str]:
    """The property names of the reply schema the app asked for, if any."""
    config = request.get("generationConfig") or {}
    schema = config.get("responseJsonSchema") or config.get("responseSchema") or {}
    return set(schema.get("properties") or {})


def file_bytes(request: dict[str, Any]) -> bytes:
    """The uploaded file sent inline, if any."""
    for content in request.get("contents") or []:
        for part in content.get("parts") or []:
            data = (part.get("inlineData") or {}).get("data")
            if data:
                # URL-safe and unpadded, as the SDK sends it.
                return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return b""


def system_text(request: dict[str, Any]) -> str:
    """The system instruction's text (the agents' reply format names its keys)."""
    parts = (request.get("systemInstruction") or {}).get("parts") or []
    return " ".join(part.get("text", "") for part in parts)


def generate(request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The status and body for a generateContent request."""
    fields = schema_fields(request)
    if "gross_salary" in fields:
        if TIMEOUT_MARKER in file_bytes(request):
            error = {
                "code": 504,
                "message": "Deadline expired.",
                "status": "DEADLINE_EXCEEDED",
            }
            return 504, {"error": error}
        return 200, text_reply(json.dumps(SALARY))
    if fields:  # another reply schema no test needs yet (a bank certificate, the assistant)
        return 400, {"error": {"code": 400, "message": "Not faked.", "status": "INVALID_ARGUMENT"}}
    if request.get("tools"):
        if '"citations"' in system_text(request):
            return 200, text_reply(json.dumps({"note": "No passages to cite.", "citations": []}))
        return 200, text_reply(json.dumps({"message": "Your certificates look complete."}))
    return 200, text_reply(SUMMARY)


def embed(path: str, request: dict[str, Any]) -> dict[str, Any]:
    """Fixed vectors: one per request for a batch, else one."""
    vector = {"values": [0.1] * DIMENSIONS}
    if path.endswith(":batchEmbedContents"):
        return {"embeddings": [vector for _ in request.get("requests") or []]}
    return {"embedding": vector}


class Handler(BaseHTTPRequestHandler):
    """Answers the Gemini endpoints the app calls."""

    def do_POST(self) -> None:  # noqa: N802  # pylint: disable=invalid-name
        """generateContent and the embedding endpoints."""
        length = int(self.headers.get("Content-Length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        path = self.path.split("?", 1)[0]
        if path.endswith(":generateContent"):
            status, body = generate(request)
        elif path.endswith((":batchEmbedContents", ":embedContent")):
            status, body = 200, embed(path, request)
        else:
            status, body = (
                404,
                {
                    "error": {
                        "code": 404,
                        "message": "Not faked.",
                        "status": "NOT_FOUND",
                    }
                },
            )
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802  # pylint: disable=invalid-name
        """A health check for the stack's start-up."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=redefined-builtin
        """One short line per request, without bodies."""
        status = args[1] if len(args) > 1 else ""
        print(f"fake-gemini: {self.command} {self.path.split('?', 1)[0]} {status}")


if __name__ == "__main__":
    print(f"fake-gemini listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
