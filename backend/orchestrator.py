"""
The call orchestrator. This is where the "hard production problem" from
the pitch actually lives: separating a low-friction reminder from a
high-trust, harder-to-trigger escalation, and recovering cleanly from
interruptions instead of losing or duplicating state.

Session state is kept in-memory (a dict keyed by session_id). That's a
deliberate, documented limitation for a prototype — see README
Limitations. A production deployment would move this to Redis or
similar so state survives a process restart / scales across workers.
"""
import re
import uuid
from typing import Dict, List, Optional

from backend.config import settings
from backend.i18n import persona_name, rime_lang_code, t
from backend.models import CallTurnResponse, PatientMemory
from backend.patient_registry import patient_registry
from backend.qdrant_store import new_patient_memory, now_iso, qdrant_store
from backend.rime_client import rime_client

# ---------------------------------------------------------------------
# In-memory session + alert stores (prototype scope — see README)
# ---------------------------------------------------------------------
SESSIONS: Dict[str, dict] = {}
ALERTS: List[dict] = []


# ---------------------------------------------------------------------
# Rule-based intent classification
#
# This is intentionally simple (keyword / phrase matching — English,
# transliterated Hindi, AND native Devanagari script) rather than an
# LLM call, so the core call flow is fast, free to run, and fully
# deterministic for testing. A real deployment should replace this
# with a proper NLU model or an LLM prompt — documented in README
# Limitations.
#
# Devanagari matters because the browser's SpeechRecognition API set
# to hi-IN returns native script ("हाँ", "नहीं लिया"), not Romanized
# text — so both forms need to be recognised, not just transliterated
# Hindi typed in Latin letters.
# ---------------------------------------------------------------------
_LATER_PHRASES = [
    "later", "call back", "baad me", "not now", "call me later", "busy right now", "can you call",
    "बाद में", "थोड़ी देर बाद", "अभी नहीं",
]
_MISSED_PHRASES = [
    "not yet", "haven't taken", "havent taken", "didn't take", "didnt take",
    "forgot", "nahi liya", "not taken", "missed it", "no i haven't", "no i didn't",
    "नहीं ली", "अभी नहीं ली", "भूल गया", "भूल गई", "नहीं लिया",
]
_MISSED_WORDS = {"no", "nope", "nahi", "नहीं"}
_TAKEN_PHRASES = [
    "already took", "took it", "haan le liya", "le liya", "i took", "yes i did",
    "ले ली", "ले लिया", "हाँ ले ली", "पहले ले ली",
]
_TAKEN_WORDS = {"yes", "yeah", "yep", "taken", "done", "liya", "haan", "हाँ", "हां", "ली", "लिया"}


def _words(text: str) -> set:
    # Latin letters AND Devanagari block (U+0900–U+097F) so Hindi
    # speech-recognition output (native script) tokenises correctly.
    return set(re.findall(r"[a-zA-Z\u0900-\u097F']+", text.lower()))


def classify_intent(text: str) -> str:
    t = text.lower().strip()
    w = _words(t)

    if any(p in t for p in _LATER_PHRASES):
        return "LATER"
    if any(p in t for p in _MISSED_PHRASES) or (w & _MISSED_WORDS):
        return "MISSED"
    if any(p in t for p in _TAKEN_PHRASES) or (w & _TAKEN_WORDS):
        return "TAKEN"
    return "UNCLEAR"


# ---------------------------------------------------------------------
# Speech generation helper
# ---------------------------------------------------------------------
def _speak(text: str, voice_pref: str, language: str) -> dict:
    audio_b64 = rime_client.synthesize(text, speaker=voice_pref, lang=rime_lang_code(language))
    return {
        "text": text,
        "audio_b64": audio_b64,
        "audio_source": "rime" if audio_b64 else "none",
    }


def _event_summary(patient_id: str, memory: PatientMemory) -> str:
    """Short synthetic description used only to build the similarity
    vector — never raw patient speech. See qdrant_store.py docstring."""
    return (
        f"patient {patient_id} risk {memory.risk_level} "
        f"missed_count {memory.missed_count} "
        f"escalations {len(memory.escalation_history)} "
        f"deferred {memory.deferred}"
    )


# ---------------------------------------------------------------------
# Public API used by main.py
# ---------------------------------------------------------------------
def start_call(patient_id: str) -> CallTurnResponse:
    patient = patient_registry.get(patient_id)
    if patient is None:
        raise ValueError(f"Unknown patient_id: {patient_id}")

    memory = qdrant_store.get_patient_memory(patient_id)
    if memory is None:
        memory = new_patient_memory(patient_id, patient.language, patient.voice_pref, patient.risk_level)

    if memory.deferred:
        greeting = t(memory.language, "greet_deferred", medicine=patient.medicine)
    elif memory.missed_count >= 1:
        greeting = t(memory.language, "greet_last_missed", medicine=patient.medicine)
    else:
        greeting = t(memory.language, "greet_routine", medicine=patient.medicine, time=patient.schedule_time)

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {"patient_id": patient_id, "stage": "AWAIT_CONFIRMATION", "reask_count": 0}

    speech = _speak(greeting, memory.voice_pref, memory.language)
    similar = qdrant_store.find_similar_cases(patient_id, _event_summary(patient_id, memory))

    return CallTurnResponse(
        session_id=session_id,
        stage="AWAIT_CONFIRMATION",
        speaker_text=speech["text"],
        audio_b64=speech["audio_b64"],
        audio_source=speech["audio_source"],
        escalated=False,
        persona_name=persona_name(memory.language),
        memory_snapshot=memory,
        similar_cases=similar,
    )


def handle_response(session_id: str, patient_id: str, text: str) -> CallTurnResponse:
    if session_id not in SESSIONS:
        raise ValueError("Unknown or expired session_id. Start a new call.")
    session = SESSIONS[session_id]
    if session["patient_id"] != patient_id:
        # This check is what guarantees session state can never be
        # applied to the wrong patient's memory.
        raise ValueError("session_id does not belong to this patient_id.")

    patient = patient_registry.get(patient_id)
    memory = qdrant_store.get_patient_memory(patient_id) or new_patient_memory(
        patient_id, patient.language, patient.voice_pref, patient.risk_level
    )

    intent = classify_intent(text)
    escalated = False

    if intent == "TAKEN":
        memory.missed_count = 0
        memory.last_confirmed = now_iso()
        memory.deferred = False
        reply = t(memory.language, "reply_taken")
        session["stage"] = "CLOSED"

    elif intent == "MISSED":
        memory.missed_count += 1
        memory.last_missed = now_iso()
        memory.deferred = False
        if memory.missed_count >= settings.ESCALATION_THRESHOLD:
            escalated = True
            alert = {
                "alert_id": str(uuid.uuid4()),
                "patient_id": patient_id,
                "display_name": patient.display_name,
                "created_at": now_iso(),
                "reason": f"{memory.missed_count} consecutive missed doses",
                "missed_count": memory.missed_count,
            }
            memory.escalation_history.append(alert)
            ALERTS.append(alert)
            reply = t(memory.language, "reply_missed_escalate")
        else:
            reply = t(memory.language, "reply_missed_log", medicine=patient.medicine)
        session["stage"] = "CLOSED"

    elif intent == "LATER":
        memory.deferred = True
        reply = t(memory.language, "reply_later")
        session["stage"] = "DEFERRED"

    else:  # UNCLEAR
        session["reask_count"] += 1
        if session["reask_count"] > settings.MAX_CLARIFYING_REASKS:
            reply = t(memory.language, "reply_unclear_giveup")
            session["stage"] = "CLOSED"
        else:
            reply = t(memory.language, "reply_unclear_reask")
            session["stage"] = "AWAIT_CONFIRMATION"

    memory.call_log.append({"at": now_iso(), "heard": text, "intent": intent})
    qdrant_store.save_patient_memory(memory, _event_summary(patient_id, memory))

    speech = _speak(reply, memory.voice_pref, memory.language)
    similar = qdrant_store.find_similar_cases(patient_id, _event_summary(patient_id, memory))

    return CallTurnResponse(
        session_id=session_id,
        stage=session["stage"],
        speaker_text=speech["text"],
        audio_b64=speech["audio_b64"],
        audio_source=speech["audio_source"],
        escalated=escalated,
        persona_name=persona_name(memory.language),
        memory_snapshot=memory,
        similar_cases=similar,
    )


def get_alerts() -> List[dict]:
    return list(reversed(ALERTS))


def get_memory_snapshot(patient_id: str) -> Optional[PatientMemory]:
    return qdrant_store.get_patient_memory(patient_id)
