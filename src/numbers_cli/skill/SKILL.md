---
name: apple-numbers
description: >-
  Create, read, view, and edit Apple Numbers (.numbers) spreadsheets from the
  command line or as MCP tools. Use when the user wants to work with a .numbers
  file: build one, read cells or tables, set values or formulas, add or remove
  rows, columns, sheets, or tables, find where a value lives, fill a template,
  export to csv, xlsx, or pdf, or render a table to see it. Modeled on OfficeCli
  but for Apple Numbers, so trigger on phrases like "edit this Numbers file",
  "read the Numbers spreadsheet", "put these values into a .numbers", or "make a
  Numbers report".
---

# Apple Numbers command line and MCP server

`numbers-cli` gives an agent OfficeCli-style control over Apple Numbers
`.numbers` files. It reads and writes the file directly through the
`numbers-parser` library, and delegates the things only Numbers can do -
evaluating formulas, rendering pages, native export - to the Numbers application
through `osascript`.

This skill ships with the tool (`nmbr`) itself, from
<https://github.com/indiebrain/numbers-cli>, and is placed here by
`nmbr skill install`. The command is `nmbr`. Every command prints one JSON
object: `{"ok": true, "data": ...}` on success, or `{"ok": false, "error":
{"code", "message", "hint"}}` on failure. Pass `--human` for readable output
while exploring.

## Prerequisites (check before starting)

**First, make sure `nmbr` is on the path** — this is the step to run before any
command below:

```bash
command -v nmbr >/dev/null || { brew tap indiebrain/numbers && brew install numbers-cli; }
```

- Installing puts `nmbr` on the path so any shell or session can call it by name.
  The snappy dependency is bundled (via `cramjam`), so no separate library
  install is required.
- **The Homebrew formula installs the core command line only.** The Model Context
  Protocol server is an optional extra with a large dependency tree; enable it
  with `pipx install 'numbers-cli[mcp] @ git+https://github.com/indiebrain/numbers-cli'`,
  then run `nmbr mcp`.
- **For formulas, rendering, and export only**: the **Numbers application**
  installed, plus Automation permission (macOS prompts on first use). Without it,
  the reading and editing commands still work; only `recalc`, `export`, and
  `view --as pdf|png` need it. Run `nmbr doctor` to see whether the application
  engine is available.

## Path grammar

Every command addresses parts of a document with a path, resolved left to right:

```
/sheet[1]/table[1]/cell[B2]           first sheet, first table, cell B2
/sheet['Budget']/table['Q1']/range[A1:C3]   by name, a rectangular range
/sheet[2]/table[1]/row[3]             a whole row (one based)
/sheet[1]/table[1]/col[B]             a whole column (letter or one based index)
```

A bare integer is a one based index; a quoted value is a name. `sheet[1]` is the
first sheet, while `sheet['1']` is the sheet literally named `1`.

## Commands

| Command | What it does | Engine |
|---|---|---|
| `nmbr create <file> [--sheets A B ...]` | Make a blank document | parser |
| `nmbr view <file> [path] --as text\|csv\|md\|outline\|json\|html\|pdf\|png` | Render for reading (L1) | parser; pdf/png use the app |
| `nmbr get <file> <path>` | Read a cell, range, row, column, or table (L2) | parser |
| `nmbr set <file> <path> <value>` | Write a value; a leading `=` is a formula | parser; formulas use the app |
| `nmbr add <file> [path] --kind sheet\|table\|row\|col [--name N] [--count K]` | Add structure (L2) | parser |
| `nmbr remove <file> <path> [--kind ...]` | Remove a row or column (L2) | parser |
| `nmbr query <file> <text> [--path ...]` | Find cells containing text, get their paths (L2) | parser |
| `nmbr batch <file> <ops.json>` | Apply many operations in one pass | parser (+app) |
| `nmbr merge <template> <data.json> -o <out>` | Fill `{{placeholders}}` | parser |
| `nmbr dump <file>` | Serialise to a replayable operation list | parser |
| `nmbr raw <file> [--id N] [--grep TYPE]` | Inspect the protocol buffer objects (L3, read) | parser |
| `nmbr recalc <file>` | Recalculate formulas and save | application |
| `nmbr export <file> --to csv\|xlsx\|pdf [--out ...]` | Native export | application |
| `nmbr doctor [--probe]` | Report versions and engine availability; `--probe` drives Numbers end to end | - |
| `nmbr mcp` | Run the MCP server over stdio | - |

Full detail: `references/command-reference.md`.

## Workflow

1. **Confirm the tool is ready.** Run `command -v nmbr >/dev/null || { brew tap
   indiebrain/numbers && brew install numbers-cli; }`, then `nmbr doctor`. Note
   whether `app_engine_available` is true; if it is false, avoid `recalc`,
   `export`, and formula writes, or expect a clear `ENGINE_UNAVAILABLE` error.
   `numbers_app_info` shows which app resolved (name, version, bundle id) - Apple
   ships Numbers under more than one display name. `app_engine_available` only
   means the app *resolves*, not that automation works; to confirm the round trip
   for real (it launches Numbers), run `nmbr doctor --probe` and check
   `app_engine_healthy`.
2. **Orient before editing.** Use `nmbr view <file> --as outline` to see sheets
   and tables, then `nmbr view <file> <table-path> --as csv` or `nmbr query` to
   find the cells you care about.
3. **Edit.** Use `set` for single cells, or write an operation list and run
   `batch` for several changes at once (one open and save pass).
4. **Verify.** Read the changed cells back with `get`, or render the table with
   `view --as csv` (or `--as html` for a visual check that needs no application).
5. **Formulas and export.** When the Numbers application is available, `set` a
   `=formula`, then `recalc`, then `get` the computed value; use `export` for
   csv, xlsx, or pdf.

## Load-bearing facts (read before trusting a result)

- **`numbers-parser` cannot write a live formula.** Writing `=A1+A2` through the
  parser stores the text, not a formula. `nmbr set` therefore routes any value
  starting with `=` to the Numbers application. If the application is
  unavailable, `set` fails with `ENGINE_UNAVAILABLE` rather than silently storing
  wrong text. `--as-text` forces the literal string when that is genuinely what
  you want.
- **Sheets and tables cannot be deleted** by `numbers-parser` (its save writes
  from an internal model, so removing them from the object list does nothing).
  `remove --kind sheet|table` refuses with a clear message. To drop a sheet or
  table, rebuild with `dump` then `batch` into a fresh file, or delete it in the
  Numbers application. Rows and columns delete normally.
- **The application engine is macOS only** and needs Numbers plus Automation
  permission; the parser engine works anywhere.
- **Password-protected files** cannot be opened; re-save without a password in
  Numbers first.
- **The raw layer is read only.** Patching undocumented protocol buffers is not
  offered because it can corrupt files and cannot be verified safely.

## References

- `references/architecture.md` - the two engines, the router, and the layers.
- `references/command-reference.md` - every command and flag with examples.
- `references/mcp-tools.md` - the MCP tool catalog and how to enable the server.
- `references/format-notes.md` - the `.numbers` format and the honest limits.
- `references/tool-install-guide.md` - installing the tool, the MCP extra, and Numbers.
