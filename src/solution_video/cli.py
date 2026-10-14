"""Command line entry point for Phase-1 rendering."""
import argparse
import sys
from pathlib import Path

from . import __version__
from .engine.encode import EncodeError
from .pipeline import render_from_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solution-video", description="JSON in, solution video out.")
    parser.add_argument("--version", action="version", version=f"solution-video {__version__}")
    sub = parser.add_subparsers(dest="command")
    render_parser = sub.add_parser("render", help="Render a content-driven solution JSON")
    render_parser.add_argument("--input", required=True, type=Path)
    render_parser.add_argument("--out", required=True, type=Path)
    render_parser.add_argument("--theme", type=Path)
    render_parser.add_argument("--no-voice", action="store_true", help="Accepted for future compatibility")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "render":
        try:
            meta = render_from_file(args.input, args.out, theme_path=args.theme)
        except (ValueError, EncodeError) as exc:
            print(f"render failed: {exc}", file=sys.stderr)
            return 4
        print(f"Rendered {meta.path}: {meta.duration_s:.1f}s ({meta.size_bytes} bytes).")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
