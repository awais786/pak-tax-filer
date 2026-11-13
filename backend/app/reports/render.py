"""Rendering a PDF from the templates (feature 008, task T006; research R6).

Jinja2 HTML, then WeasyPrint. Figures are only formatted for reading, never calculated
(Principle I). WeasyPrint is CPU-bound, so it runs in a worker thread.
"""

from pathlib import Path
from typing import Any

import anyio
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATES = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
    # A missing or renamed field fails the test rather than printing blank (FR-006).
    undefined=StrictUndefined,
)


def rupees(amount: str | None) -> str:
    """ "1800000.00" -> "Rs 1,800,000.00"; the same reading the screens give (no arithmetic)."""
    if amount is None:
        return ""
    sign = "-" if amount.startswith("-") else ""
    whole, _, fraction = amount.lstrip("-").partition(".")
    grouped = f"{int(whole):,}" if whole.isdigit() else whole
    return f"{sign}Rs {grouped}{f'.{fraction}' if fraction else ''}"


def balance(amount: str | None, overpaid: str) -> str:
    """ "12000" -> "Rs 12,000 payable"; "-3000" -> "Rs 3,000 over-deducted"; "0" -> "Nothing to
    pay"; worded as the Tax page words it."""
    if amount is None:
        return ""
    if amount.lstrip("-").strip("0.") == "":
        return "Nothing to pay"
    if amount.startswith("-"):
        return f"{rupees(amount[1:])} {overpaid}"
    return f"{rupees(amount)} payable"


_TEMPLATES.globals.update(rupees=rupees, balance=balance)

# At most two renders at once: each takes about 70 MB, and the deployment is an e2-micro. Its own
# limiter, so PDFs never use up the thread pool the rest of the app shares.
_RENDERS = anyio.CapacityLimiter(2)


def _no_fetching(url: str, *args: Any, **kwargs: Any) -> Any:
    """Refuse every URL: the templates need none, so a template mistake can't make WeasyPrint
    read a local file or the network."""
    del args, kwargs
    raise ValueError(f"PDFs fetch nothing (asked for {url[:40]}).")


def _render(template: str, context: dict[str, Any]) -> bytes:
    html = _TEMPLATES.get_template(template).render(**context)
    # Imported here, not at the top: WeasyPrint loads Pango when imported, which only the Docker
    # image and CI have, and the app (and the contract check, run on the developer's machine)
    # must import without it.
    from weasyprint import HTML  # pylint: disable=import-outside-toplevel

    pdf: bytes = HTML(string=html, url_fetcher=_no_fetching).write_pdf()
    return pdf


async def render_pdf(template: str, **context: Any) -> bytes:
    """The PDF for a template and its context, rendered off the event loop."""
    return await anyio.to_thread.run_sync(_render, template, context, limiter=_RENDERS)
