"""Transcription tool wrapping faster-whisper / WhisperX.

Provides speech-to-text with word-level timestamps and optional speaker
diarization. Falls back gracefully when GPU or diarization dependencies
are not available.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class Transcriber(BaseTool):
    name = "transcriber"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "whisperx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["python:faster_whisper"]
    install_instructions = (
        "Set DIARIZE_URL and DIARIZE_API_KEY to transcribe through a "
        "self-hosted diarization service, or install a local engine: "
        "pip install faster-whisper  # CPU mode\n"
        "pip install faster-whisper[gpu]  # GPU mode (requires CUDA)\n"
        "pip install whisperx  # For diarization support"
    )
    agent_skills = ["speech-to-text"]

    capabilities = [
        "transcribe",
        "word_timestamps",
        "diarization",
        "language_detection",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Path to audio or video file"},
            "model_size": {
                "type": "string",
                "enum": ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                "default": "base",
            },
            "language": {"type": "string", "description": "ISO 639-1 language code, or null for auto-detect"},
            "diarize": {"type": "boolean", "default": False},
            "output_dir": {"type": "string", "description": "Directory for output files"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "segments": {"type": "array"},
            "word_timestamps": {"type": "array"},
            "language": {"type": "string"},
            "duration_seconds": {"type": "number"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2,
        ram_mb=2048,
        vram_mb=0,  # CPU by default; GPU optional
        disk_mb=500,
        network_required=False,
    )

    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["MemoryError"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["input_path", "model_size", "language"]
    side_effects = ["writes transcript JSON to output_dir"]
    fallback = None
    user_visible_verification = [
        "Check transcript text against source audio",
        "Verify word timestamps align with speech",
    ]

    @staticmethod
    def _remote_config() -> Optional[tuple[str, str]]:
        """Return (base_url, api_key) when a diarization service is configured."""
        url = os.environ.get("DIARIZE_URL", "").strip().rstrip("/")
        api_key = os.environ.get("DIARIZE_API_KEY", "").strip()
        return (url, api_key) if url and api_key else None

    def get_status(self) -> ToolStatus:
        if self._remote_config():
            return ToolStatus.AVAILABLE
        try:
            import faster_whisper  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def _has_diarization(self) -> bool:
        try:
            import whisperx  # noqa: F401
            return True
        except ImportError:
            return False

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Rough estimate: ~0.5x real-time on CPU for 'base' model."""
        return 60.0  # conservative default

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        model_size = inputs.get("model_size", "base")
        language = inputs.get("language")
        diarize = inputs.get("diarize", False)
        output_dir = Path(inputs.get("output_dir", input_path.parent))

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input file not found: {input_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        remote = self._remote_config()
        if remote:
            return self._transcribe_remote(remote, input_path, output_dir, inputs)

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return ToolResult(
                success=False,
                error="faster-whisper is not installed. Run: pip install faster-whisper",
            )

        start = time.time()

        # faster-whisper executes through CTranslate2, so that runtime—not
        # PyTorch—is authoritative for CUDA availability and compute types.
        device = "cpu"
        compute_type = "int8"
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                supported = ctranslate2.get_supported_compute_types("cuda")
                for candidate in ("float16", "int8_float16", "float32"):
                    if candidate in supported:
                        device = "cuda"
                        compute_type = candidate
                        break
        except Exception:
            # Probing is advisory. CPU remains a safe deterministic baseline.
            pass

        def _transcribe_on(selected_device: str, selected_compute_type: str):
            model = WhisperModel(
                model_size,
                device=selected_device,
                compute_type=selected_compute_type,
            )
            segments_iter, transcription_info = model.transcribe(
                str(input_path),
                language=language,
                word_timestamps=True,
                vad_filter=True,
            )

            parsed_segments = []
            parsed_words = []
            # faster-whisper evaluates lazily. Draining the iterator here keeps
            # missing CUDA runtime libraries inside the fallback boundary.
            for seg in segments_iter:
                seg_data = {
                    "id": seg.id,
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                }

                if seg.words:
                    words = []
                    for word in seg.words:
                        word_entry = {
                            "word": word.word,
                            "start": round(word.start, 3),
                            "end": round(word.end, 3),
                            "probability": round(word.probability, 3),
                        }
                        words.append(word_entry)
                        parsed_words.append(word_entry)
                    seg_data["words"] = words

                parsed_segments.append(seg_data)

            return parsed_segments, parsed_words, transcription_info

        gpu_fallback_reason = None
        try:
            segments, word_timestamps, info = _transcribe_on(device, compute_type)
        except Exception as exc:
            if device == "cpu":
                raise
            gpu_fallback_reason = f"{type(exc).__name__}: {exc}"
            device = "cpu"
            compute_type = "int8"
            segments, word_timestamps, info = _transcribe_on(device, compute_type)

        detected_language = language or info.language
        duration = info.duration

        # Optional diarization pass
        if diarize and self._has_diarization():
            segments = self._apply_diarization(
                str(input_path), segments, detected_language
            )

        elapsed = time.time() - start

        result_data = {
            "segments": segments,
            "word_timestamps": word_timestamps,
            "language": detected_language,
            "duration_seconds": round(duration, 3),
            "model_size": model_size,
            "device": device,
            "compute_type": compute_type,
            "gpu_fallback_reason": gpu_fallback_reason,
        }

        # Write transcript JSON
        output_path = output_dir / f"{input_path.stem}_transcript.json"
        output_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    @staticmethod
    def _map_words(utterance: dict[str, Any]) -> list[dict]:
        """Map service words onto the faster-whisper word shape."""
        mapped = []
        for word in utterance.get("words") or []:
            entry = {
                "word": word["text"],
                "start": round(word["start"], 3),
                "end": round(word["end"], 3),
            }
            if word.get("conf") is not None:
                entry["probability"] = word["conf"]
            mapped.append(entry)
        return mapped

    def _transcribe_remote(
        self,
        remote: tuple[str, str],
        input_path: Path,
        output_dir: Path,
        inputs: dict[str, Any],
    ) -> ToolResult:
        """Transcribe through a self-hosted diarization service.

        The service returns speaker utterances with timecodes. Word-level
        timestamps stay inside it, so `word_timestamps` comes back empty and
        downstream cues fall back to utterance-level timing.
        """
        import requests

        base_url, api_key = remote
        timeout = int(os.environ.get("DIARIZE_TIMEOUT", "900"))
        start = time.time()

        try:
            with input_path.open("rb") as handle:
                response = requests.post(
                    f"{base_url}/v1/diarize",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (input_path.name, handle)},
                    data={
                        "mode": "auto",
                        "merge_speakers": "false",
                        "response_format": "json",
                        "words": "true",
                    },
                    timeout=timeout,
                )
        except requests.RequestException as exc:
            return ToolResult(
                success=False,
                error=f"Diarization service unreachable at {base_url}: {exc}",
            )

        if response.status_code != 200:
            return ToolResult(
                success=False,
                error=(
                    f"Diarization service returned {response.status_code}: "
                    f"{response.text[:300]}"
                ),
            )

        utterances = response.json().get("segments", [])
        segments = []
        word_timestamps: list[dict] = []
        for index, utterance in enumerate(utterances):
            segment = {
                "id": index,
                "start": round(utterance["start"], 3),
                "end": round(utterance["end"], 3),
                "text": utterance["text"].strip(),
                "speaker": utterance.get("speaker"),
            }
            # Older service builds return utterances only; cues then fall back
            # to utterance-level timing instead of word-level.
            words = self._map_words(utterance)
            if words:
                segment["words"] = words
                word_timestamps.extend(words)
            segments.append(segment)

        result_data = {
            "segments": segments,
            "word_timestamps": word_timestamps,
            "language": inputs.get("language") or "ru",
            "duration_seconds": segments[-1]["end"] if segments else 0.0,
            "backend": "diarization_service",
            "service_url": base_url,
        }

        output_path = output_dir / f"{input_path.stem}_transcript.json"
        output_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(output_path)],
            duration_seconds=round(time.time() - start, 2),
        )

    def _apply_diarization(
        self,
        audio_path: str,
        segments: list[dict],
        language: str,
    ) -> list[dict]:
        """Apply WhisperX diarization to assign speaker labels."""
        try:
            import whisperx

            # Load audio for alignment
            audio = whisperx.load_audio(audio_path)

            # Align segments with word timestamps
            align_model, align_metadata = whisperx.load_align_model(
                language_code=language, device="cpu"
            )
            aligned = whisperx.align(
                segments, align_model, align_metadata, audio, device="cpu"
            )

            # Diarize
            import os
            hf_token = os.environ.get("HF_TOKEN")
            if not hf_token:
                # Can't diarize without HuggingFace token for pyannote
                return segments

            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=hf_token, device="cpu"
            )
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, aligned)

            return result.get("segments", segments)
        except Exception:
            # Diarization is best-effort; return original segments on failure
            return segments
