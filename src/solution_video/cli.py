"""Command line entry point for Phase-1 rendering."""
import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .engine.encode import EncodeError
from .llm import GeminiProvider, GroqProvider, LLMError
from .pipeline import generate_steps, render, render_from_file
from .schema import QuestionInput
from .engine.theme import load_theme


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solution-video", description="JSON in, solution video out.")
    parser.add_argument("--version", action="version", version=f"solution-video {__version__}")
    sub = parser.add_subparsers(dest="command")
    render_parser = sub.add_parser("render", help="Render a content-driven solution JSON")
    render_parser.add_argument("--input", required=True, type=Path)
    render_parser.add_argument("--out", required=True, type=Path)
    render_parser.add_argument("--theme", type=Path)
    render_parser.add_argument("--no-voice", action="store_true", help="Accepted for future compatibility")
    steps_parser = sub.add_parser("steps", help="Generate and verify steps from today.json")
    steps_parser.add_argument("--input", required=True, type=Path)
    steps_parser.add_argument("--out", required=True, type=Path)
    steps_parser.add_argument("--provider", choices=("groq", "gemini"), default="groq")
    today_parser = sub.add_parser("render-from-today", help="Generate, verify, then render today.json")
    today_parser.add_argument("--input", required=True, type=Path)
    today_parser.add_argument("--out", required=True, type=Path)
    today_parser.add_argument("--provider", choices=("groq", "gemini"), default="groq")
    today_parser.add_argument("--theme", type=Path)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "render":
        try:
            meta = render_from_file(args.input, args.out, theme_path=args.theme)
        except (ValueError, EncodeError) as exc:
            print(f"render failed: {exc}", file=sys.stderr)
            return 2 if "Accuracy gate" in str(exc) else 4
        print(f"Rendered {meta.path}: {meta.duration_s:.1f}s ({meta.size_bytes} bytes).")
        return 0
    if args.command in {"steps", "render-from-today"}:
        _load_local_env()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            # Checked-in examples carry expected_steps as local fixtures; it is not today.json input.
            payload.pop("expected_steps", None)
            question = QuestionInput.model_validate(payload)
            provider = GroqProvider() if args.provider == "groq" else GeminiProvider()
            spec = generate_steps(question, provider, cache_dir=Path("out/.solution-video-cache"))
        except LLMError as exc:
            print(f"LLM failed: {exc}", file=sys.stderr)
            return 3
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"accuracy gate failed: {exc}", file=sys.stderr)
            args.out.with_suffix(".meta.json").write_text(json.dumps({"status": "blocked", "answer_verified": False, "reasons": [str(exc)]}, indent=2), encoding="utf-8")
            return 2
        if args.command == "steps":
            args.out.write_text(json.dumps(spec.model_dump(mode="json"), indent=2), encoding="utf-8")
            print(f"Wrote verified steps to {args.out}")
            return 0
        try:
            meta = render(spec, load_theme(args.theme), args.out)
        except (ValueError, EncodeError) as exc:
            print(f"render failed: {exc}", file=sys.stderr)
            return 2 if "Accuracy gate" in str(exc) else 4
        print(f"Rendered {meta.path}: {meta.duration_s:.1f}s ({meta.size_bytes} bytes).")
        return 0
    return 1


def _load_local_env() -> None:
    """Load only missing environment keys from ignored .env; never print values."""
    path = Path(".env")
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in {"GROQ_API_KEY", "GROQ_MODEL", "GEMINI_API_KEY"} and not os.getenv(key):
            os.environ[key] = value.strip()


if __name__ == "__main__":
    raise SystemExit(main())
