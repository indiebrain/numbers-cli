// JavaScript for Automation (JXA) dispatcher for the Numbers application.
//
// Invoked by numbers_cli.engine.app_engine as:
//   osascript -l JavaScript numbers_ops.js '<json>'
// where <json> is {op, file, ...}. Everything the parser engine cannot do lives
// here: entering real formulas (so Numbers evaluates them), forcing a
// recalculation, and native export. Results are printed to stdout as JSON.
//
// This file only runs on macOS with Numbers installed. app_engine checks for the
// application first and never calls in when it is missing.

function readInput(argv) {
  if (!argv || argv.length === 0) throw new Error("missing JSON argument");
  return JSON.parse(argv[0]);
}

function withDocument(app, file, fn) {
  const doc = app.open(Path(file));
  try {
    return fn(doc);
  } finally {
    doc.close({ saving: "no" });
  }
}

// Numbers addresses cells as ranges like "B2". A cell whose value string starts
// with "=" is entered as a formula and evaluated by Numbers.
function setOne(doc, edit) {
  const sheet = edit.sheet != null ? doc.sheets[edit.sheet] : doc.sheets[0];
  const table = edit.table != null ? sheet.tables[edit.table] : sheet.tables[0];
  const cell = table.cells.byName(edit.a1);
  cell.value = edit.value;
  // Read the value back with the accessor call: `cell.value` is a specifier, and
  // String() on a specifier throws "Can't convert types" on recent Numbers
  // (seen on 15.2), which would abort every formula write.
  return { a1: edit.a1, value: String(cell.value()), formula: cell.formula() };
}

function opSet(app, input) {
  return withDocument(app, input.file, function (doc) {
    const results = (input.edits || []).map(function (e) {
      return setOne(doc, e);
    });
    doc.save();
    return { ok: true, op: "set", edits: results };
  });
}

function opRecalc(app, input) {
  // Numbers recalculates on change; nudging a cell forces a dependency refresh.
  return withDocument(app, input.file, function (doc) {
    const table = doc.sheets[0].tables[0];
    const anchor = table.cells.byName("A1");
    const keep = anchor.value;
    anchor.value = keep; // no-op write to trigger recalculation
    doc.save();
    return { ok: true, op: "recalc" };
  });
}

function opGet(app, input) {
  return withDocument(app, input.file, function (doc) {
    const cells = (input.cells || []).map(function (c) {
      const sheet = c.sheet != null ? doc.sheets[c.sheet] : doc.sheets[0];
      const table = c.table != null ? sheet.tables[c.table] : sheet.tables[0];
      const cell = table.cells.byName(c.a1);
      return { a1: c.a1, value: cell.value(), formula: cell.formula() };
    });
    return { ok: true, op: "get", cells: cells };
  });
}

function opExport(app, input) {
  const FORMATS = { csv: "CSV", pdf: "PDF", xlsx: "Microsoft Excel", excel: "Microsoft Excel" };
  const fmt = FORMATS[(input.format || "").toLowerCase()];
  if (!fmt) throw new Error("unsupported export format: " + input.format);
  return withDocument(app, input.file, function (doc) {
    app.export(doc, { to: Path(input.out), as: fmt });
    return { ok: true, op: "export", out: input.out, format: fmt };
  });
}

function run(argv) {
  const app = Application("Numbers");
  app.includeStandardAdditions = true;
  const input = readInput(argv);
  const ops = { set: opSet, recalc: opRecalc, get: opGet, export: opExport };
  const handler = ops[input.op];
  if (!handler) throw new Error("unknown op: " + input.op);
  try {
    return JSON.stringify(handler(app, input));
  } catch (err) {
    return JSON.stringify({ ok: false, op: input.op, error: String(err) });
  }
}
