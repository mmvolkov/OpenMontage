"""Self-hosted CosyVoice text-to-speech provider tool.

Talks to an OpenAI-compatible /v1/audio/speech endpoint backed by
Fun-CosyVoice3 (see the `tts` service repo). Voices are deployment-side
presets — a reference recording plus its transcript — so the clone follows
whoever the operator enrolled, not a fixed vendor catalogue.

Configured with TTS_BASE_URL + TTS_API_KEY, the same way the transcriber
tool picks up a self-hosted diarization service via DIARIZE_*.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

CYRILLIC = re.compile(r"[Ѐ-ӿ]")


class CosyVoiceTTS(BaseTool):
    name = "cosyvoice_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "cosyvoice"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:TTS_BASE_URL", "env:TTS_API_KEY"]
    install_instructions = (
        "Set TTS_BASE_URL and TTS_API_KEY to a self-hosted CosyVoice speech service\n"
        "(OpenAI-compatible POST /v1/audio/speech). Voices are presets on that\n"
        "deployment — list them with GET /v1/voices. Synthesis is free: it runs on\n"
        "your own GPU."
    )
    fallback = "piper_tts"
    fallback_tools = ["piper_tts", "elevenlabs_tts", "google_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "voice_cloning",
        "multilingual",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,  # self-hosted, but still over the network
        "native_audio": True,
        "ssml": False,
    }
    best_for = [
        "narration in a cloned in-house voice at zero per-character cost",
        "Russian narration that local Piper voices read too flatly",
        "privacy-sensitive scripts that must not leave your own infrastructure",
    ]
    not_good_for = [
        "digits, dates and abbreviations left unexpanded — the text normalizer is "
        "off for Cyrillic, so write '2026' as 'две тысячи двадцать шестой'",
        "long single-call scripts — synthesis is synchronous; send one line per call",
        "deterministic reproducible output",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to speak. One narration line per call. Spell out numbers, "
                    "dates and abbreviations: the normalizer is disabled for Cyrillic."
                ),
            },
            "voice": {
                "type": "string",
                "description": "Preset name on the deployment (GET /v1/voices). Omit for its default.",
            },
            "voice_id": {
                "type": "string",
                "description": "Alias for voice (selector compatibility). Used only when voice is absent.",
            },
            "instruct": {
                "type": "string",
                "description": (
                    "Delivery instruction in English, e.g. 'speak calmly, moderate pace'. "
                    "Omit to use the preset's own instruction; pass an empty string to "
                    "drop it. Russian text here is read aloud instead of obeyed."
                ),
            },
            "instructions": {
                "type": "string",
                "description": "Alias for instruct (selector compatibility). Used only when instruct is absent.",
            },
            "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0, "default": 1.0},
            "format": {"type": "string", "enum": ["wav", "mp3"], "default": "wav"},
            "output_path": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "provider": {"type": "string"},
            "voice": {"type": "string"},
            "format": {"type": "string"},
            "text_length": {"type": "integer"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, backoff_seconds=2.0, retryable_errors=["timeout"]
    )
    idempotency_key_fields = ["text", "voice", "instruct", "speed", "format"]
    side_effects = [
        "writes audio file to output_path",
        "calls the self-hosted speech service",
    ]
    user_visible_verification = [
        "Listen to generated audio for voice-clone fidelity and correct stress",
    ]
    quality_score = 0.85
    latency_p50_seconds = 4.0

    @staticmethod
    def _service() -> tuple[str, str] | None:
        """(base_url, api_key) when both are configured, else None."""
        url = os.environ.get("TTS_BASE_URL", "").strip().rstrip("/")
        api_key = os.environ.get("TTS_API_KEY", "").strip()
        return (url, api_key) if url and api_key else None

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._service() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # self-hosted

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        service = self._service()
        if not service:
            return ToolResult(
                success=False,
                error="No self-hosted speech service configured. " + self.install_instructions,
            )

        instruct = inputs.get("instruct", inputs.get("instructions"))
        if instruct and CYRILLIC.search(instruct):
            return ToolResult(
                success=False,
                error=(
                    "instruct must be written in English: CosyVoice reads a Russian "
                    f"instruction aloud instead of obeying it. Got: {instruct!r}"
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, service=service, instruct=instruct)
        except Exception as exc:
            return ToolResult(success=False, error=f"Speech synthesis failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(
        self, inputs: dict[str, Any], *, service: tuple[str, str], instruct: str | None
    ) -> ToolResult:
        import requests

        base_url, api_key = service
        fmt = inputs.get("format", "wav")
        voice = inputs.get("voice") or inputs.get("voice_id")

        body: dict[str, Any] = {
            "input": inputs["text"],
            "response_format": fmt,
            "speed": float(inputs.get("speed", 1.0)),
        }
        if voice:
            body["voice"] = voice
        # Absent means "use the preset's instruction"; an explicit "" means "none".
        if instruct is not None:
            body["instruct"] = instruct

        response = requests.post(
            f"{base_url}/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=int(os.environ.get("TTS_TIMEOUT", "300")),
        )
        if response.status_code >= 400:
            # The service names the available presets when a voice is unknown.
            return ToolResult(
                success=False,
                error=f"Speech service returned {response.status_code}: {response.text[:500]}",
            )

        output_path = Path(inputs.get("output_path", f"cosyvoice_tts.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": response.headers.get("X-Voice", voice or ""),
                "format": fmt,
                "text_length": len(inputs["text"]),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            model="Fun-CosyVoice3-0.5B",
        )
