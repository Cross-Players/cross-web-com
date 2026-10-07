"""The agent loop: Claude researches with server-side web search/fetch, then
calls submit_article; each submission is validated and checked against the
site, and problems are sent back until the article passes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .prompts import SYSTEM_PROMPT, user_message
from .schema import SUBMIT_TOOL, Submission

MODEL = "claude-opus-5-5"
MAX_TURNS = 40          # API calls per run (research + writing + resubmissions)
MAX_SUBMISSIONS = 4     # failed submit_article attempts before giving up
MAX_PAUSES = 8          # consecutive pause_turn continuations
MAX_STREAM_ERRORS = 2   # unparseable tool JSON from the stream

# USD per million tokens / per search, for the cost estimate printed at the end.
PRICES = {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20, "search": 0.01}

TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 12},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 10, "max_content_tokens": 20000},
    SUBMIT_TOOL,
]

NUDGE = (
    "Please submit the finished article now by calling the submit_article tool "
    "with both the Vietnamese and English versions."
)


class AgentError(RuntimeError):
    pass


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0
    searches: int = 0
    calls: int = 0

    def add(self, usage: Any) -> None:
        self.calls += 1
        self.input += getattr(usage, "input_tokens", 0) or 0
        self.output += getattr(usage, "output_tokens", 0) or 0
        self.cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        server = getattr(usage, "server_tool_use", None)
        self.searches += getattr(server, "web_search_requests", 0) or 0

    def cost(self) -> float:
        p = PRICES
        return (
            self.input * p["input"] + self.output * p["output"]
            + self.cache_write * p["cache_write"] + self.cache_read * p["cache_read"]
        ) / 1e6 + self.searches * p["search"]

    def summary(self) -> str:
        return (
            f"{self.calls} API calls, {self.input + self.cache_write + self.cache_read:,} input tokens "
            f"({self.cache_read:,} from cache), {self.output:,} output tokens, {self.searches} web searches "
            f"= about ${self.cost():.2f}"
        )


@dataclass
class Result:
    submission: Submission
    usage: Usage
    attempts: int
    log: list[str] = field(default_factory=list)


def _echo(content: list[Any]) -> list[Any]:
    """Content to append to the history. After a mid-output refusal fallback,
    blocks before the last `fallback` marker that the fallback model never
    completed must not be echoed back (see the refusal-fallback docs)."""
    marks = [i for i, b in enumerate(content) if b.type == "fallback"]
    if not marks:
        return content
    cut = marks[-1]
    results = {getattr(b, "tool_use_id", None) for b in content if b.type.endswith("_tool_result")}
    keep = []
    for i, b in enumerate(content):
        if i < cut and b.type in ("thinking", "redacted_thinking", "tool_use"):
            continue
        if i < cut and b.type == "server_tool_use" and b.id not in results:
            continue
        keep.append(b)
    return keep


def _tool_uses(content: list[Any]) -> list[Any]:
    marks = [i for i, b in enumerate(content) if b.type == "fallback"]
    start = marks[-1] + 1 if marks else 0
    return [b for b in content[start:] if b.type == "tool_use"]


def _error(tool_use_id: str, message: str) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "is_error": True, "content": message}


def write_article(
    client: Any,
    topic: str,
    *,
    content_dir: Path,
    check: Callable[[Submission], list[str]],
    notes: str = "",
    today: date | None = None,
    model: str = MODEL,
    say: Callable[[str], None] = print,
) -> Result:
    today = today or date.today()
    usage = Usage()
    messages: list[dict] = [{"role": "user", "content": user_message(topic, notes, today, content_dir)}]
    failed_submissions = 0
    pauses = 0
    stream_errors = 0
    nudged = False
    last_problems: list[str] = []

    for _ in range(MAX_TURNS):
        try:
            with client.beta.messages.stream(
                model=model,
                max_tokens=64000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": "high"},
                cache_control={"type": "ephemeral"},
                fallbacks="default",
                betas=["server-side-fallback-2026-07-01"],
            ) as stream:
                response = stream.get_final_message()
        except ValueError as e:  # the stream could not parse a tool's JSON input
            stream_errors += 1
            if stream_errors > MAX_STREAM_ERRORS:
                raise AgentError(f"Claude kept sending unparseable tool input: {e}") from e
            say("  ! malformed tool input in the stream, asking again")
            continue

        usage.add(response.usage)
        content = _echo(list(response.content))
        for b in content:
            if b.type == "server_tool_use":
                arg = b.input.get("query") or b.input.get("url") or ""
                say(f"  {b.name}: {arg}")
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise AgentError(f"Claude declined the request ({getattr(details, 'category', None)}).")
        if response.stop_reason == "max_tokens":
            raise AgentError("The response hit max_tokens before finishing; try a narrower topic.")

        # History is append-only: never rewrite earlier turns.
        messages.append({"role": "assistant", "content": content})

        if response.stop_reason == "pause_turn":
            pauses += 1
            if pauses > MAX_PAUSES:
                raise AgentError("Research kept pausing without finishing.")
            continue  # resend as-is; the server resumes the paused turn
        pauses = 0

        tool_uses = _tool_uses(content)
        if not tool_uses:
            if nudged:
                raise AgentError("Claude finished without submitting an article.")
            nudged = True
            messages.append({"role": "user", "content": NUDGE})
            continue

        results = []
        for tu in tool_uses:
            if tu.name != SUBMIT_TOOL["name"]:
                results.append(_error(tu.id, f"Unknown tool {tu.name}."))
                continue
            try:
                submission = Submission.model_validate(tu.input)
            except ValidationError as e:
                last_problems = [e.json(include_url=False)]
                results.append(_error(tu.id, "The submission does not match the schema:\n" + last_problems[0]))
                continue
            say(f"  submitted '{submission.vi.title}', checking...")
            try:
                last_problems = check(submission)
            except Exception as e:  # a checker bug must not throw away a paid run
                last_problems = [f"The site checker crashed ({type(e).__name__}: {e}); "
                                 "make sure the body is plain Markdown and submit again."]
            if not last_problems:
                return Result(submission, usage, failed_submissions + 1)
            say(f"  {len(last_problems)} problem(s), sending back:")
            for p in last_problems:
                say(f"    - {p}")
            results.append(
                _error(tu.id, "The article did not pass the checks. Fix all of these and submit again:\n"
                       + "\n".join(f"- {p}" for p in last_problems))
            )

        failed_submissions += 1
        if failed_submissions >= MAX_SUBMISSIONS:
            raise AgentError(
                "The article still fails the checks after "
                f"{MAX_SUBMISSIONS} attempts:\n" + "\n".join(last_problems)
            )
        messages.append({"role": "user", "content": results})

    raise AgentError(f"Gave up after {MAX_TURNS} API calls.")


def save_run(result: Result, runs_dir: Path, topic: str) -> Path:
    """Keep every accepted submission so a paid run is never lost (e.g. if
    publishing fails); `python -m agent --from-run <file>` publishes it."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{date.today().isoformat()}-{result.submission.vi.slug}.json"
    data = {"topic": topic, "submission": result.submission.model_dump()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
