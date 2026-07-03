---
name: sync-tools-inventory
description: "Sync tool descriptions from docs/tools-inventory.md to Python source files in src/ws_mcp/tools/. Use after editing the inventory doc to push changes to code."
disable-model-invocation: true
user-invocable: true
allowed-tools: Read, Edit, Grep, Glob, Bash(git diff *), Bash(ruff check *)
effort: high
---

# Sync Tools Inventory → Code

Synchronize tool descriptions, docstrings, and parameter definitions from `docs/tools-inventory.md` (the single source of truth) into the Python tool source files.

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

Extract for each tool:
- **Tool name**: from `### \`tool_name\`` heading
- **Docstring lines**: all `> ` prefixed lines under **Docstring** (strip the `> ` prefix)
- **Parameter descriptions**: from the "Description" column of the parameters table
- **Parameter names**: from the "Parameter" column (strip backticks)

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

For each parameter in the inventory table, find the matching `Field(description="...")` in the source file and update the description string.

**Match by parameter name**: the `param_name` column maps to the Python parameter name.

**Update rule**: Replace only the `description="old text"` value inside `Field(...)`. Do NOT change the type annotation, default value, or other Field arguments (ge, le, etc.).

Example:
```python
# Before
rim_diameter: Annotated[float, Field(ge=8, le=26, description="Old description")] = None,
# After
rim_diameter: Annotated[float, Field(ge=8, le=26, description="New description from inventory")] = None,
```

## Step 5: Detect Structural Changes

Compare the set of parameter names in inventory vs code for each tool.

- **New parameter in inventory but not in code**: Report as WARNING — cannot auto-add because type annotation, default value, and Field constraints are needed. List the parameter name and suggest the user add it manually.
- **Parameter in code but removed from inventory**: Report as WARNING — do not auto-remove. List the parameter and ask the user to confirm deletion.

## Step 6: Validate

After all edits:
1. Run `ruff check src/ws_mcp/tools/` to verify no syntax/lint errors
2. Show a summary of all changes made:
   - Which tools had docstring updates
   - Which parameters had description updates
   - Any structural warnings (added/removed params)

## Important Rules

- NEVER change function signatures, return types, or logic — only docstrings and Field descriptions
- NEVER change Field constraints (ge, le, etc.) — only the description string
- NEVER change type annotations — only descriptions
- Preserve existing indentation style in each file
- If a tool exists in code but NOT in inventory — skip it, report as info
- If a tool exists in inventory but NOT in code — report as WARNING
- Use the Edit tool for all changes (not Write) to preserve file content
