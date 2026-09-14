"""Import cycle across two modules — resolver must not loop forever.

`a.thing` re-exports from `b.thing`, `b.thing` re-exports from `a.thing`.
Neither defines it. Should end up unresolved, not hang.
"""
from .b import thing  # noqa: F401
