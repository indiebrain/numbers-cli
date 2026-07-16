# MCP tools

`numbers-cli` includes a Model Context Protocol server so Claude Code, Cursor,
and other clients can call Numbers operations as native tools - the same
integration OfficeCli offers. It runs over stdio: `nmbr mcp`.

## Install the server, then register with Claude Code

The Homebrew formula installs the core command line only. Install the server
extra (isolated, via pipx), then register it:

```bash
pipx install 'numbers-cli[mcp] @ git+https://github.com/indiebrain/numbers-cli'
claude mcp add apple-numbers -- "$(command -v nmbr)" mcp
```

The pipx install provides an `nmbr` whose `nmbr mcp` starts the server. If you
register by hand instead, add this to the `mcpServers` object in `~/.claude.json`
(or your client's config), using the absolute path from `command -v nmbr`:

```json
"apple-numbers": {
  "command": "/absolute/path/to/nmbr",
  "args": ["mcp"]
}
```

Restart the client and confirm the `numbers_*` tools load.

## Tools

Each tool returns the shared envelope as a structured result: `{"ok": true,
"data": ...}` or `{"ok": false, "error": {"code", "message", "hint"}}`.

| Tool | Arguments | Notes |
|---|---|---|
| `numbers_doctor` | - | Versions and application-engine availability |
| `numbers_create` | `file`, `sheets?`, `rows?`, `cols?` | Blank document |
| `numbers_view` | `file`, `path?`, `fmt?` | Text views: text, csv, md, outline, json |
| `numbers_get` | `file`, `path` | Read a cell, range, row, column, or table |
| `numbers_set` | `file`, `path`, `value`, `as_text?` | Formulas route to the application |
| `numbers_add` | `file`, `kind`, `path?`, `name?`, `count?` | Sheet, table, row, column |
| `numbers_remove` | `file`, `path`, `kind?`, `count?` | Rows and columns only |
| `numbers_query` | `file`, `contains`, `path?`, `ignore_case?` | Find cells by text |
| `numbers_batch` | `file`, `ops`, `as_text?` | Operation list in one pass |
| `numbers_merge` | `template`, `data`, `out` | Fill `{{placeholders}}` |
| `numbers_dump` | `file` | Replayable operation list |
| `numbers_raw` | `file`, `id?`, `contains?` | Inspect protocol buffer objects |
| `numbers_recalc` | `file` | Application engine |
| `numbers_export` | `file`, `to`, `out` | Application engine |

The image and page renderings (`view --as pdf|png`) are available on the command
line; the MCP `numbers_view` tool covers the text views.
