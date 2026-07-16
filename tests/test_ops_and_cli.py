import json

import pytest

from numbers_cli import cli
from numbers_cli.engine import parser_engine as pe
from numbers_cli.errors import EngineUnavailable
from numbers_cli.layers import l2_dom
from numbers_cli.ops import batch, dump, merge
from numbers_cli.router import set_cells


def test_batch_applies_structural_then_values(doc_path):
    ops = [
        {"op": "add", "kind": "table", "path": "/sheet[1]", "name": "Q1"},
        {"op": "set", "path": "/sheet[1]/table['Q1']/cell[A1]", "value": "Revenue"},
    ]
    result = batch.apply(doc_path, ops)
    assert result["literal_cells"] == ["A1"]
    reopened = pe.open_document(doc_path)
    assert l2_dom.get(reopened, "/sheet[1]/table['Q1']/cell[A1]")["value"] == "Revenue"


def test_dump_then_batch_roundtrips_values(doc_path, tmp_path):
    recipe = dump.dump(doc_path)
    fresh = str(tmp_path / "fresh.numbers")
    doc = pe.new_document(["Budget"])
    pe.save_document(doc, fresh)
    batch.apply(fresh, recipe["ops"])
    original = pe.open_document(doc_path)
    rebuilt = pe.open_document(fresh)
    assert (
        l2_dom.get(original, "/sheet[1]/table[1]/cell[B2]")["value"]
        == l2_dom.get(rebuilt, "/sheet[1]/table[1]/cell[B2]")["value"]
    )


def test_merge_typed_and_missing(doc_path, tmp_path):
    tpl = str(tmp_path / "tpl.numbers")
    doc = pe.new_document(["S"])
    doc.sheets[0].tables[0].write("A1", "Hi {{name}}")
    doc.sheets[0].tables[0].write("A2", "{{total}}")
    doc.sheets[0].tables[0].write("A3", "{{unknown}}")
    pe.save_document(doc, tpl)
    out = str(tmp_path / "out.numbers")
    result = merge.merge(tpl, {"name": "Ada", "total": 42}, out)
    assert result["count"] == 2
    assert any("unknown" in w for w in result.get("warnings", []))
    reopened = pe.open_document(out)
    assert l2_dom.get(reopened, "/sheet[1]/table[1]/cell[A1]")["value"] == "Hi Ada"
    assert l2_dom.get(reopened, "/sheet[1]/table[1]/cell[A2]")["value"] == 42.0


def test_formula_without_numbers_raises(doc_path):
    with pytest.raises(EngineUnavailable):
        set_cells(doc_path, [("/sheet[1]/table[1]/cell[C1]", "=A1+B2")])


def test_formula_as_text_warns(doc_path):
    summary = set_cells(doc_path, [("/sheet[1]/table[1]/cell[C1]", "=A1+B2")], allow_text_formula=True)
    assert summary["warnings"]
    reopened = pe.open_document(doc_path)
    assert l2_dom.get(reopened, "/sheet[1]/table[1]/cell[C1]")["value"] == "=A1+B2"


def test_cli_envelope_success_and_failure(doc_path, capsys):
    code = cli.main(["get", doc_path, "/sheet[1]/table[1]/cell[A1]"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] is True and out["data"]["value"] == "Item"

    code = cli.main(["get", doc_path, "/sheet[9]/table[1]/cell[A1]"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and out["ok"] is False and out["error"]["code"] == "PATH_NOT_FOUND"


def test_cli_create_and_view(tmp_path, capsys):
    path = str(tmp_path / "new.numbers")
    assert cli.main(["create", path, "--sheets", "One"]) == 0
    capsys.readouterr()
    assert cli.main(["--human", "view", path, "--as", "outline"]) == 0
    assert "One" in capsys.readouterr().out


def test_skill_install_and_path(tmp_path):
    from numbers_cli import skill

    src = skill.bundled_skill_dir()
    assert (src / "SKILL.md").exists()

    target = skill.install(dest_root=tmp_path)
    assert target == tmp_path / "apple-numbers"
    assert (target / "SKILL.md").exists()
    assert (target / "references" / "command-reference.md").exists()
    assert not (target / "__init__.py").exists()

    import pytest
    from numbers_cli.errors import UsageError

    with pytest.raises(UsageError):
        skill.install(dest_root=tmp_path)  # refuses to overwrite
    skill.install(dest_root=tmp_path, force=True)  # unless forced
