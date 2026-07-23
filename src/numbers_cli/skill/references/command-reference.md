# Command reference

Every command prints one JSON object. Add `--human` before the command name for
readable output. Paths follow the grammar in `SKILL.md`.

## create

```
nmbr create <file> [--sheets NAME ...] [--rows N] [--cols N] [--force]
```

Create a blank document. `--sheets` names the sheets (default one `Sheet 1`);
the first sheet keeps a default `Table 1`. Refuses to overwrite unless `--force`.

```
nmbr create budget.numbers --sheets Budget Notes
```

## view (L1)

```
nmbr view <file> [path] --as text|csv|md|outline|json|html|pdf|png [--out FILE]
```

With no path, views every table. With a sheet path, views that sheet's tables;
with a table path, just that table. `outline` lists sheets and tables with their
sizes. `html` is generated locally and needs no application; `pdf` and `png` use
the Numbers application (`png` rasterises the pdf with `sips`).

```
nmbr view budget.numbers /sheet[1]/table[1] --as csv
nmbr view budget.numbers --as outline
nmbr view budget.numbers /sheet[1] --as html --out preview.html
```

## get (L2)

```
nmbr get <file> <path>
```

Reads whatever the path points at. A cell returns its type, value, formatted
text, and formula if any. A range returns every cell. A row or column returns its
values. A table or sheet path returns a summary.

## set (L2)

```
nmbr set <file> <path> <value> [--as-text]
```

Writes a value into a cell or every cell of a range. Values are typed
automatically: `42` is a number, `true` a boolean, `2026-07-15` a date, anything
else text. A value starting with `=` is a formula and routes to the Numbers
application; `--as-text` stores the literal string instead (with a warning) when
the application is unavailable.

```
nmbr set budget.numbers /sheet[1]/table[1]/cell[A1] "Revenue"
nmbr set budget.numbers "/sheet['Budget']/table[1]/cell[B10]" "=SUM(B2:B9)"
```

## add (L2)

```
nmbr add <file> [path] --kind sheet|table|row|col [--name NAME] [--count K]
```

Adds a sheet (no path needed), a table to the sheet in `path`, or rows or columns
to the table in `path`. A `row` or `col` leaf path inserts at that position;
otherwise it appends.

## remove (L2)

```
nmbr remove <file> <path> [--kind row|col] [--count K]
```

Removes the addressed rows or columns. Removing a sheet or table is not supported
by `numbers-parser` and is refused with a hint (rebuild via `dump` then `batch`,
or use the Numbers application).

## query (L2)

```
nmbr query <file> <text> [--path SHEET_OR_TABLE] [--case-sensitive]
```

Finds cells whose display text contains the substring and returns their paths -
useful before an edit.

## batch

```
nmbr batch <file> <ops.json | inline-json> [--as-text]
```

Applies a JSON array of operations in one open and save pass. Structural
operations (`add`, `remove`) apply in order; value operations (`set`) commit
together at the end so formulas share one recalculation. Operation shapes:

```json
[
  {"op": "add", "kind": "table", "path": "/sheet[1]", "name": "Q1"},
  {"op": "set", "path": "/sheet[1]/table['Q1']/cell[A1]", "value": "Revenue"},
  {"op": "remove", "path": "/sheet[1]/table[1]/row[5]", "kind": "row"}
]
```

## merge

```
nmbr merge <template> <data.json> -o <out>
```

Copies the template and replaces `{{key}}` tokens from the data mapping. A cell
that is exactly one token adopts the value's type; a mixed cell stays text.
Unmatched tokens are left in place and reported as a warning.

## dump

```
nmbr dump <file>
```

Emits `{"document": {...}, "ops": [...]}` describing the sheets and tables and a
`set` operation for every non-empty cell. Replaying `ops` through `batch` into a
freshly created file reproduces the data content (not the styling or layout).

## raw (L3, read)

```
nmbr raw <file> [--id N] [--grep TYPE]
```

Lists the underlying IWA protocol buffer objects as `{id, type, stream}`, or
decodes one object to a dict with `--id`. `--grep` filters the catalog by type
name.

## recalc, export (application engine)

```
nmbr recalc <file>
nmbr export <file> --to csv|xlsx|pdf [--out FILE]
```

Both need the Numbers application. `recalc` forces a recalculation and saves;
`export` uses Numbers' native exporter.

## doctor, mcp

```
nmbr doctor          # versions, engine availability, and the resolved app's identity
nmbr doctor --probe  # additionally drive Numbers end to end (launches it) and report app_engine_healthy
nmbr mcp             # run the MCP server over stdio
```

`app_engine_available` only proves the app resolves; `--probe` opens a throwaway
document through the same path real operations use and reports whether it
actually round trips (`app_engine_healthy`). `numbers_app_info` names the app
that resolved (Apple ships Numbers under more than one display name).
