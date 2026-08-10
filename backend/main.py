"""
Saathi backend — FastAPI application.

Run with:
    uvicorn backend.main:app --reload

Then open http://localhost:8000 — this same server serves the
frontend/ static files, so there's exactly one process to run.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models import (
    AddPatientRequest,
    CallTurnResponse,
    PatientMemory,
    PatientProfile,
    PrescriptionParseRequest,
    PrescriptionParseResponse,
    RespondRequest,
    StartCallRequest,
    UpdatePatientRequest,
)
from backend.orchestrator import get_alerts, get_memory_snapshot, handle_response, start_call
from backend.patient_registry import patient_registry
from backend.rime_client import rime_client
from backend.vision_client import vision_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("saathi.main")

app = FastAPI(title="Saathi — Voice Medication Companion", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype scope — tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "rime_configured": rime_client.is_configured,
        "vision_configured": vision_client.is_configured,
        "qdrant_mode": settings.QDRANT_MODE,
        "escalation_threshold": settings.ESCALATION_THRESHOLD,
    }


@app.get("/api/patients")
def list_patients():
    return [p.model_dump() for p in patient_registry.list_patients()]


@app.post("/api/patients", response_model=PatientProfile)
def add_patient(req: AddPatientRequest):
    """A caregiver (e.g. an adult child) manually adds a family member
    and their dose schedule — the non-photo path."""
    return patient_registry.add(
        display_name=req.display_name,
        relation=req.relation,
        language=req.language,
        medicine=req.medicine,
        schedule_time=req.schedule_time,
        risk_level=req.risk_level,
    )


@app.patch("/api/patients/{patient_id}", response_model=PatientProfile)
def update_patient(patient_id: str, req: UpdatePatientRequest):
    """Fix a dose time, correct a medicine name, etc. — only the
    fields actually provided are changed."""
    updated = patient_registry.update(patient_id, **req.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Unknown patient_id.")
    return updated


@app.post("/api/prescription/parse", response_model=PrescriptionParseResponse)
def parse_prescription(req: PrescriptionParseRequest):
    """Reads a photographed prescription/label and suggests a medicine
    name + schedule for the caregiver to review and confirm — never
    auto-applied without human confirmation. Works (returns
    configured=False) even with no ANTHROPIC_API_KEY set, so the photo
    upload UI is always usable, just without auto-fill."""
    return vision_client.extract(req.image_b64, req.media_type)


@app.get("/api/patients/{patient_id}/memory", response_model=PatientMemory)
def patient_memory(patient_id: str):
    memory = get_memory_snapshot(patient_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="No memory yet for this patient — start a call first.")
    return memory


@app.post("/api/call/start", response_model=CallTurnResponse)
def call_start(req: StartCallRequest):
    try:
        return start_call(req.patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/call/respond", response_model=CallTurnResponse)
def call_respond(req: RespondRequest):
    try:
        return handle_response(req.session_id, req.patient_id, req.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/alerts")
def alerts():
    return get_alerts()


# --- Serve the frontend last, so /api/* routes above take precedence ---
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
