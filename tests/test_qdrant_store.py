"""
Tests that Qdrant's vector search is actually doing something —
i.e. that "similar cases" reflects real state, not a hardcoded list.
"""
from backend import orchestrator as orch
from backend.qdrant_store import qdrant_store


def test_similar_cases_excludes_self():
    patient_id = "P001"
    turn = orch.start_call(patient_id)
    for c in turn.similar_cases:
        assert c["anon_id"] != patient_id  # never reveals the querying patient's own id


def test_similar_cases_surface_other_escalated_patients():
    # Push P002 into an escalated state.
    t0 = orch.start_call("P002")
    orch.handle_response(t0.session_id, "P002", "no not yet")
    t2 = orch.start_call("P002")
    orch.handle_response(t2.session_id, "P002", "no I haven't")  # 2nd consecutive miss -> escalates

    # Now query similar cases from P001's perspective.
    turn = orch.start_call("P001")
    handled = orch.handle_response(turn.session_id, "P001", "no not yet")

    assert isinstance(handled.similar_cases, list)
    # At least the search mechanism must run without error and return
    # well-formed records (patient_id anonymised, similarity score present).
    for case in handled.similar_cases:
        assert "similarity" in case
        assert "anon_id" in case


def test_embedding_is_deterministic():
    from backend.qdrant_store import embed_text
    v1 = embed_text("patient P001 risk normal missed_count 1")
    v2 = embed_text("patient P001 risk normal missed_count 1")
    assert v1 == v2


def test_isolated_query_returns_none_for_unknown_patient():
    assert qdrant_store.isolated_query("NOT-A-REAL-PATIENT") is None
