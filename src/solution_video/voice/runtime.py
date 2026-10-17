"""Provider selection, credit checks, caching, and speech-clip preparation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import requests

from .listening_test import (
    EDGE_VOICES,
    ELEVENLABS_MODELS,
    EdgeTTSProvider,
    ElevenLabsProvider,
    HFSpaceProvider,
    VoiceTestError,
)
from .normalization import normalize_speech


PROVIDER_NAMES = ("hf_space", "edge_tts", "elevenlabs", "none")
DEFAULT_PROVIDER_ORDER = ("hf_space", "edge_tts", "none")
SUBSCRIPTION_URL = "https://api.elevenlabs.io/v1/user/subscription"


class VoiceRuntimeError(ValueError):
    """A voice configuration or audio-processing operation failed."""


class CreditReserveError(VoiceTestError):
    """The requested ElevenLabs call would consume the configured reserve."""


@dataclass(frozen=True)
class VoiceInput:
    name: str
    text: str


@dataclass(frozen=True)
class VoiceClip:
    path: Path
    duration_s: float
    provider: str
    model: str
    characters: int
    credits: int
    text: str
    word_boundaries: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class VoiceRender:
    clips: tuple[VoiceClip | None, ...]
    warnings: tuple[str, ...]
    provider: str
    model: str | None
    characters: int
    credits: int


def provider_order(
    environment: dict[str, str],
    provider_override: str | None = None,
) -> tuple[str, ...]:
    """Resolve the run's provider order, keeping ElevenLabs explicitly opt-in."""
    raw_order = environment.get("VOICE_PROVIDER_ORDER", ",".join(DEFAULT_PROVIDER_ORDER))
    configured = tuple(part.strip() for part in raw_order.split(",") if part.strip())
    if not configured or any(name not in PROVIDER_NAMES for name in configured):
        raise VoiceRuntimeError(
            "VOICE_PROVIDER_ORDER must contain comma-separated provider names from "
            "hf_space,edge_tts,elevenlabs,none"
        )
    if len(set(configured)) != len(configured):
        raise VoiceRuntimeError("VOICE_PROVIDER_ORDER must not contain duplicates")
    if "none" in configured and configured[-1] != "none":
        raise VoiceRuntimeError("The none provider must be last in VOICE_PROVIDER_ORDER")
    elevenlabs_fallback = _env_bool(environment, "VOICE_ELEVENLABS_FALLBACK", default=False)
    if "elevenlabs" in configured:
        raise VoiceRuntimeError(
            "ElevenLabs is selected with --voice-provider elevenlabs, not VOICE_PROVIDER_ORDER"
        )
    if provider_override is None:
        return configured
    if provider_override not in PROVIDER_NAMES:
        raise VoiceRuntimeError(f"Unsupported voice provider: {provider_override}")
    if provider_override == "none":
        return ("none",)
    if provider_override == "elevenlabs":
        return ("elevenlabs", *configured) if elevenlabs_fallback else ("elevenlabs", "none")
    return (provider_override, *(name for name in configured if name != provider_override))


def synthesize_voice(
    inputs: Sequence[VoiceInput],
    *,
    environment: dict[str, str] | None = None,
    provider_override: str | None = None,
    cache_dir: Path = Path("out/.voice-cache"),
    audio_processor: Callable[[Path, Path], float] | None = None,
    credit_session: Any | None = None,
    provider_factory: Callable[[str, dict[str, str], Path], Any] | None = None,
) -> VoiceRender:
    """Synthesize each scene, reusing cache entries and falling through providers."""
    env = dict(os.environ if environment is None else environment)
    order = provider_order(env, provider_override)
    language_mode = env.get("SPEECH_LANGUAGE_MODE", "english").strip().lower() or "english"
    reserve = _nonnegative_int(env.get("ELEVENLABS_RESERVE_CREDITS", "1500"), "ELEVENLABS_RESERVE_CREDITS")
    cache_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    clips: list[VoiceClip | None] = []
    failed_providers: set[str] = set()
    reported_providers: set[str] = set()
    provider_instances: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="solution-video-voice-") as temp_name:
        temp_dir = Path(temp_name)
        for item in inputs:
            if not item.text.strip():
                clips.append(None)
                warnings.append(f"{item.name}: narration text is empty; scene will render without voice")
                continue
            normalized = normalize_speech(item.text, language_mode)
            clip = None
            for provider_name in order:
                if provider_name == "none":
                    break
                if provider_name in failed_providers:
                    continue
                try:
                    clip = _synthesize_one(
                        item,
                        normalized,
                        provider_name,
                        env,
                        reserve,
                        cache_dir,
                        audio_processor,
                        credit_session,
                        provider_factory or _make_provider,
                        provider_instances,
                        temp_dir,
                    )
                    break
                except CreditReserveError as exc:
                    if provider_name not in reported_providers:
                        warnings.append(f"{provider_name} unavailable: {exc}")
                        reported_providers.add(provider_name)
                except (VoiceTestError, VoiceRuntimeError, OSError, subprocess.SubprocessError) as exc:
                    failed_providers.add(provider_name)
                    if provider_name not in reported_providers:
                        warnings.append(f"{provider_name} unavailable: {exc}")
                        reported_providers.add(provider_name)
            clips.append(clip)
            if clip is None:
                warnings.append(f"{item.name}: narration unavailable; scene will render without voice")

    used = [clip for clip in clips if clip is not None]
    providers = sorted({clip.provider for clip in used})
    models = sorted({clip.model for clip in used})
    return VoiceRender(
        clips=tuple(clips),
        warnings=tuple(warnings),
        provider=providers[0] if len(providers) == 1 else "mixed" if providers else "none",
        model=models[0] if len(models) == 1 else ", ".join(models) if models else None,
        characters=sum(clip.characters for clip in used),
        credits=sum(clip.credits for clip in used),
    )


def _synthesize_one(
    item: VoiceInput,
    text: str,
    provider_name: str,
    environment: dict[str, str],
    reserve: int,
    cache_dir: Path,
    audio_processor: Callable[[Path, Path], float] | None,
    credit_session: Any | None,
    provider_factory: Callable[[str, dict[str, str], Path], Any],
    provider_instances: dict[str, Any],
    temp_dir: Path,
) -> VoiceClip:
    model, voice = _provider_identity(provider_name, environment)
    key_data = {
        "text": text,
        "provider": provider_name,
        "voice": voice,
        "model": model,
        "language_mode": environment.get("SPEECH_LANGUAGE_MODE", "english").strip().lower(),
        "edge_rate": _edge_rate(environment) if provider_name == "edge_tts" else None,
        "timing_format": 1,
    }
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    cached = cache_dir / f"{key}.wav"
    cached_timing = cache_dir / f"{key}.word-boundaries.json"
    characters = len(text)
    if cached.is_file():
        return VoiceClip(
            cached,
            probe_audio_duration(cached),
            provider_name,
            model,
            characters,
            0,
            text,
            _load_word_boundaries(cached_timing),
        )

    if provider_name == "elevenlabs":
        api_key = environment.get("ELEVENLABS_API_KEY", "").strip()
        needed = characters
        remaining = get_elevenlabs_remaining_characters(api_key, session=credit_session)
        if remaining - needed < reserve:
            raise CreditReserveError(
                f"ElevenLabs credit reserve would be crossed "
                f"(remaining {remaining}, needed {needed}, reserve {reserve})"
            )

    provider = provider_instances.get(provider_name)
    if provider is None:
        provider = provider_factory(provider_name, environment, temp_dir)
        provider_instances[provider_name] = provider
    word_boundaries: tuple[tuple[str, float], ...] = ()
    raw_duration = 0.0
    synthesize_with_boundaries = getattr(provider, "synthesize_with_word_boundaries", None)
    if provider_name == "edge_tts" and callable(synthesize_with_boundaries):
        raw_path, word_boundaries = synthesize_with_boundaries(text)
        raw_duration = probe_audio_duration(raw_path)
    else:
        raw_path = provider.synthesize(text)
    output_path = temp_dir / f"{key}.normalized.wav"
    if audio_processor is not None:
        duration = audio_processor(raw_path, output_path)
    elif provider_name == "edge_tts" and word_boundaries:
        duration = normalize_audio_file(raw_path, output_path, preserve_leading_silence=True)
    else:
        duration = normalize_audio_file(raw_path, output_path)
    if duration <= 0:
        raise VoiceRuntimeError(f"{provider_name} returned an empty audio clip")
    if raw_duration > 0:
        word_boundaries = tuple(
            (word, min(duration, max(0.0, offset * duration / raw_duration)))
            for word, offset in word_boundaries
        )
    cached_temp = cache_dir / f".{key}.tmp.wav"
    shutil.copyfile(output_path, cached_temp)
    cached_temp.replace(cached)
    if word_boundaries:
        timing_temp = cache_dir / f".{key}.word-boundaries.tmp.json"
        timing_temp.write_text(
            json.dumps(
                [{"text": word, "offset_s": offset} for word, offset in word_boundaries],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        timing_temp.replace(cached_timing)
    else:
        cached_timing.unlink(missing_ok=True)
    return VoiceClip(
        cached,
        duration,
        provider_name,
        model,
        characters,
        characters if provider_name == "elevenlabs" else 0,
        text,
        word_boundaries,
    )


def _provider_identity(provider_name: str, environment: dict[str, str]) -> tuple[str, str]:
    if provider_name == "hf_space":
        space_id = environment.get("HF_TTS_SPACE", "").strip()
        if not space_id:
            raise VoiceTestError("set HF_TTS_SPACE")
        return space_id.rsplit("/", 1)[-1], space_id
    if provider_name == "edge_tts":
        voice = environment.get("EDGE_TTS_VOICE", "en-IN-NeerjaNeural").strip()
        if not voice:
            raise VoiceTestError("EDGE_TTS_VOICE must not be empty")
        return voice, voice
    if provider_name == "elevenlabs":
        voice_id = environment.get("ELEVENLABS_VOICE_ID", "").strip()
        if not voice_id:
            raise VoiceTestError("ELEVENLABS_VOICE_ID is not configured")
        model = environment.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()
        if model not in ELEVENLABS_MODELS:
            raise VoiceTestError(f"Unsupported ELEVENLABS_MODEL_ID: {model}")
        return model, voice_id
    raise VoiceTestError(f"Unsupported voice provider: {provider_name}")


def _make_provider(provider_name: str, environment: dict[str, str], temp_dir: Path):
    if provider_name == "hf_space":
        if not environment.get("HF_TOKEN", "").strip():
            raise VoiceTestError("HF_TOKEN is not configured")
        reference = Path(
            environment.get("HF_TTS_REFERENCE_AUDIO", "local_assets/ref_voice.wav")
        ).expanduser()
        if not reference.is_absolute():
            reference = Path.cwd() / reference
        reference = reference.resolve()
        request_limit_value = environment.get("HF_TTS_REQUEST_LIMIT", "").strip()
        request_limit = (
            _nonnegative_int(request_limit_value, "HF_TTS_REQUEST_LIMIT")
            if request_limit_value
            else None
        )
        if request_limit == 0:
            raise VoiceRuntimeError("HF_TTS_REQUEST_LIMIT must be at least 1")
        try:
            request_pause_s = float(environment.get("HF_TTS_REQUEST_PAUSE_S", "0"))
        except ValueError as exc:
            raise VoiceRuntimeError("HF_TTS_REQUEST_PAUSE_S must be a non-negative number") from exc
        if not math.isfinite(request_pause_s) or request_pause_s < 0:
            raise VoiceRuntimeError("HF_TTS_REQUEST_PAUSE_S must be a non-negative number")
        return HFSpaceProvider(
            environment["HF_TTS_SPACE"].strip(),
            environment["HF_TOKEN"].strip(),
            reference,
            request_limit=request_limit,
            request_pause_s=request_pause_s,
        )
    if provider_name == "edge_tts":
        voice = environment.get("EDGE_TTS_VOICE", EDGE_VOICES[-1]).strip()
        return EdgeTTSProvider(voice, temp_dir, rate=_edge_rate(environment))
    if provider_name == "elevenlabs":
        if not environment.get("ELEVENLABS_API_KEY", "").strip():
            raise VoiceTestError("ELEVENLABS_API_KEY is not configured")
        if not environment.get("ELEVENLABS_VOICE_ID", "").strip():
            raise VoiceTestError("ELEVENLABS_VOICE_ID is not configured")
        return ElevenLabsProvider(
            environment["ELEVENLABS_API_KEY"].strip(),
            environment["ELEVENLABS_VOICE_ID"].strip(),
            environment.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip(),
            temp_dir,
        )
    raise VoiceTestError(f"Unsupported voice provider: {provider_name}")


def _edge_rate(environment: dict[str, str]) -> str:
    rate = environment.get("EDGE_TTS_RATE", "-8%").strip()
    match = re.fullmatch(r"([+-])(\d{1,3})%", rate)
    if match is None or int(match.group(2)) > 100:
        raise VoiceRuntimeError("EDGE_TTS_RATE must be a percentage from -100% to +100%")
    return rate


def _load_word_boundaries(path: Path) -> tuple[tuple[str, float], ...]:
    if not path.is_file():
        return ()
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VoiceRuntimeError(f"Cached word-boundary data is invalid: {path.name}") from exc
    if not isinstance(entries, list):
        raise VoiceRuntimeError(f"Cached word-boundary data is invalid: {path.name}")
    result = []
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("text"), str)
            or isinstance(entry.get("offset_s"), bool)
            or not isinstance(entry.get("offset_s"), (int, float))
            or entry["offset_s"] < 0
        ):
            raise VoiceRuntimeError(f"Cached word-boundary data is invalid: {path.name}")
        result.append((entry["text"], float(entry["offset_s"])))
    return tuple(result)


def get_elevenlabs_remaining_characters(api_key: str, *, session: Any | None = None) -> int:
    """Read documented subscription usage and fail closed on incomplete responses."""
    if not api_key:
        raise VoiceTestError("ELEVENLABS_API_KEY is not configured")
    client = session or requests.Session()
    try:
        response = client.get(
            SUBSCRIPTION_URL,
            headers={"xi-api-key": api_key},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        message = str(exc).replace(api_key, "[REDACTED]")
        raise VoiceTestError(f"Unable to check ElevenLabs remaining credits: {message}") from exc
    if not isinstance(payload, dict):
        raise VoiceTestError("ElevenLabs subscription response is not a JSON object")
    count, limit = payload.get("character_count"), payload.get("character_limit")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not isinstance(limit, int)
        or isinstance(limit, bool)
        or count < 0
        or limit < count
    ):
        raise VoiceTestError("ElevenLabs subscription response has invalid character usage fields")
    return limit - count


def normalize_audio_file(
    source: Path,
    destination: Path,
    *,
    preserve_leading_silence: bool = False,
) -> float:
    """Trim silence, normalize loudness, and return probed duration."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VoiceRuntimeError("ffmpeg is required to normalize voice audio but was not found on PATH")
    silence_filter = (
        "silenceremove=stop_periods=1:stop_duration=0.08:stop_threshold=-45dB"
        if preserve_leading_silence
        else "silenceremove=start_periods=1:start_duration=0.04:start_threshold=-45dB:"
        "stop_periods=1:stop_duration=0.08:stop_threshold=-45dB"
    )
    command = [
        ffmpeg, "-y", "-v", "error", "-i", str(source),
        "-af", silence_filter + ",loudnorm=I=-18:TP=-1.5:LRA=11",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceRuntimeError(f"Unable to process synthesized voice audio: {exc}") from exc
    return probe_audio_duration(destination)


def probe_audio_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise VoiceRuntimeError("ffprobe is required to measure voice clips but was not found on PATH")
    command = [
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        duration = float(result.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise VoiceRuntimeError(f"Unable to measure voice audio {path.name}: {exc}") from exc
    if duration <= 0:
        raise VoiceRuntimeError(f"Voice audio {path.name} has no positive duration")
    return duration


def speed_up_audio(path: Path, factor: float) -> tuple[Path, float]:
    """Apply a small pitch-preserving atempo adjustment and return its duration."""
    if not 1.0 <= factor <= 1.12:
        raise VoiceRuntimeError("Voice speed-up factor must be between 1.0 and 1.12")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VoiceRuntimeError("ffmpeg is required to shorten voice audio but was not found on PATH")
    destination = path.with_name(f"{path.stem}.atempo-{factor:.4f}.wav")
    try:
        subprocess.run(
            [
                ffmpeg, "-y", "-v", "error", "-i", str(path),
                "-af", f"atempo={factor:.6f}", "-ar", "44100", "-ac", "1",
                "-c:a", "pcm_s16le", str(destination),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        return destination, probe_audio_duration(destination)
    except (OSError, subprocess.SubprocessError) as exc:
        destination.unlink(missing_ok=True)
        raise VoiceRuntimeError(f"Unable to shorten voice audio: {exc}") from exc


def _nonnegative_int(value: str, name: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise VoiceRuntimeError(f"{name} must be a non-negative integer") from exc
    if result < 0:
        raise VoiceRuntimeError(f"{name} must be a non-negative integer")
    return result


def _env_bool(environment: dict[str, str], name: str, *, default: bool) -> bool:
    value = environment.get(name)
    if value is None:
        return default
    if value.strip() not in {"0", "1"}:
        raise VoiceRuntimeError(f"{name} must be 0 or 1")
    return value.strip() == "1"


def estimate_voice(
    inputs: Sequence[VoiceInput],
    *,
    environment: dict[str, str] | None = None,
    provider_override: str | None = None,
) -> tuple[str, str, int, int]:
    """Return a provider/model/character/credit estimate without network access."""
    env = dict(os.environ if environment is None else environment)
    order = provider_order(env, provider_override)
    provider = next((name for name in order if name != "none"), "none")
    mode = env.get("SPEECH_LANGUAGE_MODE", "english").strip().lower() or "english"
    characters = sum(len(normalize_speech(item.text, mode)) for item in inputs)
    if provider == "elevenlabs":
        model = env.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()
        credits = characters
    elif provider == "edge_tts":
        model = env.get("EDGE_TTS_VOICE", "en-IN-NeerjaNeural").strip()
        credits = 0
    elif provider == "hf_space":
        model = env.get("HF_TTS_SPACE", "configured HF Space").strip() or "configured HF Space"
        credits = 0
    else:
        model, credits = "none", 0
    return provider, model, characters, credits
