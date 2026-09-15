"""Rank likely entry modules for the runtime probe.

Users typically don't know which module to name in the ``entry_module``
field. We already parse every .py file in the repo for the static graph;
here we reuse a similar walk to count where the agent constructions
actually live and score modules by:

- how many agent-shaped calls occur at module level (a module that just
  imports agents doesn't count — those get 0)
- whether the module carries ``if __name__ == "__main__"`` (real entry
  script)
- whether the module is named in ``pyproject.toml``'s ``[project.scripts]``
- conventional filenames: ``agent``, ``pipeline``, ``main``, ``__main__``,
  ``app``, ``run``

The output is sorted best-first so the client can offer the top pick as
the default in the entry-module dropdown.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Class names that count as agent constructions when called at module scope.
# Keep in sync with adk_parser.adapter.AGENT_CLASSES; duplicated here to
# avoid importing the whole adapter for a cheap scan.
_AGENT_CLASSES = {
    "LlmAgent",
    "Agent",
    "SequentialAgent",
    "ParallelAgent",
    "LoopAgent",
    "BaseAgent",
}

_CONVENTIONAL_NAMES = {
    "agent": 5,
    "pipeline": 5,
    "main": 4,
    "__main__": 4,
    "app": 3,
    "run": 2,
    "root": 2,
    "workflow": 3,
}


@dataclass
class EntryCandidate:
    module: str
    path: str
    score: int = 0
    agent_count: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "path": self.path,
            "score": self.score,
            "agent_count": self.agent_count,
            "reasons": self.reasons,
        }


def _iter_python_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        parts = p.relative_to(root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        yield p


def _module_fq(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _count_agent_constructions(tree: ast.Module) -> int:
    """Number of module-level agent-class calls (or module-level assigns
    whose RHS is one). Nested calls inside function bodies aren't counted —
    those need to be *invoked* for the agent to exist at import time."""
    count = 0
    for stmt in tree.body:
        # `agent = LlmAgent(...)` or `LlmAgent(...)` bare.
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            if _is_agent_call(stmt.value):
                count += 1
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if _is_agent_call(stmt.value):
                count += 1
    return count


def _is_agent_call(call: ast.Call) -> bool:
    fn = call.func
    if isinstance(fn, ast.Name) and fn.id in _AGENT_CLASSES:
        return True
    if isinstance(fn, ast.Attribute) and fn.attr in _AGENT_CLASSES:
        return True
    return False


def _has_main_guard(tree: ast.Module) -> bool:
    for stmt in tree.body:
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        # `if __name__ == "__main__":`
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
            left = test.left
            right = test.comparators[0] if test.comparators else None
            if (
                isinstance(left, ast.Name)
                and left.id == "__name__"
                and isinstance(right, ast.Constant)
                and right.value == "__main__"
            ):
                return True
    return False


def _pyproject_scripts(root: Path) -> set[str]:
    """Read ``[project.scripts]`` module names out of pyproject.toml, if any."""
    pyproj = root / "pyproject.toml"
    if not pyproj.exists():
        return set()
    try:
        import tomllib  # 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return set()
    try:
        data = tomllib.loads(pyproj.read_text())
    except Exception:
        return set()
    scripts = data.get("project", {}).get("scripts", {}) or {}
    modules: set[str] = set()
    for _name, target in scripts.items():
        # Format is "<module>:<attr>" or just "<module>".
        if isinstance(target, str):
            modules.add(target.split(":", 1)[0])
    return modules


def rank_entry_candidates(root: Path, limit: int = 10) -> list[EntryCandidate]:
    """Return top ``limit`` candidate modules for the entry-module input.

    Ranking is best-effort; ties are broken by shorter module name, then
    lexicographic order for determinism.
    """
    scripts = _pyproject_scripts(root)
    candidates: list[EntryCandidate] = []

    for path in _iter_python_files(root):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        module = _module_fq(root, path)
        if not module:
            # Top-level __init__.py without a package (unlikely) — skip.
            continue

        agent_count = _count_agent_constructions(tree)
        score = agent_count * 10  # heaviest signal
        reasons: list[str] = []
        if agent_count:
            reasons.append(f"{agent_count} agent construction(s)")
        if _has_main_guard(tree):
            score += 8
            reasons.append("has __main__ guard")
        if module in scripts:
            score += 12
            reasons.append("pyproject [project.scripts]")
        leaf = module.rsplit(".", 1)[-1]
        conv = _CONVENTIONAL_NAMES.get(leaf, 0)
        if conv:
            score += conv
            reasons.append(f"conventional name '{leaf}'")

        if score <= 0:
            continue
        candidates.append(
            EntryCandidate(
                module=module,
                path=str(path),
                score=score,
                agent_count=agent_count,
                reasons=reasons,
            )
        )

    candidates.sort(key=lambda c: (-c.score, len(c.module), c.module))
    return candidates[:limit]
