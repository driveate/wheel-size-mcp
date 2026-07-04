"""Unit tests for the eval grader (evals/grading.py). No API calls, no billing."""

from evals.grading import QUESTIONS_PATH, check_params, check_tools, grade, load_questions

# --- check_tools: multiset containment ---


def test_tools_exact_match():
    ok, reason = check_tools(["ws_list_makes"], ["ws_list_makes"])
    assert ok and not reason


def test_tools_extra_calls_allowed():
    ok, _ = check_tools(["ws_search_by_vehicle"], ["ws_list_makes", "ws_list_models", "ws_search_by_vehicle"])
    assert ok


def test_tools_duplicate_expected_requires_duplicate_actual():
    expected = ["ws_search_by_vehicle", "ws_search_by_vehicle"]
    ok, reason = check_tools(expected, ["ws_search_by_vehicle"])
    assert not ok
    assert "ws_search_by_vehicle x1" in reason

    ok, _ = check_tools(expected, ["ws_search_by_vehicle", "ws_search_by_vehicle"])
    assert ok


def test_tools_missing_reported():
    ok, reason = check_tools(["ws_list_makes", "ws_list_years"], ["ws_list_makes"])
    assert not ok
    assert "ws_list_years" in reason


# --- check_params ---


def _q(**kwargs):
    return {"id": "t-01", "category": "test", "question": "?", **kwargs}


def test_params_vacuous_pass_without_expectations():
    ok, reason = check_params(_q(expected_tools=["ws_list_makes"]), [])
    assert ok and not reason


def test_params_superset_on_any_expected_tool():
    q = _q(expected_tools=["ws_list_makes", "ws_list_years"], expected_params={"make": "bmw", "model": "3-series"})
    calls = [
        ("ws_list_makes", {}),
        ("ws_list_years", {"make": "bmw", "model": "3-series", "region": ["eudm"]}),
    ]
    ok, _ = check_params(q, calls)
    assert ok


def test_params_fail_when_split_across_calls():
    q = _q(expected_tools=["ws_list_makes", "ws_list_years"], expected_params={"make": "bmw", "model": "3-series"})
    calls = [("ws_list_makes", {"make": "bmw"}), ("ws_list_years", {"model": "3-series"})]
    ok, reason = check_params(q, calls)
    assert not ok and "expected tools" in reason


def test_params_loose_numeric_compare():
    q = _q(expected_tools=["ws_list_models"], expected_params={"year": 2024})
    ok, _ = check_params(q, [("ws_list_models", {"make": "toyota", "year": 2024.0})])
    assert ok


def test_params_bool_not_equal_to_int():
    q = _q(expected_tools=["ws_list_models"], expected_params={"flag": 1})
    ok, _ = check_params(q, [("ws_list_models", {"flag": True})])
    assert not ok


def test_params_list_order_insensitive():
    q = _q(expected_tools=["ws_list_makes"], expected_params={"region": ["usdm", "jdm"]})
    ok, _ = check_params(q, [("ws_list_makes", {"region": ["jdm", "usdm"]})])
    assert ok


def test_params_list_length_must_match():
    q = _q(expected_tools=["ws_list_makes"], expected_params={"region": ["usdm"]})
    ok, _ = check_params(q, [("ws_list_makes", {"region": ["usdm", "jdm"]})])
    assert not ok


def test_params_search_only_matches_terminal_tool():
    q = _q(
        expected_tools=["ws_list_makes", "ws_search_by_vehicle"],
        expected_params_search={"make": "toyota"},
    )
    # matching params on a NON-terminal tool must not satisfy expected_params_search
    ok, reason = check_params(q, [("ws_list_makes", {"make": "toyota"})])
    assert not ok and "ws_search_by_vehicle" in reason

    ok, _ = check_params(q, [("ws_search_by_vehicle", {"make": "toyota", "model": "camry"})])
    assert ok


# --- grade: combined verdict ---


def test_grade_combines_tools_and_params():
    q = _q(expected_tools=["ws_list_models"], expected_params={"make": "toyota"}, tests="note")
    result = grade(q, [("ws_list_models", {"make": "toyota", "year": 2024})])
    assert result["scored"]
    assert result["passed"] and result["tools_pass"] and result["params_pass"]
    assert result["calls"] == [{"tool": "ws_list_models", "input": {"make": "toyota", "year": 2024}}]

    result = grade(q, [("ws_list_makes", {})])
    assert result["passed"] is False
    assert "ws_list_models" in result["reason"]


def test_grade_unscored_without_expectations():
    q = _q(tests="behavior described in prose only")
    result = grade(q, [("ws_search_by_rim", {"bolt_pattern": "5x114.3"})])
    assert result["scored"] is False
    assert result["passed"] is None


# --- loader against the real fixture ---


def test_load_questions_fixture():
    questions = load_questions(QUESTIONS_PATH)
    assert len(questions) >= 80
    # a few edge-case questions intentionally have no expected_tools
    # (typo/error-recovery behavior) — they grade as vacuous PASS
    assert all("id" in q and "question" in q and "category" in q for q in questions)
    # every expected tool name must carry the ws_ prefix (guards against fixture drift)
    for q in questions:
        for tool in q.get("expected_tools", []):
            assert tool.startswith("ws_"), f"{q['id']}: unprefixed tool {tool}"
