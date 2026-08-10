"""
Thin wrapper around Rime's TTS REST endpoint.

Endpoint and payload shape follow Rime's official "TTS in five minutes"
quickstart (POST /v1/rime-tts, Bearer auth, Accept: audio/wav):
https://docs.rime.ai/docs/quickstart-five-minute

Design choice — graceful degradation:
If RIME_API_KEY is not set, or the Rime call fails for any reason
(network, rate limit, bad key), `synthesize()` returns None instead of
raising. The orchestrator then falls back to text-only output and the
frontend uses the browser's built-in speech synthesis, clearly labelled
as an offline fallback voice. This means the app is always runnable and
testable end-to-end without a paid key — but a real RIME_API_KEY MUST be
set for the actual hackathon demo, since VoxForge requires Rime speech
to drive the core experience.
"""
import base64
import logging
from typing import Optional

import requests

from backend.config import settings

logger = logging.getLogger("saathi.rime")

# ---------------------------------------------------------------------
# Known Coda voices per language, pulled from Rime's live catalog
# (https://users.rime.ai/data/voices/all-v2.json) on 2026-08-09. This
# is a point-in-time snapshot for validation/warning purposes only —
# Rime ships new voices regularly, so this list can go stale. It is
# intentionally NOT used to block a request, only to warn loudly in
# logs if a configured speaker doesn't look right for its language,
# so a speaker/language mismatch is caught before a demo instead of
# silently mispronouncing on stage.
# ---------------------------------------------------------------------
KNOWN_CODA_VOICES = {
    "eng": {
        "adeline", "albion", "alfhild", "alma", "amarante", "ana", "andromeda",
        "arcade", "argon", "astra", "atrium", "aurelio", "azura", "backbay",
        "bancroft", "bauer", "beatty", "berklee", "bianchi", "blackout", "bond",
        "bronte", "brussels", "celeste", "chantal", "clara", "clarity",
        "clementine", "clipper", "cupola", "drift", "dwight", "egbert",
        "eliphas", "elsie", "estelle", "esther", "eucalyptus", "everett",
        "eyre", "fern", "firefly", "firewall", "foster", "fuzz", "godfrey",
        "green", "hawa", "helium", "heller", "hesse", "hugo", "ibis", "jayne",
        "jicarilla", "joyce", "latte", "lawton", "lintel", "luna", "lydia",
        "lyra", "maddux", "madison", "marlu", "masonry", "mercury", "merritt",
        "milan", "milton", "moraga", "moss", "myrtle", "naipaul", "neptune",
        "nexus", "nicklaus", "oculus", "orbea", "orion", "ozu", "parapet",
        "perth", "pilaster", "pola", "potrero", "prentiss", "proxy", "pulse",
        "purple", "ronan", "rooney", "rosal", "rosemount", "ru", "sachet",
        "salik", "sirius", "sky", "solana", "sonnagh", "stucco", "tauro",
        "thalassa", "tim", "topeka", "transom", "truss", "ursa", "vashti",
        "vayu", "vernal", "vespera", "vesta", "victoria", "walavista",
        "wawona", "willow", "woolsey", "yukiko", "zen",
    },
    "hin": {"nadi", "taru"},
    "spa": {
        "alba", "amanecer", "atardecer", "azulado", "brisa", "celestino",
        "cielo", "claridad", "estrella", "isla", "lark", "luz", "mar",
        "mediodia", "nieve", "nova", "ocaso", "orionne", "plenilunio",
        "resplandor", "seraphina", "serena", "solsticio", "trueno", "vespero",
    },
    "jpn": {"akari", "akatsuki", "hirake", "hiru", "nozomi", "ren", "sakura", "taiyo", "yoru", "yugata"},
    "por": {"alzira", "baltasar", "celso", "estela", "isadora", "lucia", "rio", "sol"},
    "ger": {"aura", "baldur", "kumara", "liesel", "lorelei", "nacht", "runa"},
    "fra": {"aurelie", "destin", "seraphine", "solstice", "violette"},
    "ara": {"batin", "fadil", "layla", "qadir", "sakina", "zahir"},
}


def check_voice_language_match(speaker: str, lang: Optional[str]) -> None:
    """Logs a warning (never raises) if `speaker` isn't in our known
    snapshot for `lang` on Coda. This is advisory only — the catalog
    can change, so a warning here means "double-check this," not
    "this is definitely broken." Always verify against
    https://docs.rime.ai/docs/voices before a real demo regardless."""
    if not lang or lang not in KNOWN_CODA_VOICES:
        return
    if speaker not in KNOWN_CODA_VOICES[lang]:
        logger.warning(
            "Speaker '%s' is not in the known Coda voice list for lang='%s'. "
            "It may mispronounce or fail. Verify at https://docs.rime.ai/docs/voices "
            "and update RIME_HINDI_SPEAKER (or the relevant .env setting) if wrong.",
            speaker, lang,
        )


class RimeClient:
    def __init__(self):
        self.api_key = settings.RIME_API_KEY
        self.url = settings.RIME_TTS_URL
        self.model_id = settings.RIME_MODEL_ID
        self.timeout = settings.RIME_TIMEOUT_SECONDS

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def synthesize(self, text: str, speaker: Optional[str] = None, lang: Optional[str] = None) -> Optional[str]:
        """
        Returns base64-encoded WAV audio, or None if Rime is not
        configured / the request failed. Never raises.

        `lang` is Rime's short language code (e.g. "eng", "hin") — see
        backend/i18n.py::RIME_LANG_CODES. Omitted from the payload
        entirely when not given, so this stays backward compatible
        with a plain English-only call.
        """
        if not self.is_configured:
            logger.info("RIME_API_KEY not set — skipping real synthesis (fallback mode).")
            return None

        payload = {
            "text": text,
            "speaker": speaker or settings.RIME_DEFAULT_SPEAKER,
            "modelId": self.model_id,
        }
        if lang:
            payload["lang"] = lang
        check_voice_language_match(payload["speaker"], lang)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }
        try:
            resp = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode("ascii")
        except requests.RequestException as exc:
            logger.warning("Rime synthesis failed, falling back to text-only: %s", exc)
            return None


rime_client = RimeClient()
