"""
Prescription photo parsing.

Uses Anthropic's Messages API (vision-capable Claude models) to read a
photographed prescription/medicine label and extract a medicine name
and a plain-language dose schedule. This is entirely optional: without
ANTHROPIC_API_KEY set, `extract()` returns configured=False and the
frontend simply lets the caregiver type the fields in by hand after
looking at the photo themselves — same honest-fallback pattern as
backend/rime_client.py.

IMPORTANT — this is decision support, not a medical device. See
README Limitations: extracted text is a starting point for a human
(the caregiver) to review and correct, never auto-applied without
confirmation. Never used for dosing decisions on its own.
"""
import base64
import json
import logging
import re
from typing import Optional

import requests

from backend.config import settings
from backend.models import PrescriptionParseResponse

logger = logging.getLogger("saathi.vision")

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

_EXTRACTION_PROMPT = (
    "You are looking at a photo of a medicine prescription, label, or strip. "
    "Extract ONLY what is clearly legible in the image. Respond with STRICT JSON "
    "only, no markdown fences, no commentary, matching exactly this shape:\n"
    '{"medicine": "<medicine name and strength, or null if unreadable>", '
    '"schedule_time": "<a short plain-language dosing schedule as written or '
    'clearly implied, e.g. \'8:00 AM\' or \'twice daily, morning and night\', '
    'or null if unreadable>", '
    '"confidence_note": "<one short sentence flagging anything unclear or '
    'that the caregiver should double check, or null if nothing to flag>"}\n\n'
    "If the image is not a prescription/medicine label at all, set both "
    "medicine and schedule_time to null and say so in confidence_note. "
    "Never guess a dosage or medicine you cannot actually read in the image."
)


class VisionClient:
    def __init__(self) -> None:
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_VISION_MODEL

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def extract(self, image_b64: str, media_type: str = "image/jpeg") -> PrescriptionParseResponse:
        if not self.is_configured:
            logger.info("ANTHROPIC_API_KEY not set — prescription photo parsing skipped (manual entry fallback).")
            return PrescriptionParseResponse(
                configured=False,
                confidence_note="Photo saved, but automatic reading isn't set up yet — please fill in the fields below from the photo.",
            )

        payload = {
            "model": self.model,
            "max_tokens": 400,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                        },
                        {"type": "text", "text": _EXTRACTION_PROMPT},
                    ],
                }
            ],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            resp = requests.post(ANTHROPIC_MESSAGES_URL, json=payload, headers=headers, timeout=25)
        except requests.RequestException as e:
            logger.warning("Vision request failed: %s", e)
            return PrescriptionParseResponse(
                configured=True,
                confidence_note="Couldn't reach the photo-reading service — please fill in the fields manually.",
            )

        if resp.status_code != 200:
            logger.warning("Vision API returned %s: %s", resp.status_code, resp.text[:300])
            return PrescriptionParseResponse(
                configured=True,
                confidence_note="Photo reading failed — please fill in the fields manually.",
            )

        try:
            data = resp.json()
            text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
            parsed = _parse_json_loose(text)
        except (ValueError, KeyError) as e:
            logger.warning("Could not parse vision response: %s", e)
            return PrescriptionParseResponse(
                configured=True,
                confidence_note="Got a response but couldn't read it clearly — please fill in the fields manually.",
            )

        return PrescriptionParseResponse(
            configured=True,
            medicine=parsed.get("medicine") or None,
            schedule_time=parsed.get("schedule_time") or None,
            confidence_note=parsed.get("confidence_note") or None,
        )


def _parse_json_loose(text: str) -> dict:
    """Strips accidental markdown code fences before parsing — models
    occasionally wrap JSON in ```json ... ``` despite instructions not to."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


vision_client = VisionClient()
