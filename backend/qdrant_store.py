"""
Qdrant is the memory layer of Saathi. It has two jobs, both of which
change what the product actually does — not decoration:

1. PATIENT MEMORY (payload lookup, filtered by patient_id)
   Every call reads and writes a payload: risk_level, missed_count,
   last_confirmed, escalation_history, etc. This is what lets the
   greeting change ("did you take today's dose?" vs a routine
   reminder) and what the escalation threshold check is based on.
   Payload filtering by patient_id is what keeps one patient's memory
   from ever leaking into another patient's call — this is tested in
   tests/test_orchestrator.py::test_patient_memory_isolation.

2. CASE SIMILARITY SEARCH (vector search)
   Each call event is embedded as a short text summary and stored as
   a vector. `find_similar_cases()` does a real Qdrant nearest-neighbour
   search so a caregiver dashboard could show "3 similar past cases"
   for context. The embedding used here is a small deterministic
   hashed bag-of-words vector (see `embed_text`) — a lightweight
   placeholder chosen so the whole project runs with zero external ML
   dependencies. A production deployment should swap this for a real
   sentence-embedding API (OpenAI, Cohere, etc.) — see README limitations.

QDRANT_MODE=local (default) uses Qdrant's embedded on-disk mode, so the
whole app runs with zero cloud account / zero network dependency. Set
QDRANT_MODE=cloud with QDRANT_URL / QDRANT_API_KEY to point at a real
Qdrant Cloud cluster for the actual hackathon deployment.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from backend.config import settings
from backend.models import PatientMemory

VECTOR_DIM = settings.QDRANT_VECTOR_SIZE


def embed_text(text: str, dim: int = VECTOR_DIM) -> List[float]:
    """Deterministic hashed bag-of-words embedding (MVP placeholder —
    see module docstring). Same text always maps to the same vector,
    which is all that's needed to demonstrate real nearest-neighbour
    retrieval in Qdrant without pulling in a heavy ML dependency."""
    vec = [0.0] * dim
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _patient_point_id(patient_id: str) -> str:
    # Stable UUID derived from patient_id so upserts overwrite the same point.
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"saathi-patient-{patient_id}"))


class QdrantStore:
    def __init__(self):
        if settings.QDRANT_MODE == "cloud" and settings.QDRANT_URL:
            self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
        else:
            # Embedded local mode — no server, no account, fully offline.
            self.client = QdrantClient(path=settings.QDRANT_LOCAL_PATH)
        self.collection = settings.QDRANT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=VECTOR_DIM, distance=qm.Distance.COSINE),
            )

    # ---------------- patient memory (payload) ----------------

    def get_patient_memory(self, patient_id: str) -> Optional[PatientMemory]:
        point_id = _patient_point_id(patient_id)
        results = self.client.retrieve(collection_name=self.collection, ids=[point_id], with_payload=True)
        if not results:
            return None
        return PatientMemory(**results[0].payload)

    def save_patient_memory(self, memory: PatientMemory, event_summary_text: str):
        """Upserts the patient's memory payload AND a vector representing
        the latest call event, so case-similarity search reflects the
        current state. `event_summary_text` is a short synthetic
        description like 'patient P002 missed dose risk elevated
        consecutive misses 2' — never real free-text patient speech,
        keeping this safe to store even in a shared collection."""
        point_id = _patient_point_id(memory.patient_id)
        vector = embed_text(event_summary_text)
        self.client.upsert(
            collection_name=self.collection,
            points=[qm.PointStruct(id=point_id, vector=vector, payload=memory.model_dump())],
        )

    def isolated_query(self, patient_id: str) -> Optional[PatientMemory]:
        """Fetches memory using an explicit payload filter on patient_id
        (rather than relying on the point-id lookup) — this is the code
        path that proves isolation: a query filtered to patient A can
        never return patient B's payload, even if IDs collided."""
        result = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=qm.Filter(
                must=[qm.FieldCondition(key="patient_id", match=qm.MatchValue(value=patient_id))]
            ),
            limit=1,
            with_payload=True,
        )
        points, _ = result
        if not points:
            return None
        return PatientMemory(**points[0].payload)

    # ---------------- case similarity search ----------------

    def find_similar_cases(self, patient_id: str, event_summary_text: str, top_k: int = 3) -> List[dict]:
        """Real Qdrant vector search: returns the top-k most similar
        recent call events across OTHER patients, anonymised for the
        demo (Patient A/B/C instead of real IDs).

        Uses `query_points` (current recommended Qdrant API) with a
        fallback to the older `search` method, so this works across a
        wider range of qdrant-client versions without configuration."""
        vector = embed_text(event_summary_text)
        limit = top_k + 1  # +1 in case the patient's own point is the top hit
        try:
            response = self.client.query_points(
                collection_name=self.collection, query=vector, limit=limit, with_payload=True,
            )
            hits = response.points
        except AttributeError:
            hits = self.client.search(
                collection_name=self.collection, query_vector=vector, limit=limit, with_payload=True,
            )
        out = []
        anon_map = {}
        next_letter = ord("A")
        for hit in hits:
            payload = hit.payload or {}
            pid = payload.get("patient_id")
            if pid == patient_id:
                continue
            if pid not in anon_map:
                anon_map[pid] = f"Patient {chr(next_letter)}"
                next_letter += 1
            out.append({
                "anon_id": anon_map[pid],
                "similarity": round(float(hit.score), 3),
                "risk_level": payload.get("risk_level"),
                "missed_count": payload.get("missed_count"),
                "escalated": len(payload.get("escalation_history", [])) > 0,
            })
            if len(out) >= top_k:
                break
        return out


qdrant_store = QdrantStore()


def new_patient_memory(patient_id: str, language: str, voice_pref: str, risk_level: str) -> PatientMemory:
    return PatientMemory(
        patient_id=patient_id,
        language=language,
        voice_pref=voice_pref,
        risk_level=risk_level,
        missed_count=0,
        last_confirmed=None,
        last_missed=None,
        deferred=False,
        escalation_history=[],
        call_log=[],
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
