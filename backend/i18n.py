"""
Language templates for Saathi's spoken turns, and the small amount of
language plumbing needed to make Rime and the browser speech APIs use
the right language per patient.

Adding a third language later means: add a key here with the same
five template names, add its ISO code to RIME_LANG_CODES and
BROWSER_SPEECH_LANG, and pick/verify a Rime voice that supports it.
No other file needs to change.
"""
from typing import Optional

# ---------------------------------------------------------------------
# Rime language codes (short codes per Rime's API — see
# https://docs.rime.ai/docs/models and the API changelog). Passed as
# the optional "lang" field in the TTS request payload.
#
# NOTE: Hindi Rime voice support is rolling out on Rime's Coda model.
# Before your real demo, check https://docs.rime.ai/docs/voices for a
# confirmed Hindi-capable speaker/voice ID and set RIME_HINDI_SPEAKER
# in .env accordingly — the placeholder speaker in seed_patients.py
# is not guaranteed to render Hindi correctly until you verify it.
# ---------------------------------------------------------------------
RIME_LANG_CODES = {
    "en": "eng",
    "hi": "hin",
}

# BCP-47 codes for the browser's SpeechRecognition / speechSynthesis
# APIs (used by frontend/app.js).
BROWSER_SPEECH_LANG = {
    "en": "en-US",
    "hi": "hi-IN",
}

# ---------------------------------------------------------------------
# Companion personas. Saathi's voice has a name per language, shown in
# the UI ("Lyra is calling...") so the product reads as a consistent
# companion rather than a generic TTS demo. These map directly to the
# Rime speaker IDs actually used (see config.py RIME_DEFAULT_SPEAKER /
# RIME_HINDI_SPEAKER) — keep them in sync if you change the voice.
# ---------------------------------------------------------------------
PERSONA_NAME = {
    "en": "Lyra",
    "hi": "नादी (Nadi)",
}

# ---------------------------------------------------------------------
# Spoken turn templates.
#
# Hindi is written in Devanagari script, not Romanized — Rime's Hindi
# voice (like most Hindi TTS models) is trained on native script and
# will mispronounce Romanized "Hindi-in-Latin-letters" text as if it
# were English. The frontend transcript renders Devanagari natively,
# no extra handling needed.
# ---------------------------------------------------------------------
TEXT = {
    "en": {
        "greet_routine": "Hi, this is Saathi calling for your {medicine}, scheduled around {time}. Did you take today's dose?",
        "greet_last_missed": "Hi, this is Saathi. Last time you mentioned you hadn't taken your {medicine} yet. Have you taken today's dose?",
        "greet_deferred": "Hi again, this is Saathi calling back about your {medicine}. Did you get a chance to take it?",
        "reply_taken": "Wonderful, thank you for confirming. I'll check in again at your next scheduled dose. Take care!",
        "reply_missed_escalate": "I understand. Since you've missed a couple of doses in a row, I'm going to let your caregiver know so they can check in with you. Thank you for talking with me — take care.",
        "reply_missed_log": "Thanks for letting me know. Please try to take your {medicine} soon — I'll check on you again shortly.",
        "reply_later": "No problem at all — I'll call back a little later. Take your time.",
        "reply_unclear_reask": "Sorry, I didn't quite catch that — could you tell me clearly: did you take today's dose, yes or no?",
        "reply_unclear_giveup": "No worries — I'll check in again later. Take care!",
    },
    "hi": {
        "greet_routine": "नमस्ते, मैं Saathi बोल रही हूँ। आपकी {medicine} जो {time} बजे लेनी थी — क्या आपने आज की दवाई ले ली?",
        "greet_last_missed": "नमस्ते, मैं Saathi हूँ। पिछली बार आपने बताया था कि आपने {medicine} नहीं ली थी। क्या आपने आज की दवाई ले ली?",
        "greet_deferred": "नमस्ते, मैं Saathi फिर से कॉल कर रही हूँ आपकी {medicine} के बारे में। क्या आपने ले ली?",
        "reply_taken": "बहुत अच्छा, बताने के लिए धन्यवाद। मैं अगली दवाई के समय फिर कॉल करूँगी। अपना ख़याल रखिए!",
        "reply_missed_escalate": "ठीक है। चूँकि आपने लगातार दो बार दवाई नहीं ली, मैं आपके केयरगिवर को बता रही हूँ ताकि वो आपसे बात कर सकें। बात करने के लिए धन्यवाद — अपना ख़याल रखिए।",
        "reply_missed_log": "बताने के लिए धन्यवाद। कृपया जल्द ही अपनी {medicine} ले लीजिए — मैं थोड़ी देर में फिर से पूछूँगी।",
        "reply_later": "कोई बात नहीं — मैं थोड़ी देर बाद फिर कॉल करूँगी। आप अपना समय लीजिए।",
        "reply_unclear_reask": "माफ़ कीजिए, मैं समझ नहीं पाई — कृपया साफ़ बताइए: क्या आपने आज की दवाई ली, हाँ या नहीं?",
        "reply_unclear_giveup": "कोई बात नहीं — मैं बाद में फिर से पूछूँगी। अपना ख़याल रखिए!",
    },
}


def lang_key(language: Optional[str]) -> str:
    """Normalises any patient.language value to a supported template
    key, defaulting to English for anything we don't have templates
    for — so an unrecognised language code never crashes the call."""
    if language and language.lower().startswith("hi"):
        return "hi"
    return "en"


def t(language: Optional[str], key: str, **kwargs) -> str:
    """Fetch and format a template for the given language."""
    lk = lang_key(language)
    template = TEXT[lk][key]
    return template.format(**kwargs)


def rime_lang_code(language: Optional[str]) -> str:
    return RIME_LANG_CODES[lang_key(language)]


def browser_speech_lang(language: Optional[str]) -> str:
    return BROWSER_SPEECH_LANG[lang_key(language)]


def persona_name(language: Optional[str]) -> str:
    return PERSONA_NAME[lang_key(language)]
