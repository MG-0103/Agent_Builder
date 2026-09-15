"""Entry-module ranking: score candidates so the client can suggest one."""

from __future__ import annotations

from pathlib import Path

from adk_parser.entry_candidates import rank_entry_candidates

FIXTURES = Path(__file__).parent / "fixtures"


def test_simple_agent_top_pick_is_agent_module():
    """simple_agent/agent.py holds the constructions → it wins."""
    out = rank_entry_candidates(FIXTURES / "simple_agent")
    assert out, "expected at least one candidate"
    assert out[0].module == "agent"
    assert out[0].agent_count >= 3
    assert any("agent construction" in r for r in out[0].reasons)
    assert any("conventional name" in r for r in out[0].reasons)


def test_multi_file_prefers_pipeline_over_tools():
    """pkg/pipeline.py has the SequentialAgent; pkg/tools.py has no agents,
    so the ranker should surface pipeline first and skip tools entirely."""
    out = rank_entry_candidates(FIXTURES / "multi_file")
    modules = [c.module for c in out]
    assert "pkg.pipeline" in modules
    # tools.py doesn't build agents, so it scores 0 and must be excluded.
    assert "pkg.tools" not in modules
    # pipeline should rank above researcher and writer because it names them.
    assert modules.index("pkg.pipeline") <= modules.index("pkg.writer")


def test_ranker_ignores_syntax_errors(tmp_path):
    (tmp_path / "broken.py").write_text("this is not python")
    (tmp_path / "agent.py").write_text(
        "from google.adk.agents import LlmAgent\n"
        "root = LlmAgent(name='x', model='m', instruction='i')\n"
    )
    out = rank_entry_candidates(tmp_path)
    modules = [c.module for c in out]
    assert "agent" in modules
    assert "broken" not in modules


def test_main_guard_boosts_score(tmp_path):
    (tmp_path / "run.py").write_text(
        "from google.adk.agents import LlmAgent\n"
        "root = LlmAgent(name='r', model='m', instruction='i')\n"
        "if __name__ == '__main__':\n"
        "    pass\n"
    )
    (tmp_path / "other.py").write_text(
        "from google.adk.agents import LlmAgent\n"
        "root = LlmAgent(name='o', model='m', instruction='i')\n"
    )
    out = rank_entry_candidates(tmp_path)
    modules = [c.module for c in out]
    assert modules[0] == "run"
