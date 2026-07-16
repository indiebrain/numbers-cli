# Architecture

The implementation lives in the tool's own repository,
<https://github.com/indiebrain/numbers-cli>; the module paths below refer to it.
This note describes how the tool works so you can reason about its behaviour
while driving it.

## Two engines behind one command line

`numbers-cli` has two back ends and a router that picks between them per
operation.

### Parser engine (`engine/parser_engine.py`)

Wraps [`numbers-parser`](https://github.com/masaccio/numbers-parser) to read and
write `.numbers` files directly. This is the default for everything structural:
open, read cells, write literal values, add rows, columns, sheets, and tables,
delete rows and columns, and save. It launches no application, so it is fast and
runs anywhere the library installs.

What it cannot do: evaluate a formula, render a page, or export to another
format. Two hard limits also live here - it cannot write a live formula (a
`=A1+A2` write is stored as text), and it cannot delete a sheet or table (save
writes from an internal model, not the object list the wrapper exposes).

### Application engine (`engine/app_engine.py`, `jxa/numbers_ops.js`)

Drives the Numbers application through `osascript -l JavaScript`. Used only for
what the parser cannot do: entering real formulas so Numbers evaluates them,
forcing a recalculation, and native export. It is macOS only, needs Numbers
installed, and needs Automation permission (macOS prompts on first use).
`available()` checks all three before any call, so operations that need it fail
with a clear `ENGINE_UNAVAILABLE` error instead of a stack trace.

## The router (`router.py`)

A `Session` opens one document, collects edits, and commits them with the right
engine:

1. Literal values are written in memory through the parser and saved once.
2. Formula cells are, after that save, handed to the application engine, which
   enters them in Numbers where they evaluate; the computed values are read back.

This is the "write then recalculate then reread" round trip. When a formula edit
is requested but Numbers is unavailable, the session raises `ENGINE_UNAVAILABLE`
unless the caller passed `allow_text_formula`, in which case it stores the literal
string and attaches a warning.

## The layers

* **L1 view** (`layers/l1_view.py`, `render.py`) - read only renderings: text,
  csv, markdown, outline, json (all from the parser), plus html (built locally
  from the parsed tables, no application needed) and pdf and png (from the
  application).
* **L2 dom** (`layers/l2_dom.py`) - the structured editing surface: `get`, `set`,
  `add`, `remove`, `query`, all over the path grammar.
* **L3 raw** (`layers/l3_raw.py`) - read access to the underlying IWA protocol
  buffer objects, for inspection the higher layers cannot express.

## The address grammar (`paths.py`)

One parser and resolver, reused by every layer, turns a path such as
`/sheet['Budget']/table[1]/cell[B2]` into a resolved `Target` (the sheet and
table objects plus zero based leaf coordinates). Index versus name resolution
hinges on quoting, captured at parse time.

## Response envelope (`errors.py`)

Every command and MCP tool returns the same shape - `{"ok", "data"}` or
`{"ok", "error": {"code", "message", "hint"}}` - so a caller can branch on a
stable machine code and act on a human hint.
