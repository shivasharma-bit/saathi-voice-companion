"""
Pydantic schemas shared between the API layer and the orchestrator.
Keeping these separate from orchestrator.py makes the API contract
explicit and easy to test independently of the business logic.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    patient_id: str
    display_name: str
    relation: str = "Family member"  # e.g. "Mother", "Father", "Grandmother" — shown on the family dashboard card
    language: str = "en"
    voice_pref: str = "celeste"
    medicine: str
    schedule_time: str
    risk_level: Literal["normal", "elevated"] = "normal"


class PatientMemory(BaseModel):
    """The full shape of what we store in / read from Qdrant's payload
    for a given patient. This is the object judges should see change
    live during the demo — that's what makes Qdrant's role visible."""
    patient_id: str
    language: str = "en"
    voice_pref: str = "celeste"
    risk_level: str = "normal"
    missed_count: int = 0
    last_confirmed: Optional[str] = None
    last_missed: Optional[str] = None
    deferred: bool = False
    escalation_history: List[dict] = Field(default_factory=list)
    call_log: List[dict] = Field(default_factory=list)


class StartCallRequest(BaseModel):
    patient_id: str


class RespondRequest(BaseModel):
    session_id: str
    patient_id: str
    text: str


class CallTurnResponse(BaseModel):
    session_id: str
    stage: str
    speaker_text: str
    audio_b64: Optional[str] = None
    audio_source: Literal["rime", "none"] = "none"
    escalated: bool = False
    persona_name: str = "Lyra"
    memory_snapshot: PatientMemory
    similar_cases: List[dict] = Field(default_factory=list)


class Alert(BaseModel):
    alert_id: str
    patient_id: str
    display_name: str
    created_at: str
    reason: str
    missed_count: int


class AddPatientRequest(BaseModel):
    """A caregiver (e.g. an adult child) manually adding or fixing a
    family member's profile and dose schedule — the non-photo path."""
    display_name: str
    relation: str = "Family member"
    language: str = "en"
    medicine: str
    schedule_time: str
    risk_level: Literal["normal", "elevated"] = "normal"


class UpdatePatientRequest(BaseModel):
    """Partial update — only fields a caregiver actually changed are
    sent; everything else is left as-is. Used for 'fix the dose time'
    style edits without re-entering the whole profile."""
    display_name: Optional[str] = None
    relation: Optional[str] = None
    language: Optional[str] = None
    medicine: Optional[str] = None
    schedule_time: Optional[str] = None
    risk_level: Optional[Literal["normal", "elevated"]] = None


class PrescriptionParseRequest(BaseModel):
    image_b64: str
    media_type: str = "image/jpeg"


class PrescriptionParseResponse(BaseModel):
    configured: bool  # False if ANTHROPIC_API_KEY isn't set — UI should show manual entry
    medicine: Optional[str] = None
    schedule_time: Optional[str] = None
    confidence_note: Optional[str] = None
    raw_notes: Optional[str] = None
