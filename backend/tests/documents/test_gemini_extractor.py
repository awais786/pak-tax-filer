"""The real Gemini client, tested through the SDK with a fake network (task T036, research R1/R8).

No API key or quota: an httpx2 MockTransport answers in place of Google, so these tests check the
exact request we send and how every kind of reply or failure is handled.
"""

import base64
import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from google import genai
from google.genai import types

from app.documents.extraction.client import GeminiExtractor
from app.documents.extraction.prompt import SYSTEM_PROMPT
from app.documents.models import DocType, FieldName

pytestmark = pytest.mark.anyio

PDF = b"%PDF-1.7 synthetic"
PNG = b"\x89PNG\r\n\x1a\n synthetic"
FAKE_KEY = "test-key-not-real"

BANK_REPLY = {
    "document_type": "bank_profit_certificate",
    "tax_year": {"value": "2025-26", "confidence": "high", "page": 1, "label": "Tax Year"},
    "profit_amount": {"value": "Rs. 120,000", "confidence": "high", "page": 1, "label": "Profit"},
    "tax_withheld": {"value": None, "confidence": "low", "page": None, "label": None},
}

Handler = Callable[[httpx2.Request], httpx2.Response]


def reply(
    text: str | None = None,
    finish: str = "STOP",
    model: str = "gemini-3.8-flash-001",
    blocked: str | None = None,
) -> Any:
    """A generateContent reply body."""
    body: dict[str, Any] = {
        "usageMetadata": {"promptTokenCount": 1200, "candidatesTokenCount": 80},
        "modelVersion": model,
    }
    if blocked is not None:
        body["promptFeedback"] = {"blockReason": blocked}
        return body
    parts = [{"text": text}] if text is not None else []
    body["candidates"] = [{"content": {"role": "model", "parts": parts}, "finishReason": finish}]
    return body


def extractor(handler: Handler, api_key: str | None = FAKE_KEY) -> GeminiExtractor:
    """A GeminiExtractor whose SDK client talks to `handler` instead of Google."""
    client = genai.Client(
        api_key=FAKE_KEY,
        http_options=types.HttpOptions(
            httpx_async_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    return GeminiExtractor(api_key=api_key, model="gemini-3.8-flash", effort="low", client=client)


def replying(body: Any, status: int = 200, sent: list[httpx2.Request] | None = None) -> Handler:
    """A handler that records each request and answers with `body`."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if sent is not None:
            sent.append(request)
        return httpx2.Response(status, json=body)

    return handle


async def test_pdf_request_has_the_file_instructions_schema_and_thinking_level() -> None:
    """Fails if the request drifts from research R1 (PDF part, prompt, JSON schema, thinking)."""
    sent: list[httpx2.Request] = []
    gemini = extractor(replying(reply(json.dumps(BANK_REPLY)), sent=sent))

    await gemini.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert len(sent) == 1
    request = sent[0]
    assert request.url.path.endswith("/models/gemini-3.8-flash:generateContent")
    assert request.headers["x-goog-api-key"] == FAKE_KEY
    body = json.loads(request.content)
    file_part, instruction = body["contents"][0]["parts"]
    assert file_part["inlineData"]["mime_type"] == "application/pdf"
    assert file_part["inlineData"]["data"] == base64.b64encode(PDF).decode()
    assert "profit certificate" in instruction["text"]
    assert body["systemInstruction"]["parts"][0]["text"] == SYSTEM_PROMPT
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert set(config["responseJsonSchema"]["properties"]) == set(BANK_REPLY)
    assert config["thinkingConfig"]["thinking_level"] == "LOW"


async def test_image_is_sent_with_its_own_media_type() -> None:
    """Fails if a photo is sent as a PDF (the model must know what it is reading)."""
    sent: list[httpx2.Request] = []
    salary: dict[str, object] = {name.value: BANK_REPLY["tax_year"] for name in list(FieldName)[:4]}
    salary["document_type"] = "salary_certificate"
    gemini = extractor(replying(reply(json.dumps(salary)), sent=sent))

    await gemini.extract(DocType.SALARY_CERTIFICATE, PNG, "image/png")

    file_part = json.loads(sent[0].content)["contents"][0]["parts"][0]
    assert file_part["inlineData"]["mime_type"] == "image/png"


async def test_reply_becomes_fields_and_records_the_model_and_tokens() -> None:
    """Fails if values, not-found fields, the model that answered or token counts are lost."""
    gemini = extractor(replying(reply(json.dumps(BANK_REPLY))))

    result = await gemini.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is None
    assert result.model == "gemini-3.8-flash-001"
    assert result.fields["profit_amount"].value == "Rs. 120,000"
    assert result.fields["profit_amount"].label == "Profit"
    assert result.fields["tax_withheld"].value is None
    assert (result.input_tokens, result.output_tokens) == (1200, 80)


async def test_without_an_api_key_nothing_is_sent() -> None:
    """Fails if a missing key makes a request, or fails without saying why."""
    sent: list[httpx2.Request] = []
    gemini = extractor(replying(reply(), sent=sent), api_key=None)

    result = await gemini.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert not sent
    assert result.failure_reason is not None
    assert "key" in result.failure_reason
    assert not result.fields


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (reply(blocked="SAFETY"), "declined"),
        (reply(json.dumps(BANK_REPLY), finish="SAFETY"), "declined"),
        (reply(json.dumps(BANK_REPLY), finish="MAX_TOKENS"), "incomplete"),
        (reply(None), "incomplete"),
        (reply("not json"), "incomplete"),
        (reply(json.dumps({"tax_year": BANK_REPLY["tax_year"]})), "incomplete"),
    ],
    ids=["prompt-blocked", "answer-blocked", "cut-off", "empty", "not-json", "missing-fields"],
)
async def test_blocked_cut_off_or_unusable_replies_fail_cleanly(body: Any, expected: str) -> None:
    """Fails if a blocked, truncated or malformed answer is treated as figures (R1)."""
    gemini = extractor(replying(body))

    result = await gemini.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is not None
    assert expected in result.failure_reason
    assert not result.fields


@pytest.mark.parametrize(
    ("status", "expected", "limit_reached", "service_failed"),
    [
        (429, "free AI limit", True, False),
        (500, "busy", False, True),
        (503, "busy", False, True),
        (504, "busy", False, True),  # Google's 60-second deadline (seen live, 2026-11-12)
        (401, "key", False, False),
        (403, "key", False, False),
        (400, "couldn't read", False, False),
    ],
)
async def test_api_errors_become_short_reasons(
    status: int, expected: str, limit_reached: bool, service_failed: bool
) -> None:
    """Fails if an API error escapes, its reason is unclear, or its details leak (R1)."""
    error = {"error": {"code": status, "message": "secret details", "status": "X"}}
    gemini = extractor(replying(error, status=status))

    result = await gemini.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is not None
    assert expected in result.failure_reason
    assert "secret details" not in result.failure_reason
    assert result.limit_reached is limit_reached
    # Google's side failed (5xx): the try isn't charged to the user (FR-017, amended).
    assert result.service_failed is service_failed


async def test_an_invalid_key_is_reported_as_the_key_not_the_file() -> None:
    """Fails if Gemini's 400 for a bad key (found in quickstart 3.1, 2026-11-10) tells the user
    their file couldn't be read. Told apart by Google's structured reason, never message text."""
    error = {
        "error": {
            "code": 400,
            "message": "secret details",
            "status": "INVALID_ARGUMENT",
            "details": [
                {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}
            ],
        }
    }
    gemini = extractor(replying(error, status=400))

    result = await gemini.extract(DocType.SALARY_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason == "The AI service didn't accept the app's key."


@pytest.mark.parametrize(
    ("network_error", "expected"),
    [(httpx2.ReadTimeout("slow"), "busy"), (httpx2.ConnectError("down"), "reach")],
)
async def test_network_failures_become_short_reasons(
    network_error: Exception, expected: str
) -> None:
    """Fails if a timeout or lost connection escapes instead of failing the document."""

    def fail(_request: httpx2.Request) -> httpx2.Response:
        raise network_error

    result = await extractor(fail).extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is not None
    assert expected in result.failure_reason
    assert "Retry" in result.failure_reason
    assert result.service_failed is True


@pytest.mark.parametrize(
    ("seen", "expected"),
    [
        (
            "salary_certificate",
            "This doesn't look like a bank profit certificate. It may be a salary certificate: "
            'if it is, choose "Salary certificate" as the type and upload it again.',
        ),
        (
            "other",
            "This doesn't look like a bank profit certificate. "
            "Check the file and the type you chose.",
        ),
    ],
)
async def test_a_document_of_another_type_fails_with_a_clear_reason(
    seen: str, expected: str
) -> None:
    """Fails if a document of the wrong type is reviewed as empty fields, or the message doesn't
    say which type to choose when the AI has a guess, still only as a hint (FR-005a)."""
    gemini = extractor(replying(reply(json.dumps({**BANK_REPLY, "document_type": seen}))))

    result = await gemini.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason == expected
    assert result.wrong_type is True
    assert not result.fields


def with_app_retries(handler: Handler) -> GeminiExtractor:
    """A GeminiExtractor using its own retry settings, talking to `handler` instead of Google."""
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return GeminiExtractor(api_key=FAKE_KEY, model="gemini-test", effort="low", http_client=http)


def answers(*statuses: int) -> tuple[Handler, list[httpx2.Request]]:
    """A handler answering each request with the next status (200 = a good reply)."""
    sent: list[httpx2.Request] = []
    queue = list(statuses)

    def handle(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        status = queue.pop(0) if queue else 200
        if status == 200:
            return httpx2.Response(200, json=reply(json.dumps(BANK_REPLY)))
        error = {"error": {"code": status, "message": "busy", "status": "UNAVAILABLE"}}
        return httpx2.Response(status, json=error)

    return handle, sent


async def test_temporary_server_errors_are_retried() -> None:
    """Fails if a brief Google outage (503) fails the upload instead of being retried."""
    handler, sent = answers(503, 503)

    result = await with_app_retries(handler).extract(
        DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf"
    )

    assert result.failure_reason is None
    assert len(sent) == 3


async def test_a_lasting_outage_still_fails_cleanly() -> None:
    """Fails if retries go on forever or the final failure loses its short reason."""
    handler, sent = answers(503, 503, 503, 503)

    result = await with_app_retries(handler).extract(
        DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf"
    )

    assert len(sent) == 3
    assert result.failure_reason is not None
    assert "busy" in result.failure_reason


async def test_a_deadline_timeout_is_not_retried() -> None:
    """Fails if a 504 (the 60-second deadline) is retried, making the user wait minutes."""
    handler, sent = answers(504)

    result = await with_app_retries(handler).extract(
        DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf"
    )

    assert len(sent) == 1
    assert result.failure_reason is not None


async def test_a_wrong_type_answer_is_flagged() -> None:
    """Fails if the router can't tell a wrong-type refusal from other failures (FR-005a)."""
    body = reply(json.dumps({**BANK_REPLY, "document_type": "salary_certificate"}))

    result = await extractor(replying(body)).extract(
        DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf"
    )

    assert result.wrong_type is True
    assert result.limit_reached is False
