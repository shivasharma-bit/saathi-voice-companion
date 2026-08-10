"""
Sets up an isolated test environment BEFORE any `backend.*` module is
imported, so tests never touch real dev data (a separate, temporary
Qdrant local-mode directory) and never require a real Rime API key.
"""
import os
import tempfile

os.environ["QDRANT_MODE"] = "local"
os.environ["QDRANT_LOCAL_PATH"] = tempfile.mkdtemp(prefix="saathi_test_qdrant_")
os.environ["ESCALATION_THRESHOLD"] = "2"
os.environ["MAX_CLARIFYING_REASKS"] = "1"
os.environ["RIME_API_KEY"] = ""  # force fallback mode unless a test overrides it

import pytest  # noqa: E402

from backend import orchestrator as orch  # noqa: E402
from backend.data.seed_patients import DEMO_PATIENTS  # noqa: E402
from backend.qdrant_store import new_patient_memory, qdrant_store  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    """Runs before every test: clears in-memory sessions/alerts and
    resets every demo patient's Qdrant memory to a known baseline, so
    tests never depend on execution order."""
    orch.SESSIONS.clear()
    orch.ALERTS.clear()
    for p in DEMO_PATIENTS:
        memory = new_patient_memory(p.patient_id, p.language, p.voice_pref, p.risk_level)
        qdrant_store.save_patient_memory(memory, f"patient {p.patient_id} baseline reset")
    yield
