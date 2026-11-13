"""Running one agent (feature 007, tasks T006 and T009; research R4).

An agent gets instructions, a prompt, its own read-only tools and the shape of its final answer.
The client runs the tool loop (the model asks for a tool, the toolbox answers, the model goes on)
and returns the structured answer, or raises AgentError (or TimeoutError). The real client uses
Gemini (T009); FakeAgentClient follows a script for tests, calling the real toolbox.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

import httpx2
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.documents.extraction.client import THINKING_LEVELS
from app.rag.answer import GOOGLE_DEADLINE_MS, RETRY
from app.telemetry.ai import record_gemini_usage, tool_call
from app.workflow.settings import MAX_SEARCHES
from app.workflow.tools import Toolbox

Reply = TypeVar("Reply", bound=BaseModel)


class AgentError(Exception):
    """The agent couldn't give a usable answer (API error, refusal, a forbidden tool, a reply
    in the wrong shape). The step then uses its plain result."""


class AgentClient(Protocol):  # pylint: disable=too-few-public-methods
    """Runs one agent to its final answer."""

    async def run(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        agent: str,
        instructions: str,
        prompt: str,
        tools: Toolbox,
        allowed: frozenset[str],
        reply: type[Reply],
    ) -> Reply:
        """The agent's final answer, in the shape of `reply`."""
        ...  # pylint: disable=unnecessary-ellipsis


async def call_tool(
    tools: Toolbox, allowed: frozenset[str], name: str, arguments: Mapping[str, Any]
) -> Any:
    """Run one tool the agent asked for; anything outside its own tools is refused."""
    if name not in allowed:
        raise AgentError(f"The agent asked for a tool it doesn't have: {name}.")
    # One of the agent's own tools (checked above), so the name is never the model's free text.
    with tool_call(name):
        try:
            return await getattr(tools, name)(**arguments)
        except TypeError as exc:
            raise AgentError(f"The agent called {name} with the wrong arguments.") from exc
        except (AttributeError, ValueError) as exc:
            # E.g. a number where the tool expects text (backend review M2).
            raise AgentError(f"The agent called {name} with unusable arguments.") from exc


@dataclass
class Script:
    """What one fake agent does: tool calls in order, then its reply (or an error to raise)."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    reply: dict[str, Any] | BaseException = field(default_factory=dict)


@dataclass
class FakeAgentClient:
    """Scripted agents for tests, keyed by agent name; records every tool call. An agent with
    no script fails, as if the AI were unavailable."""

    scripts: dict[str, Script] = field(default_factory=dict)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    async def run(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        agent: str,
        instructions: str,
        prompt: str,
        tools: Toolbox,
        allowed: frozenset[str],
        reply: type[Reply],
    ) -> Reply:
        """Make the scripted tool calls, then return the scripted reply or raise it."""
        del instructions, prompt
        script = self.scripts.get(agent)
        if script is None:
            raise AgentError("No AI in tests.")
        for name, arguments in script.calls:
            self.calls.append((agent, name, arguments))
            await call_tool(tools, allowed, name, arguments)
        if isinstance(script.reply, BaseException):
            raise script.reply
        try:
            return reply.model_validate(script.reply)
        except ValidationError as exc:
            raise AgentError("The reply wasn't in the expected form.") from exc


# The tools' parameters, as Gemini's function declarations need them (contracts/workflow-api.md).
_PARAMETERS: dict[str, tuple[str, ...]] = {
    "list_confirmed_documents": (),
    "validate_salary_information": ("tax_year", "gross_salary", "taxable_salary", "tax_deducted"),
    "check_bank_certificate": ("tax_year", "profit_amount", "tax_withheld"),
    "search_tax_documents": ("query",),
}
# Enough for a few tool calls and the answer; a model still calling tools after this is stopped.
MAX_TURNS = 6


class GeminiAgentClient:  # pylint: disable=too-few-public-methods
    """Runs an agent with Gemini function calling (free tier); any failure is an AgentError."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._effort = effort
        self._http_client = http_client

    async def run(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        agent: str,
        instructions: str,
        prompt: str,
        tools: Toolbox,
        allowed: frozenset[str],
        reply: type[Reply],
    ) -> Reply:
        """Call tools as Gemini asks (only the agent's own, at most MAX_SEARCHES searches),
        then read its final JSON answer."""
        del agent
        if not self._api_key:
            raise AgentError("No GEMINI_API_KEY is set.")
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                retry_options=RETRY, httpx_async_client=self._http_client
            ),
        )
        config = types.GenerateContentConfig(
            system_instruction=f"{instructions}\n\n{_answer_format(reply)}",
            tools=[types.Tool(function_declarations=[_declaration(n) for n in sorted(allowed)])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVELS[self._effort]),
            max_output_tokens=800,
            http_options=types.HttpOptions(timeout=GOOGLE_DEADLINE_MS),
        )
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=prompt)])
        ]
        searches = [0]  # how many searches so far, shared across turns
        for _ in range(MAX_TURNS):
            response = await _generate(client, self._model, contents, config)
            calls = response.function_calls or []
            if not calls:
                return _final(response, reply)
            contents.append(response.candidates[0].content)  # type: ignore[index,arg-type]
            parts = [await _answer(call, tools, allowed, searches) for call in calls]
            contents.append(types.Content(role="user", parts=parts))
        raise AgentError("The agent didn't finish.")


async def _answer(
    call: types.FunctionCall, tools: Toolbox, allowed: frozenset[str], searches: list[int]
) -> types.Part:
    """The toolbox's answer to one tool call; a search past MAX_SEARCHES gets an error back."""
    name = call.name or ""
    result: Any
    if name == "search_tax_documents" and searches[0] >= MAX_SEARCHES:
        result = {"error": "No more searches."}
    else:
        searches[0] += name == "search_tax_documents"
        result = await call_tool(tools, allowed, name, call.args or {})
    return types.Part.from_function_response(name=name, response={"result": result})


async def _generate(
    client: genai.Client,
    model: str,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
) -> types.GenerateContentResponse:
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
    except (errors.APIError, httpx2.HTTPError) as exc:
        raise AgentError(type(exc).__name__) from exc
    record_gemini_usage(response.usage_metadata)
    candidates = response.candidates or []
    if not candidates or candidates[0].finish_reason != types.FinishReason.STOP:
        raise AgentError("The reply was cut short or blocked.")
    return response


def _final(response: types.GenerateContentResponse, reply: type[Reply]) -> Reply:
    """The final answer: JSON in the model's text (fences allowed), in the shape of `reply`."""
    text = (response.text or "").strip().removeprefix("```json").removeprefix("```")
    text = text.removesuffix("```").strip()
    try:
        return reply.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AgentError("The reply wasn't in the expected form.") from exc


def _declaration(name: str) -> types.FunctionDeclaration:
    method = getattr(Toolbox, name)
    parameters = _PARAMETERS[name]
    return types.FunctionDeclaration(
        name=name,
        description=(method.__doc__ or name).strip(),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={p: types.Schema(type=types.Type.STRING) for p in parameters},
            required=list(parameters),
        )
        if parameters
        else None,
    )


def _answer_format(reply: type[BaseModel]) -> str:
    fields = ", ".join(f'"{name}"' for name in reply.model_fields)
    return (
        "When you have finished with the tools, reply with only a JSON object with the keys "
        f"{fields}."
    )
