import json
from pathlib import Path

from adk_parser.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "simple_agent"


def test_cli_writes_valid_json(tmp_path, capsys):
    out = tmp_path / "graph.json"
    rc = main([str(FIXTURE), "-o", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["framework"] == "google-adk"
    assert any(n["name"] == "researcher" for n in payload["nodes"])


def test_cli_stdout(capsys):
    rc = main([str(FIXTURE)])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["nodes"]


def test_cli_emit(tmp_path):
    out = tmp_path / "emitted.py"
    rc = main([str(FIXTURE), "--emit", "-o", str(out)])
    assert rc == 0
    src = out.read_text()
    assert "LlmAgent" in src
    assert "researcher" in src
