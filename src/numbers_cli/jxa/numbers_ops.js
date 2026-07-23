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

ObjC.import("Foundation");

// Sleep without StandardAdditions: the global `delay` is not dependable from a
// script file and `Application(...).delay` is not understood by app objects, so
// use the Foundation bridge, which works regardless of the host application.
function sleep(seconds) {
  $.NSThread.sleepForTimeInterval(seconds);
}

function readInput(argv) {
  if (!argv || argv.length === 0) throw new Error("missing JSON argument");
  return JSON.parse(argv[0]);
}

function basename(p) {
  const i = String(p).lastIndexOf("/");
  return i >= 0 ? String(p).slice(i + 1) : String(p);
}

// Resolve the open document by matching its name (or file path) against the
// requested file. app.open() cannot be trusted to return the document -- on some
// Numbers builds (seen on 15.3) it returns null even though the file opens -- so
// we look it up in app.documents instead. Matching by name also avoids grabbing
// an unrelated window that happened to be frontmost.
function findOpenDoc(app, file) {
  const want = basename(file);
  const wantNoExt = want.replace(/\.numbers$/i, "");
  const docs = app.documents;
  for (let i = 0; i < docs.length; i++) {
    const doc = docs[i];
    let name = null;
    try { name = doc.name(); } catch (e) {}
    if (name && (name === want || name === wantNoExt)) return doc;
    let path = null;
    try { path = String(doc.file()); } catch (e) {}
    if (path && path.indexOf(want) !== -1) return doc;
  }
  return null;
}

function withDocument(app, file, fn) {
  // Never rely on app.open()'s return value (null on some builds). Open, then
  // resolve the document from app.documents, polling briefly for the window to
  // appear before giving up.
  app.open(Path(file));
  let doc = null;
  for (let i = 0; i < 50 && doc === null; i++) {
    doc = findOpenDoc(app, file);
    if (doc === null) sleep(0.1);
  }
  if (doc === null) {
    throw new Error("Numbers did not open the document: " + file);
  }
  try {
    return fn(doc);
  } finally {
    try {
      doc.close({ saving: "no" });
    } catch (e) {
      // Closing is best effort: never let a close failure mask the real result
      // or error from fn (a null-doc close was the original masking bug).
    }
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
    // Materialize the value with the accessor call before writing it back:
    // `anchor.value` is a specifier, so `anchor.value = anchor.value` assigns a
    // specifier rather than a concrete value and does not reliably dirty the
    // document. `anchor.value()` returns the actual value.
    anchor.value = anchor.value(); // no-op write to trigger recalculation
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
