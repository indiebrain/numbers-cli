# Tool install guide

The tool lives in its own repository,
<https://github.com/indiebrain/numbers-cli>, and installs from a public Homebrew
tap. Read this when `nmbr doctor` reports a missing piece or an install fails.

## The command line (`nmbr`)

```bash
brew tap indiebrain/numbers
brew install numbers-cli
```

This puts `nmbr` on your path (`$(brew --prefix)/bin/nmbr`) and pulls in
`python@3.13`. The snappy dependency is bundled via `cramjam`, so nothing
system-level is required.

Without Homebrew, install from source with pipx:

```bash
pipx install 'git+https://github.com/indiebrain/numbers-cli'
```

## The Model Context Protocol server (optional)

The Homebrew formula installs the core command line only, because the server
pulls in a large dependency tree (pydantic, starlette, uvicorn, ...). Enable it
in an isolated pipx environment:

```bash
pipx install 'numbers-cli[mcp] @ git+https://github.com/indiebrain/numbers-cli'
```

That provides an `nmbr` with `nmbr mcp`. Register it with Claude Code:

```bash
claude mcp add apple-numbers -- "$(command -v nmbr)" mcp
```

## The Numbers application (for formulas, rendering, export)

Only needed for `recalc`, `export`, and `view --as pdf|png`.

- Install **Numbers** from the Mac App Store.
- The first time a command drives Numbers, macOS asks to allow Automation. Grant
  it under **System Settings, Privacy and Security, Automation** for the terminal
  or client you run from. Until then those commands return `ENGINE_UNAVAILABLE`.
- `png` rendering also uses `sips`, which ships with macOS.

Confirm with `nmbr doctor`: `app_engine_available` should be `true` and
`numbers_app` should show the application path.
