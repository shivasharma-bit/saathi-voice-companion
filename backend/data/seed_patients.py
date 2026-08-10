"""
Synthetic demo patients only. No real names, no real personal or
medical information — required by the hackathon's data rules for
sensitive domains.
"""
from backend.config import settings
from backend.models import PatientProfile

DEMO_PATIENTS = [
    PatientProfile(
        patient_id="P001",
        display_name="Demo Patient A",
        language="en",
        voice_pref=settings.RIME_DEFAULT_SPEAKER,
        medicine="Amlodipine 5mg",
        schedule_time="09:00",
        risk_level="normal",
    ),
    PatientProfile(
        patient_id="P002",
        display_name="Demo Patient B",
        language="en",
        voice_pref=settings.RIME_DEFAULT_SPEAKER,
        medicine="Metformin 500mg",
        schedule_time="08:00",
        risk_level="elevated",
    ),
    PatientProfile(
        patient_id="P003",
        display_name="Demo Patient C",
        language="en",
        voice_pref=settings.RIME_DEFAULT_SPEAKER,
        medicine="Atorvastatin 10mg",
        schedule_time="21:00",
        risk_level="normal",
    ),
    PatientProfile(
        patient_id="P004",
        display_name="Demo Patient D (Hindi)",
        language="hi",
        # Sourced from RIME_HINDI_SPEAKER in .env — see config.py for
        # why this needs verifying against Rime's current voice list.
        voice_pref=settings.RIME_HINDI_SPEAKER,
        medicine="Metformin 500mg",
        schedule_time="08:30",
        risk_level="elevated",
    ),
]

PATIENTS_BY_ID = {p.patient_id: p for p in DEMO_PATIENTS}
