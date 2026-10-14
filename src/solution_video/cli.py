"""Command line entry point. Commands are added in phases 1-6 (render, steps, render-from-today, validate, voice-test)."""
import argparse
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solution-video", description="JSON in, solution video out.")
    parser.add_argument("--version", action="version", version=f"solution-video {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("render", help="Render a video from a spec JSON (not implemented yet: phase 1/2)")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    print(f"'{args.command}' is not implemented yet. See PLAN.md and docs/prompts/.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
