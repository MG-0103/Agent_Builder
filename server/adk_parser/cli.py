import argparse
import sys

from .adapter import parse_path
from .codegen import EmitSkipped, emit_python


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="parse-agents", description="Extract Google ADK agent graph from source.")
    p.add_argument("path", help="Root directory to scan.")
    p.add_argument("-o", "--out", help="Write JSON to file (default: stdout).")
    p.add_argument(
        "--emit",
        action="store_true",
        help="Emit ADK Python source reconstructed from the graph instead of JSON.",
    )
    args = p.parse_args(argv)

    graph = parse_path(args.path)

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
