# numbers-cli

An OfficeCli-style command line and Model Context Protocol server for Apple
Numbers spreadsheets. It lets you (or an AI agent) create, read, view, and edit
`.numbers` files, delegating the things only Numbers can do - evaluating
formulas, rendering, native export - to the Numbers application.

## Why this exists

[OfficeCli](https://github.com/iOfficeAI/OfficeCli) gives one-line control over
Word, Excel, and PowerPoint. Those are documented zip-and-xml formats. Apple
Numbers is not: a `.numbers` file is a bundle of Snappy-compressed protocol
buffer streams (the "IWA" format) with no public specification. This tool takes
the same layered approach as OfficeCli, built on the two engines that exist for
Numbers.

## Two engines

- **Parser engine** - [`numbers-parser`](https://github.com/masaccio/numbers-parser)
  reads and writes `.numbers` directly. Fast, no application, cross platform. It
  cannot evaluate formulas and has some format limits.
- **Application engine** - the Numbers application driven through `osascript`.
  It evaluates formulas, renders pages, and exports. macOS only, needs Numbers
  installed and Automation permission.

The router chooses per operation and, for formula edits, runs the write in the
parser then hands the formula cells to Numbers so they evaluate.

## Install

### Homebrew (recommended, macOS)

```bash
brew tap indiebrain/numbers
brew install numbers-cli
```

The command `nmbr` is then on your path. The formula installs the core command
line; the Model Context Protocol server is an optional extra (see below).

### pip / pipx (from source)

```bash
pipx install 'git+https://github.com/indiebrain/numbers-cli'          # core command line
pipx install 'numbers-cli[mcp] @ git+https://github.com/indiebrain/numbers-cli'  # also enable the MCP server
```

## The MCP server is optional

The Model Context Protocol server pulls in a large dependency tree (pydantic,
starlette, uvicorn, and friends), so it is an optional extra rather than a core
dependency. Install it only if you want `nmbr mcp`:

```bash
pip install 'numbers-cli[mcp]'
```

Without it, every other command works; `nmbr mcp` prints a clear message telling
you to install the extra.

## Quick start

```bash
nmbr create budget.numbers --sheets Budget
nmbr set budget.numbers "/sheet['Budget']/table[1]/cell[A1]" "Rent"
nmbr set budget.numbers "/sheet['Budget']/table[1]/cell[B1]" 1200
nmbr --human view budget.numbers "/sheet[1]/table[1]" --as csv
nmbr --human query budget.numbers "Rent"
```

Every command prints one JSON object (`{"ok": true, "data": ...}` or a structured
error); pass `--human` for readable output.

## Layers

- **L1 view** - `view` renders a document, sheet, or table as text, csv,
  markdown, outline, json, html, pdf, or png.
- **L2 dom** - `get`, `set`, `add`, `remove`, `query` over a stable path address
  space such as `/sheet[1]/table[1]/cell[B2]`.
- **L3 raw** - `raw` inspects the underlying protocol buffer objects (read only).

Plus `batch` (an operation list applied in one pass), `merge` (fill
`{{placeholders}}` from data), and `dump` (serialise to a replayable op-list).

## Honest limits

- `numbers-parser` cannot write a live formula (it stores `=A1+A2` as text), so
  formula edits route to the Numbers application, or fail with a clear
  `ENGINE_UNAVAILABLE` error when it is unavailable.
- It cannot delete a sheet or table; those are refused with a rebuild hint. Rows
  and columns delete normally.
- The application engine (formulas, recalc, export, pdf/png) is macOS only and
  needs Numbers plus Automation permission; the parser engine works anywhere.
- Password-protected files cannot be opened.

## License

GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later). See
[COPYING.LESSER](COPYING.LESSER) (the LGPLv3 additional permissions) and
[COPYING](COPYING) (the GPLv3 base license).
