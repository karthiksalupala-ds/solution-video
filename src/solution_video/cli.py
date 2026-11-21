"""Command-line interface for rendering verified solution videos."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterator

from pydantic import ValidationError
from PIL import Image, ImageDraw

from . import __version__
from .engine.frame_chunks import FrameChunk, render_ordered
from .engine.audio import AudioMixer, write_wav
from .engine.encode import EncodeError, encode_frames
from .engine.output import OutputValidationError, validate_output
from .engine.theme import Theme, load_theme
from .llm import GeminiProvider, GroqProvider, LLMError
from .llm.base import SPEECH_LANGUAGE_MODES
from .pipeline import PlannedScene, generate_steps, plan_scenes, render, render_from_file
from .schema import QuestionInput, SolutionSpec
from .voice.runtime import estimate_voice
from .styles import registered_styles, resolve_style, style_theme
from .verify import verify
from .voice.listening_test import (
    EDGE_VOICES,
    VoiceTestError,
    load_text_variants,
    run_listening_test,
)


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
    steps_parser.add_argument("--speech-language-mode", choices=SPEECH_LANGUAGE_MODES)

    today_parser = sub.add_parser("render-from-today", help="Generate, verify, then render today.json")
    today_parser.add_argument("--input", required=True, type=Path)
    today_parser.add_argument("--out", required=True, type=Path)
    today_parser.add_argument("--provider", choices=("groq", "gemini"), default="groq")
    today_parser.add_argument("--speech-language-mode", choices=SPEECH_LANGUAGE_MODES)
    _add_render_options(today_parser)

    validate_parser = sub.add_parser("validate", help="Validate a question or render-ready solution JSON")
    validate_parser.add_argument("--input", required=True, type=Path)

    voice_parser = sub.add_parser("voice-test", help="Compare approved narration samples with TTS providers")
    voice_parser.add_argument("--input", type=Path, default=Path("examples/speed_train.json"))
    voice_parser.add_argument("--variants", type=Path, default=Path("examples/voice_tests/approved_variants.json"))
    voice_parser.add_argument("--out", type=Path, default=Path("examples/voice_tests"))
    voice_parser.add_argument(
        "--provider",
        choices=("all", "hf_space", "elevenlabs", "edge_tts"),
        default="all",
    )
    voice_parser.add_argument("--elevenlabs-voice-id")
    voice_parser.add_argument("--approve-elevenlabs-credits", type=int)
    voice_parser.add_argument("--synthesize", action="store_true", help="Make provider requests and write audio")
    voice_parser.add_argument("--approve-texts", action="store_true", help="Confirm that the test text was reviewed")
    bench_parser = sub.add_parser("bench", help="Measure style frame rendering without encoding or voice")
    bench_parser.add_argument("--style", default="classic")
    bench_parser.add_argument("--example", required=True, type=Path)
    bench_parser.add_argument("--frames", type=int, default=60)
    bench_parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    gallery_parser = sub.add_parser("gallery", help="Write style contact sheets, a short reel, and an index")
    gallery_parser.add_argument("--example", required=True, type=Path)
    gallery_parser.add_argument("--styles", default="all", help="all or comma-separated registered style names")
    gallery_parser.add_argument("--out", type=Path, default=Path("out/gallery"))
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "voice-test":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        _load_local_env()
        try:
            variants = load_text_variants(args.variants, args.input)
            providers = {"hf_space", "elevenlabs", "edge_tts"} if args.provider == "all" else {args.provider}
            return run_listening_test(
                variants,
                args.out,
                providers,
                synthesize=args.synthesize,
                text_approved=args.approve_texts,
                elevenlabs_voice_id=args.elevenlabs_voice_id,
                approved_elevenlabs_credits=args.approve_elevenlabs_credits,
            )
        except VoiceTestError as exc:
            print(f"Voice test failed: {exc}", file=sys.stderr)
            return 4
    if args.command == "validate":
        return _validate_input(args.input)
    if args.command == "bench":
        return _bench(args.example, args.style, args.frames, args.workers)
    if args.command == "gallery":
        return _gallery(args.example, args.styles, args.out)

    _load_local_env()
    render_started = False
    try:
        if args.command == "steps":
            spec = _generate_from_today(
                args.input, args.provider, args.seed, args.speech_language_mode
            )
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
                _print_plan(
                    spec,
                    _style_theme(load_theme(args.theme), args.style, spec.question_input.day),
                    args.voice_provider,
                    args.no_voice,
                    args.allow_scene_style_overrides,
                )
                return 0
            meta = render(
                spec, load_theme(args.theme), args.out,
                no_voice=args.no_voice,
                voice_provider=args.voice_provider,
                sync_report=args.sync_report,
                style=args.style,
                allow_scene_styles=args.allow_scene_style_overrides,
            )
        else:
            spec = _generate_from_today(
                args.input, args.provider, args.seed, args.speech_language_mode
            )
            render_started = True
            if args.dry_run:
                _print_plan(
                    spec,
                    _style_theme(load_theme(args.theme), args.style, spec.question_input.day),
                    args.voice_provider,
                    args.no_voice,
                    args.allow_scene_style_overrides,
                )
                return 0
            meta = render(
                spec, load_theme(args.theme), args.out,
                no_voice=args.no_voice,
                voice_provider=args.voice_provider,
                sync_report=args.sync_report,
                style=args.style,
                allow_scene_styles=args.allow_scene_style_overrides,
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
    parser.add_argument(
        "--voice-provider",
        choices=("hf_space", "edge_tts", "elevenlabs", "none"),
        help="Override the configured narration provider order for this run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the scene plan without rendering")
    parser.add_argument("--sync-report", action="store_true", help="Print narration word-time and reveal-time alignment")
    parser.add_argument("--style", help="Style name, or auto to rotate deterministically by day")
    parser.add_argument(
        "--allow-scene-style-overrides",
        action="store_true",
        help="Apply theme.scene_styles overrides for individual scenes",
    )
    parser.add_argument("--verbose", action="store_true")


def _style_theme(theme: Theme, requested: str | None, day: int) -> Theme:
    return style_theme(theme, resolve_style(requested or theme.style, day, theme.style_allowlist).name)


@dataclass(frozen=True)
class _BenchChunkRenderer:
    example: Path
    style_name: str
    frame_count: int

    def __call__(self, chunk: FrameChunk) -> list[tuple[float, int]]:
        spec = _load_render_spec(self.example)
        theme = _style_theme(load_theme(), self.style_name, spec.question_input.day)
        plan = plan_scenes(spec, theme)
        started = time.perf_counter()
        for index in range(chunk.start, chunk.stop):
            item = plan[index % len(plan)]
            local_frame = index % max(1, round(item.duration_s * theme.canvas.fps))
            item.render_frame(local_frame / theme.canvas.fps, theme)
        return [(time.perf_counter() - started, chunk.stop - chunk.start)]


_TIER_RENDER_BUDGET_S = {1: 120.0, 2: 165.0, 3: 210.0}


def _benchmark_style(example: Path, style_name: str, frame_count: int, workers: int) -> dict[str, object]:
    spec = _load_render_spec(example)
    base_theme = load_theme()
    style_pack = resolve_style(style_name, spec.question_input.day, base_theme.style_allowlist)
    theme = style_theme(base_theme, style_pack.name)
    plan = plan_scenes(spec, theme)
    started = time.perf_counter()
    if workers == 1:
        for index in range(frame_count):
            item = plan[index % len(plan)]
            local_frame = index % max(1, round(item.duration_s * theme.canvas.fps))
            item.render_frame(local_frame / theme.canvas.fps, theme)
        elapsed = time.perf_counter() - started
        ms_per_frame = elapsed * 1000 / frame_count
    else:
        renderer = _BenchChunkRenderer(example, style_pack.name, frame_count)
        chunk_size = ceil(frame_count / workers)
        chunk_times = list(render_ordered(
            frame_count,
            renderer,
            workers=workers,
            chunk_size=chunk_size,
        ))
        elapsed = time.perf_counter() - started
        ms_per_frame = max(duration / count for duration, count in chunk_times) * 1000
    projected_60_s = ms_per_frame * 60 * theme.canvas.fps / 1000
    budget_s = _TIER_RENDER_BUDGET_S[style_pack.tier]
    return {
        "style": style_pack.name,
        "tier": style_pack.tier,
        "workers": workers,
        "frames": frame_count,
        "ms_per_frame": round(ms_per_frame, 2),
        "estimated_render_s": round(ms_per_frame * sum(round(item.duration_s * theme.canvas.fps) for item in plan) / 1000, 2),
        "projected_60_s": round(projected_60_s, 2),
        "budget_s": budget_s,
        "benchmark_wall_s": round(elapsed, 2),
        "status": (
            "COMPARE"
            if workers == 2
            else "PASS" if projected_60_s <= budget_s else "FAIL"
        ),
    }


def _print_bench_table(rows: list[dict[str, object]]) -> None:
    print("| style | tier | workers | ms_per_frame | 60s render estimate | tier budget | status |")
    print("|---|---:|---:|---:|---:|---:|---|")
    for row in rows:
        print(
            f"| {row['style']} | {row['tier']} | {row['workers']} | {row['ms_per_frame']} | "
            f"{row['projected_60_s']} s | {row['budget_s']} s | {row['status']} |"
        )


def _bench(example: Path, style_name: str, frame_count: int, workers: int = 1) -> int:
    if frame_count <= 0:
        print("bench --frames must be positive", file=sys.stderr)
        return 2
    if workers not in (1, 2):
        print("bench --workers must be 1 or 2", file=sys.stderr)
        return 2
    try:
        base_theme = load_theme()
        names = (
            _enabled_styles(base_theme)
            if style_name.strip().lower() == "all"
            else [style_name]
        )
        if not names:
            raise ValueError("bench has no enabled styles to measure")
        if style_name.strip().lower() != "all" and style_name not in _enabled_styles(base_theme):
            raise ValueError(f"Style {style_name!r} is excluded by themes/default.json style_allowlist")
        rows = [_benchmark_style(example, name, frame_count, workers) for name in names]
        _print_bench_table(rows)
        return 5 if any(row["status"] == "FAIL" for row in rows) else 0
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        print(f"bench failed: {exc}", file=sys.stderr)
        return 2


def _frames_for_duration(
    plan: tuple[PlannedScene, ...],
    theme: Theme,
    duration_s: float,
) -> Iterator[Image.Image]:
    frame_count = round(duration_s * theme.canvas.fps)
    scene_starts = []
    cursor = 0.0
    for item in plan:
        scene_starts.append(cursor)
        cursor += item.duration_s
    for frame_index in range(frame_count):
        time_s = frame_index / theme.canvas.fps
        scene_index = max(index for index, start in enumerate(scene_starts) if start <= time_s)
        item = plan[scene_index]
        yield item.render_frame(time_s - scene_starts[scene_index], theme)


def _write_gallery_reel(
    example: Path,
    styles: list[str],
    output_dir: Path,
    clip_duration_s: float = 2.0,
) -> dict[str, int]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise EncodeError("ffmpeg is required to make the style reel.")
    base_theme = load_theme()
    spec = _load_render_spec(example)
    segment_dir = output_dir / "clips"
    segment_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / ".style-reel-silence.wav"
    playlist_path = output_dir / ".style-reel-concat.txt"
    write_wav(audio_path, AudioMixer(44_100, clip_duration_s, 0).mix())
    segment_paths = []
    sizes: dict[str, int] = {}
    try:
        for name in styles:
            theme = _style_theme(base_theme, name, spec.question_input.day)
            plan = plan_scenes(spec, theme)
            target = segment_dir / f"{name}.mp4"
            encode_frames(
                _frames_for_duration(plan, theme, clip_duration_s),
                theme.canvas.width,
                theme.canvas.height,
                theme.canvas.fps,
                audio_path,
                target,
                clip_duration_s,
            )
            validate_output(target)
            segment_paths.append(target)
            sizes[name] = target.stat().st_size
        playlist_path.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_paths),
            encoding="utf-8",
        )
        reel_path = output_dir / "style-reel.mp4"
        subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(playlist_path),
             "-c", "copy", "-movflags", "+faststart", str(reel_path)],
            check=True,
            capture_output=True,
        )
        validate_output(reel_path)
        print(f"Wrote {reel_path} ({reel_path.stat().st_size} bytes)")
        return sizes
    finally:
        audio_path.unlink(missing_ok=True)
        playlist_path.unlink(missing_ok=True)


def _gallery(example: Path, styles: str, output_dir: Path) -> int:
    try:
        spec = _load_render_spec(example)
        base_theme = load_theme()
        requested = (
            _enabled_styles(base_theme)
            if styles.strip().lower() == "all"
            else [part.strip() for part in styles.split(",") if part.strip()]
        )
        if not requested:
            raise ValueError("gallery needs at least one enabled style")
        excluded = set(requested) - set(_enabled_styles(base_theme))
        if excluded:
            raise ValueError(f"Styles excluded by themes/default.json style_allowlist: {', '.join(sorted(excluded))}")
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for style_name in requested:
            theme = _style_theme(base_theme, style_name, spec.question_input.day)
            plan = plan_scenes(spec, theme)
            total_duration = sum(item.duration_s for item in plan)
            frames = []
            for index in range(6):
                sample_time = total_duration * (index + 0.5) / 6
                scene_start = 0.0
                for item in plan:
                    if sample_time < scene_start + item.duration_s:
                        frames.append((sample_time, item.render_frame(sample_time - scene_start, theme)))
                        break
                    scene_start += item.duration_s
            thumb_width, thumb_height = 180, 320
            sheet = Image.new("RGB", (thumb_width * 3, (thumb_height + 28) * 2), (8, 8, 16))
            draw = ImageDraw.Draw(sheet)
            for index, (sample_time, frame) in enumerate(frames):
                x, y = (index % 3) * thumb_width, (index // 3) * (thumb_height + 28)
                sheet.paste(frame.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS), (x, y))
                draw.text((x + 5, y + thumb_height + 5), f"{sample_time:.1f}s", fill=(255, 255, 255))
            sheet.save(output_dir / f"{example.stem}-{theme.style}.png")
            rows.append(_benchmark_style(example, theme.style, 60, 1))
            print(f"Wrote {output_dir / f'{example.stem}-{theme.style}.png'}")
        preview_sizes = _write_gallery_reel(example, [str(row["style"]) for row in rows], output_dir)
        for row in rows:
            row["preview_mp4_bytes"] = preview_sizes[str(row["style"])]
        table = [
            f"# Style gallery: {example.name}",
            "",
            "The reel contains a 2-second, no-voice preview per enabled style. Preview size is not a full-video size check.",
            "",
            "| Style | Tier | ms/frame | 60s estimate | Tier budget | Preview MP4 bytes | Budget |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        table.extend(
            f"| {row['style']} | {row['tier']} | {row['ms_per_frame']} | {row['projected_60_s']} s | "
            f"{row['budget_s']} s | {row['preview_mp4_bytes']} | {row['status']} |"
            for row in rows
        )
        (output_dir / "index.md").write_text("\n".join(table) + "\n", encoding="utf-8")
        (output_dir / "bench.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote {output_dir / 'index.md'}")
        return 5 if any(row["status"] == "FAIL" for row in rows) else 0
    except (OSError, ValueError, ValidationError, json.JSONDecodeError, EncodeError, OutputValidationError, subprocess.SubprocessError) as exc:
        print(f"gallery failed: {exc}", file=sys.stderr)
        return 2 if not isinstance(exc, OutputValidationError) else 5


def _seed(value: str) -> int:
    try:
        seed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seed must be an integer") from exc
    if not 0 <= seed <= 2**31 - 1:
        raise argparse.ArgumentTypeError("seed must be between 0 and 2147483647")
    return seed


def _enabled_styles(theme: Theme) -> list[str]:
    allowed = set(theme.style_allowlist)
    return [name for name in registered_styles() if not allowed or name in allowed]


def _load_render_spec(input_path: Path) -> SolutionSpec:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    return SolutionSpec.from_payload(payload)


def _generate_from_today(
    input_path: Path,
    provider_name: str,
    seed: int | None,
    speech_language_mode: str | None = None,
) -> SolutionSpec:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    payload.pop("expected_steps", None)
    question = QuestionInput.model_validate(payload)
    provider = GroqProvider() if provider_name == "groq" else GeminiProvider()
    spec = generate_steps(
        question,
        provider,
        cache_dir=Path("out/.solution-video-cache"),
        speech_language_mode=speech_language_mode,
    )
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


def _print_plan(
    spec: SolutionSpec,
    theme: Theme,
    voice_provider: str | None = None,
    no_voice: bool = False,
    allow_scene_styles: bool = False,
) -> None:
    plan = plan_scenes(spec, theme, allow_scene_styles=allow_scene_styles)
    voice = (
        ("none", "none", 0, 0)
        if no_voice
        else estimate_voice(
            _speech_inputs_for_cli(spec),
            provider_override=voice_provider,
        )
    )
    print(json.dumps({
        "renders": False,
        "estimated_duration_s": round(sum(item.duration_s for item in plan), 2),
        "style": theme.style,
        "scenes": [
            {
                "name": item.name,
                "style": getattr(item.scene, "theme", theme).style,
                "duration_s": round(item.duration_s, 2),
            }
            for item in plan
        ],
        "voice_estimate": {
            "provider": voice[0],
            "model": voice[1],
            "characters": voice[2],
            "estimated_credits": voice[3],
        },
    }, indent=2))


def _speech_inputs_for_cli(spec: SolutionSpec):
    from .pipeline import _speech_inputs

    return _speech_inputs(spec)


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
        value = value.strip().strip("\"'").strip()
        if key in {
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "GROQ_JSON_MODE",
            "GEMINI_API_KEY",
            "SPEECH_LANGUAGE_MODE",
            "STYLE_ALLOW_HEAVY",
            "HF_TOKEN",
            "HF_TTS_SPACE",
            "HF_TTS_REFERENCE_AUDIO",
            "HF_TTS_REQUEST_LIMIT",
            "HF_TTS_REQUEST_PAUSE_S",
            "ELEVENLABS_API_KEY",
            "ELEVENLABS_VOICE_ID",
            "ELEVENLABS_MODEL_ID",
            "ELEVENLABS_RESERVE_CREDITS",
            "VOICE_PROVIDER_ORDER",
            "VOICE_ELEVENLABS_FALLBACK",
            "EDGE_TTS_VOICE",
        } and not os.getenv(key) and value:
            os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
