"""
Patient registry — where family members (patients) actually live.

Design: `backend/data/seed_patients.py` is the immutable set of demo
patients shipped with the repo (so a fresh clone always has something
to demo with, per the hackathon's synthetic-data rule). This module
adds a small persistence layer on top so a caregiver can add a real
family member or fix a dose time through the UI, and have that survive
a server restart.

Storage: a single JSON file (`backend/data/patients_store.json`,
gitignored — never committed, since a team's local dev edits shouldn't
clash). This is intentionally simple for a prototype — see README
Limitations for why a real deployment would use a proper database
instead of a JSON file (no concurrent-write safety, no migrations).
"""
import json
import os
import uuid
from typing import Dict, List, Optional

from backend.config import settings
from backend.data.seed_patients import DEMO_PATIENTS
from backend.models import PatientProfile

_STORE_PATH = settings.PATIENT_STORE_PATH


def _default_voice(language: str) -> str:
    return settings.RIME_HINDI_SPEAKER if language.lower().startswith("hi") else settings.RIME_DEFAULT_SPEAKER


class PatientRegistry:
    def __init__(self, store_path: str = _STORE_PATH):
        self._store_path = store_path
        self._patients: Dict[str, PatientProfile] = {p.patient_id: p for p in DEMO_PATIENTS}
        self._load()

    def _load(self) -> None:
        """Merge any previously-added/edited patients from disk on top
        of the demo set. A missing or corrupt file is not an error —
        we just start from the demo patients only (fresh clone case)."""
        if not os.path.exists(self._store_path):
            return
        try:
            with open(self._store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.get("patients", []):
                profile = PatientProfile(**entry)
                self._patients[profile.patient_id] = profile
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            # Corrupt store file — don't crash the app over it, just
            # fall back to demo patients only. Worth fixing by hand
            # (or deleting the file) if this ever actually happens.
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
        # Only persist patients that aren't part of the original demo
        # set, OR that have been edited away from their demo defaults —
        # simplest correct approach: persist everything currently in
        # memory except pristine untouched demo patients, so we don't
        # bother writing the same 4 demo rows back out every time.
        demo_ids = {p.patient_id for p in DEMO_PATIENTS}
        to_save = [
            p.model_dump() for pid, p in self._patients.items()
            if pid not in demo_ids or p != next(d for d in DEMO_PATIENTS if d.patient_id == pid)
        ]
        with open(self._store_path, "w", encoding="utf-8") as f:
            json.dump({"patients": to_save}, f, ensure_ascii=False, indent=2)

    def list_patients(self) -> List[PatientProfile]:
        return list(self._patients.values())

    def get(self, patient_id: str) -> Optional[PatientProfile]:
        return self._patients.get(patient_id)

    def add(
        self, display_name: str, relation: str, language: str,
        medicine: str, schedule_time: str, risk_level: str = "normal",
    ) -> PatientProfile:
        patient_id = "U" + uuid.uuid4().hex[:8].upper()  # "U" = user-added, vs "P" for demo patients
        profile = PatientProfile(
            patient_id=patient_id,
            display_name=display_name,
            relation=relation,
            language=language,
            voice_pref=_default_voice(language),
            medicine=medicine,
            schedule_time=schedule_time,
            risk_level=risk_level,
        )
        self._patients[patient_id] = profile
        self._save()
        return profile

    def update(self, patient_id: str, **fields) -> Optional[PatientProfile]:
        existing = self._patients.get(patient_id)
        if not existing:
            return None
        data = existing.model_dump()
        for k, v in fields.items():
            if v is not None:
                data[k] = v
        # If language changed, re-derive the voice to match the new
        # persona (Lyra/Nadi) rather than leaving a stale voice_pref.
        if "language" in fields and fields["language"] is not None:
            data["voice_pref"] = _default_voice(data["language"])
        updated = PatientProfile(**data)
        self._patients[patient_id] = updated
        self._save()
        return updated


patient_registry = PatientRegistry()
