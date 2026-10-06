"""Qwen3-TTS voice provider (realtime 3.8 stack) via HuggingFace Inference.

Token is loaded from env/vault at call time, never hardcoded or committed.
No token, no gated-model accept, any error -> raise; callers fall back to
edge-tts so the $0 path never breaks. Pattern mirrors freaktown's
QwenTTSProvider (async/httpx there, sync/urllib here — same endpoint).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen3-TTS-12Hz-0.6B-Base"


class QwenVoiceError(Exception):
    pass


def token() -> str:
    for name in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        tok = (os.environ.get(name) or "").strip()
        if tok:
            return tok
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            for name in ("HF_TOKEN=", "HUGGINGFACE_TOKEN=", "HUGGING_FACE_HUB_TOKEN="):
                if line.startswith(name):
                    tok = line.split("=", 1)[1].strip()
                    if tok:
                        return tok
    return ""


def configured() -> bool:
    return bool(token())


def generate(text: str, out_mp3: Path, voice: str = "default",
             ref_audio: Path | None = None, timeout: int = 120) -> Path:
    """3-second-clone capable TTS. ref_audio enables voice cloning;
    without it the base voice speaks. Raises QwenVoiceError on any failure
    so the caller can fall back to edge-tts."""
    tok = token()
    if not tok:
        raise QwenVoiceError("no HF token — attach HF_TOKEN for Qwen voices")
    payload: dict = {"inputs": text}
    if ref_audio and ref_audio.is_file():
        import base64
        payload["inputs"] = {
            "text": text,
            "reference_audio": base64.b64encode(ref_audio.read_bytes()).decode(),
        }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            blob = r.read()
    except urllib.error.HTTPError as e:
        raise QwenVoiceError(f"Qwen TTS HTTP {e.code} — check token + gated-model accept")
    except Exception as e:  # noqa: BLE001
        raise QwenVoiceError(f"Qwen TTS unreachable: {str(e)[:120]}")
    if len(blob) < 500:
        raise QwenVoiceError("Qwen TTS returned no audio")
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    out_mp3.write_bytes(blob)
    return out_mp3
