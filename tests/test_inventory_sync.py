"""Guard against drift between docs/tools-inventory.md and the tool source files.

docs/tools-inventory.md is the single source of truth for tool docstrings and
parameter descriptions (see .claude/skills/sync-tools-inventory). This test
fails when either side is edited without the other, before the drift can be
silently overwritten by a later sync.

No API required — pure static comparison.
"""

import ast
import pathlib
import re

TOOLS_DIR = pathlib.Path(__file__).parent.parent / "src" / "ws_mcp" / "tools"
DOC = pathlib.Path(__file__).parent.parent / "docs" / "tools-inventory.md"

SHARED_ROW_MARKER = "shared geometric parameters"
# The shared geometric block in the doc mirrors the module-level Annotated
# aliases in classified.py; ws_find_tires_for_rim carries the full set in code.
SHARED_SOURCE_TOOL = "ws_find_tires_for_rim"


def _field_description(node) -> str | None:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and getattr(sub.func, "id", "") == "Field":
            for kw in sub.keywords:
                if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                    return kw.value.value
    return None


def _code_side() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Docstrings and param descriptions per tool, resolving Annotated aliases."""
    docstrings, params = {}, {}
    for f in TOOLS_DIR.glob("*.py"):
        tree = ast.parse(f.read_text())
        aliases = {
            node.targets[0].id: desc
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and (desc := _field_description(node.value))
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef) or node.name.startswith("_"):
                continue
            ds = ast.get_docstring(node)
            if not ds:
                continue
            docstrings[node.name] = ds
            params[node.name] = {}
            for a in node.args.args + node.args.kwonlyargs:
                if a.annotation is None:
                    continue
                if isinstance(a.annotation, ast.Name) and a.annotation.id in aliases:
                    params[node.name][a.arg] = aliases[a.annotation.id]
                elif desc := _field_description(a.annotation):
                    params[node.name][a.arg] = desc
    return docstrings, params


def _parse_table(text: str) -> tuple[dict[str, str], bool]:
    """Param -> description from a markdown table; also whether it references the shared block."""
    rows, has_shared_ref = {}, False
    for line in text.splitlines():
        if not line.startswith("|") or re.match(r"\|[-\s|]+\|$", line):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) != 3 or cells[0] in ("Parameter", ""):
            continue
        if SHARED_ROW_MARKER in cells[0]:
            has_shared_ref = True
            continue
        rows[cells[0].strip("`")] = cells[2].replace("\\|", "|")
    return rows, has_shared_ref


def _doc_side() -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    doc = DOC.read_text()
    shared_m = re.search(
        r'marked with the row "\+ shared geometric parameters":\n\n((?:\|[^\n]*\n)+)', doc
    )
    assert shared_m, "shared geometric parameters block not found in inventory doc"
    shared, _ = _parse_table(shared_m.group(1))

    docstrings, params = {}, {}
    for m in re.finditer(r"### `(\w+)`[^\n]*\n(.*?)(?=\n### |\n## |\Z)", doc, re.S):
        name, body = m.group(1), m.group(2)
        dm = re.search(r"\*\*Docstring\*\*:\n((?:>[^\n]*\n)+)", body)
        assert dm, f"no Docstring block for {name} in inventory doc"
        docstrings[name] = "\n".join(
            re.sub(r"^> ?", "", line) for line in dm.group(1).splitlines()
        )
        tm = re.search(r"\*\*Parameters\*\*:\n((?:\|[^\n]*\n)+)", body)
        rows, has_shared_ref = _parse_table(tm.group(1)) if tm else ({}, False)
        if has_shared_ref:
            rows = {**rows, **shared}
        params[name] = rows
    return docstrings, params, shared


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


CODE_DOCSTRINGS, CODE_PARAMS = _code_side()
DOC_DOCSTRINGS, DOC_PARAMS, DOC_SHARED = _doc_side()


def test_same_tool_sets():
    assert set(CODE_DOCSTRINGS) == set(DOC_DOCSTRINGS)


def test_docstrings_match():
    drifted = [
        name
        for name in CODE_DOCSTRINGS
        if name in DOC_DOCSTRINGS and _norm(CODE_DOCSTRINGS[name]) != _norm(DOC_DOCSTRINGS[name])
    ]
    assert not drifted, (
        f"docstrings differ between code and docs/tools-inventory.md: {drifted}. "
        "Update the inventory doc (or run the sync-tools-inventory skill if the doc is newer)."
    )


def test_param_descriptions_match():
    problems = []
    for tool, cparams in CODE_PARAMS.items():
        dparams = DOC_PARAMS.get(tool, {})
        for pname, cdesc in cparams.items():
            ddesc = dparams.get(pname)
            if ddesc is None:
                problems.append(f"{tool}.{pname}: missing from inventory doc table")
            elif _norm(cdesc) != _norm(ddesc):
                problems.append(f"{tool}.{pname}:\n  code: {cdesc}\n  doc:  {ddesc}")
    assert not problems, "param descriptions drifted:\n" + "\n".join(problems)


def test_no_stale_doc_params():
    stale = [
        f"{tool}.{pname}"
        for tool, dparams in DOC_PARAMS.items()
        if tool in CODE_PARAMS
        for pname in dparams
        if pname not in CODE_PARAMS[tool]
    ]
    assert not stale, f"inventory doc lists params that do not exist in code: {stale}"


def test_shared_block_matches_aliases():
    code_shared = CODE_PARAMS[SHARED_SOURCE_TOOL]
    for pname, ddesc in DOC_SHARED.items():
        assert pname in code_shared, f"shared block param {pname} not found in {SHARED_SOURCE_TOOL}"
        assert _norm(code_shared[pname]) == _norm(ddesc), (
            f"shared block description for {pname} differs from classified.py alias:\n"
            f"  code: {code_shared[pname]}\n  doc:  {ddesc}"
        )
