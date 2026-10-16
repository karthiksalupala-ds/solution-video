"""Provider adapters and guarded orchestration for the Phase 5 voice test."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import quote

import requests


VARIANT_NAMES = ("english", "tanglish_latin", "telugu_script", "telugu_english")
EDGE_VOICES = ("te-IN-ShrutiNeural", "te-IN-MohanNeural", "en-IN-NeerjaNeural")
ELEVENLABS_MODELS = ("eleven_v3", "eleven_multilingual_v2")
ELEVENLABS_CREDITS_PER_CHARACTER = 1
ELEVENLABS_TEST_CREDIT_LIMIT = 1500
HF_API_NAME = "/generate_tts_audio"
HF_API_PARAMETERS = (
    "text_input",
    "audio_prompt_path_input",
    "exaggeration_input",
    "temperature_input",
    "seed_num_input",
    "cfgw_input",
    "vad_trim_input",
)


class VoiceTestError(RuntimeError):
    """A provider or listening-test configuration failed explicitly."""


@dataclass(frozen=True)
class TextVariant:
    n: int
    step: int
    source_text: str
    variant: str
    text: str


class VoiceProvider(Protocol):
    provider: str
    model: str

    def synthesize(self, text: str) -> Path:
        """Synthesize text and return the resulting audio file."""


def load_text_variants(variants_path: Path, source_path: Path) -> list[TextVariant]:
    """Load approved translations and verify each source sentence exists in its step."""
    try:
        variants = json.loads(variants_path.read_text(encoding="utf-8"))
        source = json.loads(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VoiceTestError(f"Unable to read voice-test input: {exc.filename}") from exc
    except json.JSONDecodeError as exc:
        raise VoiceTestError(f"Invalid voice-test JSON: {exc.msg}") from exc

    steps = source.get("expected_steps", {}).get("steps")
    if not isinstance(steps, list):
        raise VoiceTestError("The source example must contain expected_steps.steps")

    result: list[TextVariant] = []
    for sample in variants.get("samples", []):
        step_number = sample.get("step")
        if not isinstance(step_number, int) or not 1 <= step_number <= len(steps):
            raise VoiceTestError(f"Voice-test sample {sample.get('n')} has an invalid step number")
        source_text = sample.get("source_text")
        step_speech = steps[step_number - 1].get("speech", "")
        if not isinstance(source_text, str) or source_text not in step_speech:
            raise VoiceTestError(
                f"Voice-test source sentence does not occur in source step {step_number}"
            )
        sample_variants = sample.get("variants", {})
        if set(sample_variants) != set(VARIANT_NAMES):
            raise VoiceTestError(f"Voice-test sample {sample.get('n')} must define all four variants")
        for variant_name in VARIANT_NAMES:
            text = sample_variants[variant_name]
            if not isinstance(text, str) or not text.strip():
                raise VoiceTestError(f"Voice-test sample {sample.get('n')} has an empty {variant_name} variant")
            result.append(TextVariant(sample["n"], step_number, source_text, variant_name, text))

    if len(result) != 12:
        raise VoiceTestError(f"Expected exactly 12 approved text variants; found {len(result)}")
    return result


def character_count(variants: list[TextVariant]) -> int:
    """Count Unicode code points sent as text to a provider."""
    return sum(len(item.text) for item in variants)


def print_estimates(variants: list[TextVariant], printer: Callable[[str], None] = print) -> int:
    """Print expected characters and ElevenLabs credit estimates before synthesis."""
    characters = character_count(variants)
    printer("Provider | Model/voice | Characters | Estimated credits")
    printer(f"hf_space | configured private Space | {characters} | not applicable")
    for voice in EDGE_VOICES:
        printer(f"edge_tts | {voice} | {characters} | 0 (no ElevenLabs credits)")
    for model in ELEVENLABS_MODELS:
        credits = characters * ELEVENLABS_CREDITS_PER_CHARACTER
        printer(f"elevenlabs | {model} | {characters} | {credits}")
    printer(
        "ElevenLabs total estimate: "
        f"{characters * len(ELEVENLABS_MODELS)} credits "
        f"(limit {ELEVENLABS_TEST_CREDIT_LIMIT})."
    )
    return characters * len(ELEVENLABS_MODELS)


def format_variants(variants: list[TextVariant], printer: Callable[[str], None] = print) -> None:
    """Print the approved test sentences for human review."""
    for item in variants:
        printer(f"{item.n}.{item.variant}: {item.text}")


def _temporary_audio(directory: Path, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix="voice-test-", suffix=suffix, dir=directory)
    os.close(fd)
    return Path(filename)


class EdgeTTSProvider:
    """Adapter for one Microsoft Edge neural voice."""

    provider = "edge_tts"

    def __init__(
        self,
        voice: str,
        temp_dir: Path,
        communicate_factory: Callable[..., Any] | None = None,
    ) -> None:
        if communicate_factory is None:
            try:
                import edge_tts
            except ImportError as exc:
                raise VoiceTestError("Install the optional voice dependencies to use edge-tts") from exc
            communicate_factory = edge_tts.Communicate
        self.model = voice
        self.temp_dir = temp_dir
        self.communicate_factory = communicate_factory

    def synthesize(self, text: str) -> Path:
        output = _temporary_audio(self.temp_dir, ".mp3")

        async def save() -> None:
            await self.communicate_factory(text, self.model).save(str(output))

        try:
            asyncio.run(save())
        except Exception as exc:
            output.unlink(missing_ok=True)
            raise VoiceTestError(f"edge-tts {self.model} synthesis failed: {exc}") from exc
        return output


class HFSpaceProvider:
    """Adapter for the inspected private Space endpoint and its own-voice prompt."""

    provider = "hf_space"

    def __init__(
        self,
        space_id: str,
        token: str,
        reference_audio: Path,
        client_factory: Callable[..., Any] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not reference_audio.is_file():
            raise VoiceTestError(f"HF reference audio is missing: {reference_audio}")
        if client_factory is None:
            try:
                from gradio_client import Client
            except ImportError as exc:
                raise VoiceTestError("Install the optional voice dependencies to use the HF Space") from exc
            client_factory = Client

        self.model = space_id.rsplit("/", 1)[-1]
        self.reference_audio = reference_audio
        self.sleep_fn = sleep_fn
        try:
            self.client = client_factory(
                space_id,
                token=token,
                verbose=False,
                httpx_kwargs={"timeout": 600},
            )
            api_description = self.client.view_api(print_info=False, return_format="str")
        except Exception as exc:
            raise VoiceTestError(f"Unable to inspect HF Space API: {_redact(str(exc), token)}") from exc
        if not isinstance(api_description, str) or HF_API_NAME not in api_description:
            raise VoiceTestError(f"HF Space API no longer exposes the inspected endpoint {HF_API_NAME}")
        missing = [name for name in HF_API_PARAMETERS if name not in api_description]
        if missing:
            raise VoiceTestError("HF Space API parameters changed; missing: " + ", ".join(missing))

    def synthesize(self, text: str) -> Path:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                result = self.client.predict(
                    text,
                    str(self.reference_audio),
                    0.5,
                    0.8,
                    0,
                    0.5,
                    False,
                    api_name=HF_API_NAME,
                )
                audio_path = _gradio_output_path(result)
                if not audio_path.is_file():
                    raise VoiceTestError("HF Space returned an audio path that does not exist")
                return audio_path
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    self.sleep_fn(5)
        assert last_error is not None
        token = getattr(self.client, "token", "")
        raise VoiceTestError(
            f"HF Space synthesis failed after one retry: {_redact(str(last_error), token)}"
        ) from last_error


class ElevenLabsProvider:
    """Official ElevenLabs REST adapter for stock voices and MP3 synthesis."""

    provider = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model: str,
        temp_dir: Path,
        session: Any | None = None,
    ) -> None:
        if model not in ELEVENLABS_MODELS:
            raise VoiceTestError(f"Unsupported ElevenLabs comparison model: {model}")
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.temp_dir = temp_dir
        self.session = session or requests.Session()

    def synthesize(self, text: str) -> Path:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{quote(self.voice_id, safe='')}"
        try:
            response = self.session.post(
                url,
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": self.api_key},
                json={"text": text, "model_id": self.model},
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VoiceTestError(f"ElevenLabs synthesis failed: {_redact(str(exc), self.api_key)}") from exc
        output = _temporary_audio(self.temp_dir, ".mp3")
        output.write_bytes(response.content)
        return output


def list_elevenlabs_stock_voices(api_key: str, session: Any | None = None) -> list[dict[str, Any]]:
    """List the account's premade voices using the documented voices endpoint."""
    client = session or requests.Session()
    url = "https://api.elevenlabs.io/v2/voices"
    params: dict[str, Any] = {"category": "premade", "page_size": 100}
    voices: list[dict[str, Any]] = []
    while True:
        try:
            response = client.get(
                url,
                params=params,
                headers={"xi-api-key": api_key},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise VoiceTestError(f"Unable to list ElevenLabs stock voices: {_redact(str(exc), api_key)}") from exc
        voices.extend(payload.get("voices", []))
        if not payload.get("has_more"):
            return voices
        next_page = payload.get("next_page_token")
        if not next_page:
            raise VoiceTestError("ElevenLabs voice list reports another page without a page token")
        params["next_page_token"] = next_page


def run_listening_test(
    variants: list[TextVariant],
    output_dir: Path,
    selected_providers: set[str],
    *,
    synthesize: bool,
    text_approved: bool,
    elevenlabs_voice_id: str | None = None,
    approved_elevenlabs_credits: int | None = None,
    environment: dict[str, str] | None = None,
    printer: Callable[[str], None] = print,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    """Run selected provider tests, emit an index, and gate ElevenLabs spend."""
    env = os.environ if environment is None else environment
    total_elevenlabs_credits = print_estimates(variants, printer)
    format_variants(variants, printer)
    if not synthesize:
        printer("Preview only; no provider/API calls made. Use --synthesize to run.")
        return 0
    if not text_approved:
        printer("No synthesis started: pass --approve-texts after reviewing the variants.")
        return 0
    if total_elevenlabs_credits > ELEVENLABS_TEST_CREDIT_LIMIT:
        raise VoiceTestError(
            f"ElevenLabs estimate {total_elevenlabs_credits} exceeds the "
            f"{ELEVENLABS_TEST_CREDIT_LIMIT}-credit test limit"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        row for row in _read_index_rows(output_dir)
        if row["provider"] not in selected_providers
        and (output_dir / str(row["file"])).is_file()
    ]
    generated_count = 0
    spent_credits = 0
    skipped: list[str] = []
    failures: list[str] = []
    selected_voice_name = _read_index_voice(output_dir)
    api_key = env.get("ELEVENLABS_API_KEY", "").strip()
    hf_token = env.get("HF_TOKEN", "").strip()
    space_id = env.get("HF_TTS_SPACE", "").strip()
    reference_audio = Path(env.get("HF_TTS_REFERENCE_AUDIO", "local_assets/ref_voice.wav").strip())
    if not reference_audio.is_absolute():
        reference_audio = Path.cwd() / reference_audio

    def generate(provider: VoiceProvider, item: TextVariant, credits: int | str) -> None:
        nonlocal generated_count, spent_credits
        audio: Path | None = None
        try:
            audio = provider.synthesize(item.text)
            if provider.provider == "elevenlabs" and isinstance(credits, int):
                spent_credits += credits
            if audio.suffix.lower() not in {".wav", ".mp3"}:
                raise VoiceTestError(f"Provider returned unsupported audio format: {audio.suffix}")
            filename = (
                f"{provider.provider}__{_safe_filename(provider.model)}__"
                f"{item.variant}_{item.n}{audio.suffix.lower()}"
            )
            destination = output_dir / filename
            shutil.copyfile(audio, destination)
            rows.append({
                "file": filename,
                "provider": provider.provider,
                "model": provider.model,
                "variant": item.variant,
                "chars": len(item.text),
                "credits": credits,
            })
            generated_count += 1
            printer(f"Wrote {destination}")
        except Exception as exc:
            message = _redact(str(exc), api_key, hf_token)
            failures.append(f"{provider.provider}/{provider.model}/{item.variant}_{item.n}: {message}")
            printer(f"Failed {provider.provider}/{provider.model}/{item.variant}_{item.n}: {message}")
        finally:
            if audio is not None and audio.is_file():
                audio.unlink(missing_ok=True)

    if "hf_space" in selected_providers:
        if not space_id or not hf_token:
            skipped.append("hf_space: set HF_TTS_SPACE and HF_TOKEN")
        elif not reference_audio.is_file():
            skipped.append(
                "hf_space: own reference audio is missing "
                "(HF_TTS_REFERENCE_AUDIO; default local_assets/ref_voice.wav)"
            )
        else:
            try:
                provider = HFSpaceProvider(space_id, hf_token, reference_audio)
            except VoiceTestError as exc:
                failures.append(str(exc))
            else:
                for item in variants:
                    generate(provider, item, "n/a")
                    sleep_fn(0.25)

    if "edge_tts" in selected_providers:
        try:
            providers = [EdgeTTSProvider(voice, Path(tempfile.gettempdir())) for voice in EDGE_VOICES]
        except VoiceTestError as exc:
            skipped.append(f"edge_tts: {exc}")
        else:
            for provider in providers:
                for item in variants:
                    generate(provider, item, "n/a")
                    sleep_fn(0.25)

    if "elevenlabs" in selected_providers:
        if not api_key:
            skipped.append("elevenlabs: ELEVENLABS_API_KEY is not configured")
        else:
            try:
                voices = list_elevenlabs_stock_voices(api_key)
            except VoiceTestError as exc:
                failures.append(str(exc))
            else:
                printer("ElevenLabs stock voices available to this account:")
                for voice in voices:
                    printer(f"- {voice.get('name', '(unnamed)')} | {voice.get('voice_id', '')}")
                if not elevenlabs_voice_id:
                    skipped.append("elevenlabs: choose a listed --elevenlabs-voice-id before synthesis")
                elif not any(voice.get("voice_id") == elevenlabs_voice_id for voice in voices):
                    failures.append("ElevenLabs voice ID is not in the account's listed premade voices")
                else:
                    selected_voice_name = next(
                        str(voice.get("name", "")) for voice in voices
                        if voice.get("voice_id") == elevenlabs_voice_id
                    )
                    if approved_elevenlabs_credits is None:
                        skipped.append(
                            "elevenlabs: synthesis not approved; rerun with "
                            f"--approve-elevenlabs-credits {total_elevenlabs_credits}"
                        )
                    elif approved_elevenlabs_credits < total_elevenlabs_credits:
                        skipped.append(
                            f"elevenlabs: approval covers {approved_elevenlabs_credits} credits, "
                            f"but estimate is {total_elevenlabs_credits}"
                        )
                    else:
                        for model in ELEVENLABS_MODELS:
                            provider = ElevenLabsProvider(
                                api_key,
                                elevenlabs_voice_id,
                                model,
                                Path(tempfile.gettempdir()),
                            )
                            for item in variants:
                                generate(
                                    provider,
                                    item,
                                    len(item.text) * ELEVENLABS_CREDITS_PER_CHARACTER,
                                )
                                sleep_fn(0.25)

    for message in skipped:
        printer(f"Skipped: {message}")
    _write_index(
        output_dir, rows, skipped, failures, total_elevenlabs_credits, selected_voice_name
    )
    printer(f"ElevenLabs estimated credits used this run: {spent_credits}")
    printer(f"Audio files generated this run: {generated_count}")
    return 4 if failures else 0


def _write_index(
    output_dir: Path,
    rows: list[dict[str, str | int]],
    skipped: list[str],
    failures: list[str],
    estimated_elevenlabs_credits: int,
    selected_voice_name: str | None,
) -> None:
    lines = [
        "# Voice listening test",
        "",
        f"Estimated ElevenLabs total if both models run: {estimated_elevenlabs_credits} credits.",
        "Free-tier samples are for non-commercial evaluation; only premade voices were used, with no cloning.",
        "This comparison tested v2 and v3; current Eleven v4 documentation lists Telugu support. Telugu was not tested in this run.",
        "Flash v2.5 was excluded: its documented language list adds Hungarian, Norwegian, and Vietnamese to multilingual v2, not Telugu.",
    ]
    if selected_voice_name:
        lines.append(f"Selected ElevenLabs stock voice: {selected_voice_name}.")
    lines.extend((
        "",
        "| File | Provider | Model | Variant | Chars | Credits |",
        "|---|---|---|---|---:|---:|",
    ))
    for row in rows:
        lines.append(
            f"| `{row['file']}` | {row['provider']} | {row['model']} | "
            f"{row['variant']} | {row['chars']} | {row['credits']} |"
        )
    if skipped:
        lines.extend(("", "## Skipped", ""))
        lines.extend(f"- {item}" for item in skipped)
    if failures:
        lines.extend(("", "## Failures", ""))
        lines.extend(f"- {item}" for item in failures)
    (output_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_index_voice(output_dir: Path) -> str | None:
    index_path = output_dir / "INDEX.md"
    if not index_path.is_file():
        return None
    prefix = "Selected ElevenLabs stock voice: "
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).removesuffix(".")
    return None


def _read_index_rows(output_dir: Path) -> list[dict[str, str | int]]:
    index_path = output_dir / "INDEX.md"
    if not index_path.is_file():
        return []
    rows: list[dict[str, str | int]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            continue
        filename = cells[0].strip("`")
        try:
            rows.append({
                "file": filename,
                "provider": cells[1],
                "model": cells[2],
                "variant": cells[3],
                "chars": int(cells[4]),
                "credits": int(cells[5]) if cells[5].isdigit() else cells[5],
            })
        except ValueError:
            continue
    return rows


def _gradio_output_path(result: Any) -> Path:
    value = result.get("path") if isinstance(result, dict) else getattr(result, "path", result)
    if not isinstance(value, (str, Path)):
        raise VoiceTestError("HF Space returned an unsupported audio result")
    return Path(value)


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-") or "model"


def _redact(message: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message
