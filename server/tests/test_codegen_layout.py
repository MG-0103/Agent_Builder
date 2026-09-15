"""Layout-preserving emit + region merge tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from adk_parser import parse_path
from adk_parser.codegen import (
    REGION_END,
    REGION_START,
    apply_region,
    emit_layout,
)

FIXTURES = Path(__file__).parent / "fixtures"

# _normalize is a straight import from the flat-emit test.
from test_codegen import _normalize  # noqa: E402


def _materialize(files: dict[str, str], root: Path) -> None:
    """Write emit_layout output onto ``root``, wrapped in region markers."""
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text() if target.exists() else ""
        target.write_text(apply_region(existing, body))


@pytest.mark.parametrize("fixture", [
    "simple_agent",
    "multi_file",
    "state_flow",
    "shared_callback",
    "attr_chain",
])
def test_layout_round_trip(fixture, tmp_path):
    src = FIXTURES / fixture
    g1 = parse_path(src)

    files = emit_layout(g1)
    assert files, "layout emit produced no files"

    # Write into a fresh directory (no pre-existing content).
    _materialize(files, tmp_path)

    # A package with sub-modules needs a stub __init__.py to be importable
    # under our from-imports layout. The adapter walks .py files regardless,
    # so it doesn't strictly need one, but be explicit.
    for rel in files:
        parent = Path(rel).parent
        if parent.parts:
            init = tmp_path / parent / "__init__.py"
            if not init.exists():
                init.write_text("")

    g2 = parse_path(tmp_path)

    assert _normalize(g1) == _normalize(g2), (
        f"layout round-trip diverged for {fixture}\n"
        f"emitted files: {list(files)}\n"
    )


def test_apply_region_appends_when_absent(tmp_path):
    existing = "# hand-written\nimport os\n"
    merged = apply_region(existing, "x = 1\n")
    assert existing in merged
    assert REGION_START in merged
    assert REGION_END in merged
    assert "x = 1" in merged


def test_apply_region_replaces_existing_block():
    existing = (
        "# hand-written above\n"
        "keep_this = 1\n"
        f"{REGION_START}\n"
        "old = 'stale'\n"
        f"{REGION_END}\n"
        "# hand-written below\n"
        "also_keep = 2\n"
    )
    merged = apply_region(existing, "new = 'fresh'\n")
    assert "keep_this = 1" in merged
    assert "also_keep = 2" in merged
    assert "old = 'stale'" not in merged
    assert "new = 'fresh'" in merged
    # Exactly one region block after merge.
    assert merged.count(REGION_START) == 1
    assert merged.count(REGION_END) == 1


def test_regen_preserves_hand_edits(tmp_path):
    """A hand-edit outside the region survives re-emit; an old region gets
    replaced in place."""
    g = parse_path(FIXTURES / "simple_agent")
    files = emit_layout(g)
    _materialize(files, tmp_path)

    # Add hand-edited content around one file's region.
    rel = next(iter(files))
    target = tmp_path / rel
    original = target.read_text()
    hand_edited = (
        "# hand-written header\n"
        "MY_CONST = 42\n\n"
        + original
        + "\n# hand-written trailer\n"
        "def custom_helper():\n    return MY_CONST\n"
    )
    target.write_text(hand_edited)

    # Re-emit. Content outside the region must be preserved.
    files_v2 = emit_layout(g)
    _materialize(files_v2, tmp_path)

    after = target.read_text()
    assert "MY_CONST = 42" in after
    assert "custom_helper" in after
    assert after.count(REGION_START) == 1
    assert after.count(REGION_END) == 1
