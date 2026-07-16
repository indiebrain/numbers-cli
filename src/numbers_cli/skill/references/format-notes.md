# Format notes and honest limits

## The `.numbers` format

A `.numbers` file is a zip archive (older documents can be a folder "package")
containing an `Index/` directory of `.iwa` streams. Each stream is a Snappy
compressed sequence of protocol buffer archives; each archive has a numeric
identifier and a typed message. Apple publishes no specification. Everything this
tool does on the file directly rests on `numbers-parser`, which reverse-engineered
that format and is tested against Numbers 10.0 through 14.4.

Because there is no from-scratch reimplementation to build, the design leans on
the two engines that exist and is explicit about where each falls short.

## What the parser engine cannot do

- **Evaluate formulas.** Writing `=A1+A2` through `numbers-parser` stores the
  text `=A1+A2`, not a formula. Real formulas need the Numbers application, which
  is why `set` routes anything starting with `=` there. This is the single most
  important thing to understand about the tool. When the application is
  unavailable, a formula write fails with `ENGINE_UNAVAILABLE`; `--as-text`
  stores the literal string on purpose.
- **Delete a sheet or table.** The library saves from an internal model, so
  removing a sheet or table from the exposed object list does not persist. The
  tool refuses these rather than reporting a success that does nothing. Rebuild
  without them via `dump` then `batch`, or delete them in the Numbers
  application.
- **Open password-protected files.** Re-save without a password in Numbers first.
- **Some styling.** Non-standard fonts fall back to Helvetica Neue, a few
  currencies use a symbol rather than a code, and borders on merged cells have
  gaps. These are `numbers-parser` limits, carried through here.

## What needs the Numbers application

`recalc`, `export`, and `view --as pdf|png` drive the Numbers application through
`osascript`. That means:

- **macOS only.** The parser-based commands run anywhere; these do not.
- **Numbers must be installed.** Run `nmbr doctor`; if `app_engine_available` is
  false, install Numbers from the App Store.
- **Automation permission.** macOS prompts the first time the terminal or client
  drives Numbers. Grant it under System Settings, Privacy and Security,
  Automation. A denial surfaces as `ENGINE_UNAVAILABLE` with a hint.
- **It is a real application.** Driving it launches Numbers briefly and is slower
  than the parser path.

## The raw layer is read only

`raw` decodes and lists the protocol buffer objects for inspection. Writing at
that level is deliberately not offered: patching undocumented protocol buffers can
produce files Numbers silently repairs or refuses to open, and it cannot be
verified safely. Use the higher layers for edits.

## Scope this build does not cover

Charts, conditional formatting, sparklines, data validation, and pivot tables are
out of scope for now. Cell styles, borders, custom number formats, merged cells,
and image insertion are supported by `numbers-parser` and are the natural next
additions to the L2 surface.
