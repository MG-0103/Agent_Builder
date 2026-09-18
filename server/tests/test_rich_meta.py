"""Tests for enriched parser meta (docstrings, signatures, agent descriptions)
that Phase 0 of the auto-probe depends on."""
from pathlib import Path

from adk_parser import parse_path

RICH = Path(__file__).parent / "fixtures" / "rich_meta"


def _by_name(nodes, name):
    return next(n for n in nodes if n.name == name)


def test_tool_docstring_extracted():
    g = parse_path(RICH)
    check = _by_name(g.nodes, "check_balance")
    doc = check.meta.get("docstring")
    assert doc is not None
    assert "current balance" in doc.lower()


def test_tool_params_and_return_annotations():
    g = parse_path(RICH)
    check = _by_name(g.nodes, "check_balance")
    params = check.meta.get("params")
    assert params == [{"name": "account_id", "annotation": "str"}]
    assert check.meta.get("returns") == "float"


def test_async_tool_wrapped_in_functiontool_carries_signature():
    g = parse_path(RICH)
    send = _by_name(g.nodes, "send_email")
    assert send.meta.get("returns") == "bool"
    names = [p["name"] for p in send.meta.get("params", [])]
    assert names == ["to", "subject", "body"]
    doc = send.meta.get("docstring")
    assert doc and "email" in doc.lower()


def test_agent_description_extracted():
    g = parse_path(RICH)
    refund = _by_name(g.nodes, "refund_agent")
    desc = refund.meta.get("description")
    assert desc is not None
    assert "refund" in desc.lower()
    # Instruction is separate from description and both should be present.
    assert refund.meta.get("instruction")
