"""Deterministic grading for MCP tool-selection evals.

Pure functions — no API calls, unit-tested in tests/test_eval_grading.py.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

QUESTIONS_PATH = Path(__file__).parent.parent / "tests" / "test_questions.json"


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    """Flatten the category-grouped fixture into a list of questions.

    Each question gets a `category` key; `_`-prefixed metadata is skipped.
    """
    data = json.loads(Path(path).read_text())
    questions = []
    for category, block in data.items():
        if category.startswith("_"):
            continue
        for q in block.get("questions", []):
            questions.append({**q, "category": category})
    return questions


def check_tools(expected: list[str], actual: list[str]) -> tuple[bool, str]:
    """Multiset containment: every expected tool call happened (repeats counted).

    Extra calls are allowed — catalog navigation legitimately adds steps.
    """
    missing = Counter(expected) - Counter(actual)
    if not missing:
        return True, ""
    detail = ", ".join(f"{t} x{n}" for t, n in sorted(missing.items()))
    return False, f"missing tool calls: {detail}"


def _values_match(expected, actual) -> bool:
    """Loose value compare: lists order-insensitive, 2024 == 2024.0, else equality."""
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        remaining = list(actual)
        for ev in expected:
            for i, av in enumerate(remaining):
                if _values_match(ev, av):
                    remaining.pop(i)
                    break
            else:
                return False
        return True
    # bool is an int subclass in Python: 1 == True — but flag=1 and flag=True
    # are different API params, so reject cross-type matches explicitly
    if isinstance(expected, bool) != isinstance(actual, bool):
        return False
    if (
        isinstance(expected, (int, float))
        and isinstance(actual, (int, float))
        and not isinstance(expected, bool)
        and not isinstance(actual, bool)
    ):
        return float(expected) == float(actual)
    return expected == actual


def _call_satisfies(expected_params: dict, call_input: dict) -> bool:
    """The call's input carries a superset of the expected params."""
    return all(k in call_input and _values_match(v, call_input[k]) for k, v in expected_params.items())


def check_params(question: dict, calls: list[tuple[str, dict]]) -> tuple[bool, str]:
    """Grade expected_params / expected_params_search against recorded calls.

    - expected_params: satisfied by ANY single call to any of expected_tools.
    - expected_params_search: satisfied only by a call to the LAST expected
      tool (the terminal search/classified call the field encodes).
    Vacuously true when the question has no param expectations.
    """
    expected_tools = question.get("expected_tools", [])
    problems = []

    expected = question.get("expected_params")
    if expected:
        candidates = [inp for name, inp in calls if name in expected_tools]
        if not any(_call_satisfies(expected, c) for c in candidates):
            problems.append(f"no call to expected tools carried {expected}")

    expected_search = question.get("expected_params_search")
    if expected_search and expected_tools:
        terminal = expected_tools[-1]
        candidates = [inp for name, inp in calls if name == terminal]
        if not any(_call_satisfies(expected_search, c) for c in candidates):
            problems.append(f"no {terminal} call carried {expected_search}")

    return (not problems, "; ".join(problems))


def grade(question: dict, calls: list[tuple[str, dict]]) -> dict:
    """Grade one question against the recorded (tool_name, input) calls.

    Questions with no machine-checkable expectations (a few edge cases only
    describe behavior in the free-text `tests` note) come back with
    scored=False — the runner reports them as SKIP and excludes them from
    the pass rate, so they can't mask regressions as vacuous passes.
    """
    scored = bool(
        question.get("expected_tools")
        or question.get("expected_params")
        or question.get("expected_params_search")
    )
    tools_pass, tools_reason = check_tools(question.get("expected_tools", []), [n for n, _ in calls])
    params_pass, params_reason = check_params(question, calls)
    return {
        "id": question["id"],
        "category": question["category"],
        "question": question["question"],
        "scored": scored,
        "passed": (tools_pass and params_pass) if scored else None,
        "tools_pass": tools_pass,
        "params_pass": params_pass,
        "reason": "; ".join(r for r in (tools_reason, params_reason) if r),
        "tests_note": question.get("tests", ""),
        "calls": [{"tool": n, "input": i} for n, i in calls],
    }
