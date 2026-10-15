"""Command-line interface for rendering verified solution videos."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .engine.encode import EncodeError
from .engine.output import OutputValidationError
from .engine.theme import Theme, load_theme
from .llm import GeminiProvider, GroqProvider, LLMError
from .pipeline import generate_steps, plan_scenes, render, render_from_file
from .schema import QuestionInput, SolutionSpec
from .verify import verify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="solution-video",
        description="Generate accurate, content-driven solution videos.",
        epilog="Exit codes: 0 success; 2 input/accuracy block; 3 LLM failure; 4 render failure; 5 output constraints failed.",
    )
    parser.add_argument("--version", action="version", version=f"solution-video {__version__}")
    sub = parser.add_subparsers(dest="command")

    render_parser = sub.add_parser("render", help="Render a content-driven solution JSON")
    render_parser.add_argument("--input", required=True, type=Path)
    render_parser.add_argument("--out", required=True, type=Path)
    _add_render_options(render_parser)

    steps_parser = sub.add_parser("steps", help="Generate and verify steps from today.json")
    steps_parser.add_argument("--input", required=True, type=Path)
    steps_parser.add_argument("--out", required=True, type=Path)
    steps_parser.add_argument("--provider", choices=("groq", "gemini"), default="groq")
    steps_parser.add_argument("--seed", type=_seed)

    today_parser = sub.add_parser("render-from-today", help="Generate, verify, then render today.json")
    today_parser.add_argument("--input", required=True, type=Path)
    today_parser.add_argument("--out", required=True, type=Path)
    today_parser.add_argument("--provider", choices=("groq", "gemini"), default="groq")
    _add_render_options(today_parser)

    validate_parser = sub.add_parser("validate", help="Validate a question or render-ready solution JSON")
    validate_parser.add_argument("--input", required=True, type=Path)

    sub.add_parser("voice-test", help="Report speech-synthesis support available in this release")
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "voice-test":
        print("Speech synthesis is not integrated in v0.1.0; generated MP4s contain sound effects only.")
        return 4
    if args.command == "validate":
        return _validate_input(args.input)

    _load_local_env()
    render_started = False
    try:
        if args.command == "steps":
            spec = _generate_from_today(args.input, args.provider, args.seed)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
            print(f"Wrote verified steps to {args.out}")
            return 0

        if args.command == "render":
            spec = _load_render_spec(args.input)
            _apply_seed(spec, args.seed)
            gate = verify(spec.question_input, spec)
            if not gate.passed:
                return _blocked(args.out, gate.reasons)
            render_started = True
            if args.dry_run:
                _print_plan(spec, load_theme(args.theme))
                return 0
            meta = render(
                spec, load_theme(args.theme), args.out,
                no_voice=args.no_voice,
            )
        else:
            spec = _generate_from_today(args.input, args.provider, args.seed)
            render_started = True
            if args.dry_run:
                _print_plan(spec, load_theme(args.theme))
                return 0
            meta = render(
                spec, load_theme(args.theme), args.out,
                no_voice=args.no_voice,
            )
    except LLMError as exc:
        print(f"LLM failed: {exc}", file=sys.stderr)
        return 3
    except OutputValidationError as exc:
        print(f"Output constraints failed: {exc}", file=sys.stderr)
        return 5
    except EncodeError as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 4
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        if render_started:
            print(f"Render failed: {exc}", file=sys.stderr)
            return 4
        print(f"Input or accuracy validation failed: {exc}", file=sys.stderr)
        if args.command in {"steps", "render-from-today", "render"}:
            _write_blocked_meta(args.out, [str(exc)])
        return 2

    print(f"Rendered {meta.path}: {meta.duration_s:.1f}s ({meta.size_bytes} bytes).")
    if args.verbose:
        print(f"Verified: {meta.answer_verified}; voice: {meta.voice_provider or 'none'}; version: {meta.version}")
        for warning in meta.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
    return 0


def _add_render_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--theme", type=Path)
    parser.add_argument("--seed", type=_seed)
    parser.add_argument("--no-voice", action="store_true", help="Render without speech synthesis")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the scene plan without rendering")
    parser.add_argument("--verbose", action="store_true")


def _seed(value: str) -> int:
    try:
        seed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seed must be an integer") from exc
    if not 0 <= seed <= 2**31 - 1:
        raise argparse.ArgumentTypeError("seed must be between 0 and 2147483647")
    return seed


def _load_render_spec(input_path: Path) -> SolutionSpec:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    return SolutionSpec.from_payload(payload)


def _generate_from_today(input_path: Path, provider_name: str, seed: int | None) -> SolutionSpec:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    payload.pop("expected_steps", None)
    question = QuestionInput.model_validate(payload)
    provider = GroqProvider() if provider_name == "groq" else GeminiProvider()
    spec = generate_steps(question, provider, cache_dir=Path("out/.solution-video-cache"))
    _apply_seed(spec, seed)
    return spec


def _apply_seed(spec: SolutionSpec, seed: int | None) -> None:
    if seed is not None:
        spec.seed = seed


def _validate_input(input_path: Path) -> int:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if "question_input" in payload or "expected_steps" in payload:
            spec = SolutionSpec.from_payload(payload)
            result = verify(spec.question_input, spec)
            if not result.passed:
                print("Accuracy gate blocked: " + "; ".join(result.reasons), file=sys.stderr)
                return 2
            print("Valid solution input; accuracy gate passed.")
        else:
            QuestionInput.model_validate(payload)
            print("Valid question input.")
        return 0
    except (OSError, json.JSONDecodeError, ValueError, ValidationError) as exc:
        print(f"Input validation failed: {exc}", file=sys.stderr)
        return 2


def _print_plan(spec: SolutionSpec, theme: Theme) -> None:
    plan = plan_scenes(spec, theme)
    print(json.dumps({
        "renders": False,
        "estimated_duration_s": round(sum(item.duration_s for item in plan), 2),
        "scenes": [{"name": item.name, "duration_s": round(item.duration_s, 2)} for item in plan],
    }, indent=2))


def _blocked(output_path: Path, reasons: tuple[str, ...]) -> int:
    _write_blocked_meta(output_path, reasons)
    print("Accuracy gate blocked render: " + "; ".join(reasons), file=sys.stderr)
    return 2


def _write_blocked_meta(output_path: Path, reasons: list[str] | tuple[str, ...]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.with_suffix(".meta.json").write_text(
        json.dumps({"status": "blocked", "answer_verified": False, "reasons": list(reasons)}, indent=2),
        encoding="utf-8",
    )


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
