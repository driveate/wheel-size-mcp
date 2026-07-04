"""Eval runner: feed tests/test_questions.json to a real Claude model with the
MCP tools attached, record its tool calls, and grade them against expectations.

Standalone script — NOT pytest, NOT CI. Costs money (Anthropic API) and needs
a reachable Wheel Fitment API (env: API_BASE_URL / WHEELSIZE_API_KEY / API_HOST_HEADER).
Every question simulates a user-initiated request, so search-tool ToS is respected.

Usage:
    uv run --group evals python evals/run_evals.py [-n 5] [--category catalog_flow]
        [--id cat-01] [--model claude-sonnet-5] [--json report.json] [--min-pass 0.8]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.grading import grade, load_questions  # noqa: E402
from ws_mcp.server import mcp  # noqa: E402

DEFAULT_MODEL = "claude-sonnet-5"  # pinned: a moving default makes pass-rate history incomparable
MAX_TOKENS = 16000
QUESTION_TIMEOUT_S = 300


async def build_anthropic_tools() -> list[dict]:
    """Map FastMCP tool objects to Anthropic tool definitions."""
    tools = []
    for tool in await mcp.list_tools():
        schema = getattr(tool, "parameters", None) or getattr(tool, "inputSchema", None)
        assert isinstance(schema, dict) and schema.get("type") == "object", (
            f"cannot extract JSON schema from FastMCP tool {tool.name!r} — "
            "FastMCP upgrade changed the tool object shape?"
        )
        tools.append({"name": tool.name, "description": tool.description, "input_schema": schema})
    return tools


async def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run one MCP tool in-process; returns (content, is_error)."""
    try:
        result = await mcp.call_tool(name, tool_input)
        return (result.content[0].text if result.content else ""), False
    except Exception as exc:
        return str(exc), True


async def run_question(
    client: anthropic.AsyncAnthropic,
    tools: list[dict],
    system: list[dict],
    question: dict,
    model: str,
    max_turns: int,
) -> dict:
    """One agentic loop: question in, graded tool-call record out."""
    messages: list[dict] = [{"role": "user", "content": question["question"]}]
    calls: list[tuple[str, dict]] = []

    for _ in range(max_turns):
        response = await client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            calls.append((block.name, block.input))
            content, is_error = await execute_tool(block.name, block.input)
            result = {"type": "tool_result", "tool_use_id": block.id, "content": content}
            if is_error:
                result["is_error"] = True
            results.append(result)
        # all tool_results for one assistant turn go back in ONE user message
        messages.append({"role": "user", "content": results})

    return grade(question, calls)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run MCP tool-selection evals")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model id (default {DEFAULT_MODEL})")
    parser.add_argument("--category", help="Only questions from this category")
    parser.add_argument("--id", dest="question_id", help="Only this question id")
    parser.add_argument("-n", type=int, default=None, help="Limit number of questions")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-turns", type=int, default=16)
    parser.add_argument("--min-pass", type=float, default=None, help="Exit 1 if pass rate is below this (0..1)")
    parser.add_argument("--json", dest="json_out", help="Write full machine-readable report to this path")
    parser.add_argument("--verbose", action="store_true", help="Print tool calls for failing questions")
    args = parser.parse_args()

    questions = load_questions()
    if args.category:
        questions = [q for q in questions if q["category"] == args.category]
    if args.question_id:
        questions = [q for q in questions if q["id"] == args.question_id]
    if args.n:
        questions = questions[: args.n]
    if not questions:
        print("no questions matched the filters")
        return 2

    tools = await build_anthropic_tools()
    # The server's own instructions — the exact artifact real MCP clients see.
    # cache_control: tools+system prefix is shared by every question.
    system = [{"type": "text", "text": mcp.instructions, "cache_control": {"type": "ephemeral"}}]
    client = anthropic.AsyncAnthropic()

    # preflight: fail fast with a clear message instead of tracebacks mid-run
    # (count_tokens is free — no tokens are billed)
    try:
        await client.messages.count_tokens(model=args.model, messages=[{"role": "user", "content": "ping"}])
    except (TypeError, anthropic.AuthenticationError):
        print(
            "No Anthropic credentials found. Set ANTHROPIC_API_KEY "
            "(or log in with `ant auth login`) and re-run.",
            file=sys.stderr,
        )
        return 2
    except anthropic.NotFoundError:
        print(f"Unknown model id {args.model!r}.", file=sys.stderr)
        return 2

    semaphore = asyncio.Semaphore(args.concurrency)

    print(f"model={args.model}  questions={len(questions)}  tools={len(tools)}\n")

    async def bounded(q: dict) -> dict:
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    run_question(client, tools, system, q, args.model, args.max_turns),
                    timeout=QUESTION_TIMEOUT_S,
                )
            except (TimeoutError, asyncio.TimeoutError):
                r = grade(q, [])
                r["reason"] = f"timed out after {QUESTION_TIMEOUT_S}s"
                if r["scored"]:
                    r["passed"] = False
                return r

    results = []
    for coro in asyncio.as_completed([bounded(q) for q in questions]):
        r = await coro
        results.append(r)
        mark = "PASS" if r["passed"] else "FAIL" if r["scored"] else "SKIP"
        seq = " -> ".join(c["tool"] for c in r["calls"]) or "(no tool calls)"
        print(f"[{mark}] {r['id']:<10} {seq}")
        if not r["scored"] and r["tests_note"]:
            print(f"       unscored — review manually: {r['tests_note']}")
        if r["scored"] and not r["passed"]:
            print(f"       reason: {r['reason']}")
            if r["tests_note"]:
                print(f"       checks: {r['tests_note']}")
            if args.verbose:
                for c in r["calls"]:
                    print(f"       call: {c['tool']} {json.dumps(c['input'], ensure_ascii=False)}")

    # summary per category — unscored questions are excluded from all rates
    scored = [r for r in results if r["scored"]]
    skipped = len(results) - len(scored)
    print("\n=== Summary ===")
    by_category: dict[str, list[dict]] = {}
    for r in scored:
        by_category.setdefault(r["category"], []).append(r)
    for category in sorted(by_category):
        rs = by_category[category]
        passed = sum(r["passed"] for r in rs)
        print(f"{category:<22} {passed}/{len(rs)}")
    if not scored:
        print("no scored questions — nothing to rate")
        return 2
    total_passed = sum(r["passed"] for r in scored)
    rate = total_passed / len(scored)
    print(f"{'TOTAL':<22} {total_passed}/{len(scored)}  ({rate:.0%})", end="")
    print(f"  [{skipped} unscored skipped]" if skipped else "")

    if args.json_out:
        report = {
            "model": args.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_scored": len(scored),
            "passed": total_passed,
            "skipped_unscored": skipped,
            "pass_rate": rate,
            "results": sorted(results, key=lambda r: r["id"]),
        }
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=1))
        print(f"\nreport written to {args.json_out}")

    if args.min_pass is not None and rate < args.min_pass:
        print(f"\nFAIL: pass rate {rate:.0%} below --min-pass {args.min_pass:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
