import argparse
import json
import sys

from .adapter import parse_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="parse-agents", description="Extract Google ADK agent graph from source.")
    p.add_argument("path", help="Root directory to scan.")
    p.add_argument("-o", "--out", help="Write JSON to file (default: stdout).")
    args = p.parse_args(argv)

    graph = parse_path(args.path)
    payload = graph.model_dump_json(indent=2)

    if args.out:
        with open(args.out, "w") as f:
            f.write(payload)
    else:
        sys.stdout.write(payload + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
