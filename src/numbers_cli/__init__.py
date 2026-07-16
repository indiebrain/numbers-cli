"""numbers_cli: an OfficeCli-style command line and MCP server for Apple Numbers.

The package is organised in the same layered way OfficeCli exposes Office files:

* ``engine`` - the two back ends. ``parser_engine`` reads and writes ``.numbers``
  files directly through ``numbers-parser`` (fast, no application, cross platform).
  ``app_engine`` drives the Numbers application through ``osascript`` for the
  things the parser cannot do: recalculating formulas, rendering, and native
  export.
* ``paths`` - the shared address grammar (``/sheet[1]/table[1]/cell[B2]``).
* ``layers`` - the L1 (view), L2 (structured edit), and L3 (raw) surfaces.
* ``ops`` - batch, template merge, and dump.
* ``router`` - chooses an engine and runs the write then recalculate then reread
  round trip when an edit touches a formula.
"""

__version__ = "0.1.0"
