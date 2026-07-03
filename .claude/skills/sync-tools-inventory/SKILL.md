---
name: sync-tools-inventory
description: "Sync tool descriptions from docs/tools-inventory.md to Python source files in src/ws_mcp/tools/. Use after editing the inventory doc to push changes to code."
disable-model-invocation: true
user-invocable: true
allowed-tools: Read, Edit, Grep, Glob, Bash(git diff *), Bash(uv run ruff check *), Bash(uv run pytest *)
effort: high
---

# Sync Tools Inventory → Code

Synchronize tool docstrings and parameter descriptions from `docs/tools-inventory.md` (the single source of truth) into the Python tool source files.

## Step 0: Drift Safety Check — ALWAYS RUN FIRST

```bash
uv run pytest tests/test_inventory_sync.py -q
```

This test compares both sides (docstrings + parameter descriptions, whitespace-normalized).

- **All green** → doc and code are already in sync. Nothing to do; report that and stop.
- **Failures** → read each reported diff and classify it:
  - The doc side contains the edits the user just made → this is the change set to push to code. Proceed.
  - The CODE side contains content absent from the doc, in sections the user did NOT just edit → **code is newer than the doc (reverse drift). STOP.** Do not overwrite it. Report the diff and ask the user to back-port code → doc first (or confirm the overwrite explicitly).

Never skip this step: a doc→code sync over a stale doc silently destroys newer docstrings, and `ruff` will not catch it.

## Step 1: Read Both Sides

Read `docs/tools-inventory.md` and all four tool source files:

| Inventory Section | Source File |
|---|---|
| `## Catalog` | `src/ws_mcp/tools/catalog.py` |
| `## Search` | `src/ws_mcp/tools/search.py` |
| `## Classified` | `src/ws_mcp/tools/classified.py` |
| `## Utility` | `src/ws_mcp/tools/utility.py` |

## Step 2: Parse Inventory Format

Each tool in inventory.md follows this structure:

```markdown
### `tool_name`

**API**: `GET /v2/endpoint/`

**Docstring**:
> Line 1 of docstring
> Line 2 of docstring
> ...

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `param_name` | `type` | Description text |
```

Format details:

- **Heading suffixes**: a heading may carry a note after the closing backtick — e.g. `` ### `check_rim_fitment_for_vehicle` (composite) ``. The tool name is only what is inside the backticks.
- **No parameters**: `list_regions` has `**Parameters**: none` instead of a table.
- **Escaped pipes**: cells may contain `\|` (e.g. type `` `"concise" \| "full"` ``) — treat `\|` as a literal `|` inside the cell, not a column separator.
- **Shared geometric block**: the `## Classified` section opens with a shared parameter table (marked "shared geometric parameters"). Tool tables reference it with the row `| *+ shared geometric parameters* | | see block above |` instead of repeating those rows. When comparing a tool's parameters, expand the shared block into its table.
- **API lines** may have suffixes too (`+ MCP-side year filtering`) — informational only, not synced.

Extract for each tool:
- **Tool name**: from the backticks in the `### ` heading
- **Docstring lines**: all `> ` prefixed lines under **Docstring** (strip the `> ` prefix; a bare `>` is a blank line; indentation after `> ` is preserved)
- **Parameter names and descriptions**: from the "Parameter" and "Description" columns (strip backticks from names)

## Step 3: Compare and Update Docstrings

For each tool, find the function in the source file by matching `async def tool_name(`.

**Docstring update rule**: Replace the entire `"""..."""` block under the function signature with the content from inventory. Preserve the indentation level (8 spaces for tool functions).

Format:
```python
    async def tool_name(...) -> dict:
        """First line of docstring.

        Remaining lines of docstring.
        Preserving blank lines from the inventory.
        """
```

- The first `> ` line becomes the first line of the docstring (on same line as `"""`)
- Subsequent `> ` lines follow with 8-space indentation
- Empty `> ` lines (just `>`) become blank lines in the docstring
- Close with `"""` on its own line at 8-space indent

## Step 4: Compare and Update Parameter Descriptions

For each parameter in the inventory table, find the matching `Field(description="...")` and update the description string. The Description column maps to the code **verbatim** — do not add or drop range/default annotations.

**Where the Field lives depends on the module:**

- `catalog.py`, `search.py`, `utility.py`: inline in the function signature — `param: Annotated[type, Field(description="...")]`.
- `classified.py`: mostly in **module-level Annotated aliases** at the top of the file (`_BoltPattern`, `_RimDiameter`, `_Cb`, `_Sort`, …) shared by several tools. The doc's shared geometric block maps to these aliases. Editing an alias changes every tool that uses it — that is intended. If the doc asks for different descriptions of the same shared parameter in different tools, report a WARNING instead of editing (per-tool divergence requires restructuring the aliases first).

**Update rule**: Replace only the `description="old text"` value inside `Field(...)`. Do NOT change the type annotation, default value, or other Field arguments (ge, le, etc.). Unescape `\|` → `|` when writing into Python strings.

## Step 5: Detect Structural Changes

Compare the set of parameter names in inventory (with the shared block expanded) vs code for each tool.

- **New parameter in inventory but not in code**: Report as WARNING — cannot auto-add because type annotation, default value, and Field constraints are needed. List the parameter name and suggest the user add it manually.
- **Parameter in code but removed from inventory**: Report as WARNING — do not auto-remove. List the parameter and ask the user to confirm deletion.

## Step 6: Validate

After all edits:

1. `uv run ruff check src/ws_mcp/tools/` — no syntax/lint errors
2. `uv run pytest tests/test_inventory_sync.py -q` — MUST be green now: doc and code are byte-consistent again
3. Show a summary of all changes made:
   - Which tools had docstring updates
   - Which parameters had description updates
   - Any structural warnings (added/removed params)

## Step 7: Cross-File Consistency Check

Tool behavior and parameter contracts are also duplicated in two places this skill does NOT edit:

- `src/ws_mcp/server.py` — the FastMCP `instructions` block (workflows, critical rules, parameter requirements)
- `README.md` — the "Available Tools" table

After a sync, grep both for statements about the tools whose descriptions changed. If a synced change contradicts them (e.g. a parameter requirement changed), report the exact lines as WARNINGS for the user to update manually. Do not auto-edit these files.

## Important Rules

- NEVER proceed past Step 0 when code-side content is newer than the doc
- NEVER change function signatures, return types, or logic — only docstrings and Field descriptions
- NEVER change Field constraints (ge, le, etc.) — only the description string
- NEVER change type annotations — only descriptions
- Preserve existing indentation style in each file
- If a tool exists in code but NOT in inventory — skip it, report as info
- If a tool exists in inventory but NOT in code — report as WARNING
- Use the Edit tool for all changes (not Write) to preserve file content
