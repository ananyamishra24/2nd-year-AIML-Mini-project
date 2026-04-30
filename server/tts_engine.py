"""
Azure OpenAI gpt-4o-mini-tts Engine
────────────────────────────────────
Calls the Azure OpenAI gpt-4o-mini-tts deployment and returns MP3 audio bytes.

Unlike classic Azure Neural TTS (which uses SSML), gpt-4o-mini-tts takes a
plain-JSON request with an ``instructions`` field that steers delivery in
natural language — we use it to make narration sound like a kind adult
reading at a child's bedside, not a clinical text-to-speech robot.

Required env vars:
  AZURE_TTS_API_KEY   — Azure OpenAI resource key
  AZURE_TTS_ENDPOINT  — Full deployment URL *including* the api-version query,
                        e.g. https://<resource>.cognitiveservices.azure.com/
                              openai/deployments/gpt-4o-mini-tts/audio/speech
                              ?api-version=2025-03-01-preview
"""

import os
import logging
import requests

logger = logging.getLogger('brave_story.tts')

# ── Voice catalogue ───────────────────────────────────────────────────
# IDs are OpenAI's canonical voice names — passed through verbatim.

VOICES = [
    {'id': 'coral',   'name': 'Coral — Warm & Friendly'},
    {'id': 'sage',    'name': 'Sage — Calm & Thoughtful'},
    {'id': 'ballad',  'name': 'Ballad — Gentle Storyteller'},
    {'id': 'nova',    'name': 'Nova — Bright & Engaging'},
    {'id': 'shimmer', 'name': 'Shimmer — Soft & Gentle'},
    {'id': 'alloy',   'name': 'Alloy — Clear & Neutral'},
    {'id': 'echo',    'name': 'Echo — Calm & Steady'},
    {'id': 'fable',   'name': 'Fable — Expressive Storyteller'},
    {'id': 'onyx',    'name': 'Onyx — Deep & Rich'},
    {'id': 'ash',     'name': 'Ash — Grounded & Warm'},
]
ALLOWED_VOICE_IDS = {v['id'] for v in VOICES}
DEFAULT_VOICE = 'coral'

# Base steering prompt — the core differentiator of gpt-4o-mini-tts.
_NARRATION_INSTRUCTIONS = (
    "You are narrating a storybook for a child aged 4 to 10 who may be in a "
    "pediatric hospital bed. Your voice should feel like a kind parent or "
    "favourite aunt or uncle reading at the bedside. Speak at a gentle, "
    "unhurried pace. Pronounce every word clearly. Embrace small natural "
    "pauses between sentences. Bring a warm smile into your voice, "
    "especially on playful or magical lines. Never sound clinical, robotic, "
    "or rushed."
)


def _api_key() -> str:
    return os.environ.get('AZURE_TTS_API_KEY', '')


def _endpoint() -> str:
    return os.environ.get('AZURE_TTS_ENDPOINT', '').strip()


def is_available() -> bool:
    return bool(_api_key() and _endpoint())


def synthesize(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0,
               instructions: str = None) -> bytes:
    """Convert text to MP3 audio bytes via Azure OpenAI gpt-4o-mini-tts."""
    if not is_available():
        raise RuntimeError(
            'gpt-4o-mini-tts not configured — set AZURE_TTS_API_KEY and AZURE_TTS_ENDPOINT'
        )

    voice = voice if voice in ALLOWED_VOICE_IDS else DEFAULT_VOICE
    speed = max(0.25, min(float(speed), 4.0))
    text  = (text or '')[:4096]
    if not text.strip():
        raise ValueError('text is empty')

    payload = {
        'model':           'gpt-4o-mini-tts',
        'input':           text,
        'voice':           voice,
        'instructions':    instructions or _NARRATION_INSTRUCTIONS,
        'response_format': 'mp3',
        'speed':           speed,
    }

    resp = requests.post(
        _endpoint(),
        headers={
            'api-key':      _api_key(),
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=60,
    )
    # Surface the upstream body on failure for actionable logs.
    if not resp.ok:
        logger.error('gpt-4o-mini-tts %s: %s', resp.status_code, resp.text[:500])
        resp.raise_for_status()
    return resp.content
