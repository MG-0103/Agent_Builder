import argparse
import sys
from pathlib import Path

from .adapter import parse_path
from .codegen import EmitSkipped, apply_region, emit_layout, emit_python


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="parse-agents",
        description="Extract Google ADK agent graph from source.",
    )
    p.add_argument("path", help="Root directory to scan.")
    p.add_argument("-o", "--out", help="Write output to file/dir (default: stdout for JSON/flat emit; required for --emit-layout).")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--emit",
        action="store_true",
        help="Emit ADK Python source (flat single-file) reconstructed from the graph.",
    )
    mode.add_argument(
        "--emit-layout",
        action="store_true",
        help="Emit per-file ADK Python into --out directory, merging with existing files via region markers.",
    )
    args = p.parse_args(argv)

    graph = parse_path(args.path)

    if args.emit_layout:
        if not args.out:
            print("--emit-layout requires -o <dir>", file=sys.stderr)
            return 2
        try:
            bodies = emit_layout(graph)
        except EmitSkipped as e:
            print(f"emit skipped: {e}", file=sys.stderr)
            return 2
        out_root = Path(args.out)
        out_root.mkdir(parents=True, exist_ok=True)
        for rel, body in bodies.items():
            target = out_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text() if target.exists() else ""
            target.write_text(apply_region(existing, body))
        return 0

    if args.emit:
        try:
            payload = emit_python(graph)
        except EmitSkipped as e:
            print(f"emit skipped: {e}", file=sys.stderr)
            return 2
    else:
        payload = graph.model_dump_json(indent=2)

    if args.out:
        with open(args.out, "w") as f:
            f.write(payload)
    else:
        sys.stdout.write(payload + ("\n" if not args.emit else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
