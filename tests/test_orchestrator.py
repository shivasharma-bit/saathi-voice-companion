"""
These tests are the "working proof" for the central claims in the
pitch:

  1. Escalation only fires after the configured threshold of
     CONSECUTIVE missed doses — never on a single miss.
  2. Qdrant payload isolation — one patient's memory can never leak
     into another patient's call, even via session misuse.
  3. Recovery — a deferred ("call later") response does not increment
     missed_count and correctly changes the next greeting, proving the
     next call "starts with context, not from zero".
  4. Unclear responses get a bounded number of re-asks before the call
     closes gracefully, instead of looping forever.
  5. Without a Rime API key, the app still runs end-to-end and clearly
     reports that it used the offline fallback path.
"""
from backend import orchestrator as orch


def test_escalation_only_after_consecutive_threshold():
    patient_id = "P001"  # ESCALATION_THRESHOLD is set to 2 in conftest

    turn0 = orch.start_call(patient_id)
    assert turn0.memory_snapshot.missed_count == 0

    # First miss: logged, but must NOT escalate yet.
    turn1 = orch.handle_response(turn0.session_id, patient_id, "no, not yet")
    assert turn1.memory_snapshot.missed_count == 1
    assert turn1.escalated is False
    assert orch.get_alerts() == []

    # Second consecutive miss (new call, same unresolved pattern): must escalate.
    turn2 = orch.start_call(patient_id)
    turn3 = orch.handle_response(turn2.session_id, patient_id, "no I haven't")
    assert turn3.memory_snapshot.missed_count == 2
    assert turn3.escalated is True
    assert len(orch.get_alerts()) == 1
    assert orch.get_alerts()[0]["patient_id"] == patient_id


def test_taken_resets_missed_count():
    patient_id = "P002"
    t0 = orch.start_call(patient_id)
    t1 = orch.handle_response(t0.session_id, patient_id, "no not yet")
    assert t1.memory_snapshot.missed_count == 1

    t2 = orch.start_call(patient_id)
    t3 = orch.handle_response(t2.session_id, patient_id, "yes, I took it")
    assert t3.memory_snapshot.missed_count == 0
    assert t3.escalated is False


def test_patient_memory_isolation():
    p1, p2 = "P001", "P002"
    t0 = orch.start_call(p1)
    orch.handle_response(t0.session_id, p1, "no not yet")

    # P2's memory must be completely untouched by P1's missed dose.
    p2_memory = orch.get_memory_snapshot(p2)
    assert p2_memory.missed_count == 0

    # A session created for P1 must not be usable against P2's data.
    try:
        orch.handle_response(t0.session_id, p2, "yes")
        assert False, "expected a ValueError for cross-patient session use"
    except ValueError:
        pass

    # The payload-filtered query path also returns only P1's own record.
    from backend.qdrant_store import qdrant_store
    isolated = qdrant_store.isolated_query(p1)
    assert isolated.patient_id == p1


def test_later_defers_without_incrementing_missed_count():
    patient_id = "P003"
    t0 = orch.start_call(patient_id)
    t1 = orch.handle_response(t0.session_id, patient_id, "can you call me later")
    assert t1.stage == "DEFERRED"
    assert t1.memory_snapshot.missed_count == 0
    assert t1.memory_snapshot.deferred is True

    # The next call must acknowledge the deferral, not start from zero.
    t2 = orch.start_call(patient_id)
    assert "call" in t2.speaker_text.lower() or "back" in t2.speaker_text.lower()


def test_unclear_response_has_bounded_reask():
    patient_id = "P001"
    t0 = orch.start_call(patient_id)
    # MAX_CLARIFYING_REASKS is set to 1 in conftest.
    t1 = orch.handle_response(t0.session_id, patient_id, "purple elephant maybe")
    assert t1.stage == "AWAIT_CONFIRMATION"  # first re-ask
    t2 = orch.handle_response(t0.session_id, patient_id, "purple elephant again")
    assert t2.stage == "CLOSED"  # gives up gracefully, does not loop forever
    assert t2.memory_snapshot.missed_count == 0  # ambiguous input never counts as a miss


def test_runs_without_rime_key_and_reports_fallback():
    patient_id = "P002"
    turn = orch.start_call(patient_id)
    assert turn.audio_source == "none"
    assert turn.audio_b64 is None
    # The product still produces a spoken-intent text turn even with no Rime key.
    assert len(turn.speaker_text) > 0


def test_hindi_patient_gets_devanagari_greeting_and_understands_devanagari_reply():
    # P004 is the Hindi demo patient (see backend/data/seed_patients.py).
    patient_id = "P004"
    turn0 = orch.start_call(patient_id)
    assert turn0.memory_snapshot.language == "hi"
    # Greeting must be in Devanagari script, not transliterated Latin
    # text — Rime's Hindi voice expects native script (see backend/i18n.py).
    assert any("\u0900" <= ch <= "\u097F" for ch in turn0.speaker_text)

    # Chrome's hi-IN SpeechRecognition returns native Devanagari, e.g.
    # "नहीं ली" for "didn't take it" — must be classified correctly,
    # not just transliterated Hindi typed in Latin letters.
    turn1 = orch.handle_response(turn0.session_id, patient_id, "नहीं ली")
    assert turn1.memory_snapshot.missed_count == 1
    assert any("\u0900" <= ch <= "\u097F" for ch in turn1.speaker_text)
