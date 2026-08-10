# Saathi — Voice Medication Companion

**StarForge 2026 · VoxForge Track · High-Trust Workflows route**

Saathi is a family dashboard where an adult child adds a parent or
grandparent — by typing their details or just photographing the
prescription — and Saathi takes it from there: it calls to confirm
today's medicine was taken, remembers each patient's adherence pattern
in Qdrant, and escalates to a caregiver only when that memory shows a
real risk, not a false alarm. Rime speaks every turn as one of two
consistent companion personas — **Lyra** in English, **नादी (Nadi)**
in Hindi — and the reminder, tone, and escalation decision all depend
on what Qdrant recalls about that specific patient.

> One-sentence claim: *A calm, memory-aware voice companion that never
> starts from zero and never cries wolf.*

---

## 1. Problem

Reminder apps assume the patient can read a screen and tap "confirm."
That fails exactly the users who need it most — elderly patients,
low-literacy patients, and anyone without a smartphone habit. Missed
doses are a silent, high-stakes problem, and families living elsewhere
have no visibility until something goes wrong. And setting up a
reminder in the first place usually means a caregiver typing out a
prescription by hand — friction that means it often just doesn't
happen.

## 2. Solution — five moments

| # | Moment | What happens |
|---|--------|---------------|
| 0 | **Onboard** | A caregiver adds a family member by photographing the prescription (auto-read, then confirmed by a human) or typing it in directly — including fixing a dose time later in one tap. |
| 1 | **Goal** | Scheduled call time arrives; Saathi checks in on today's dose. |
| 2 | **Retrieve** | Qdrant returns this patient's adherence history, language, and any unresolved reminder. |
| 3 | **Speak** | Lyra or Nadi speaks the check-in, tone matched to risk level. |
| 4 | **Act** | The response is logged; if a real pattern emerges, a caregiver alert is prepared. |
| 5 | **Recover** | An interruption, correction, or "call me later" is remembered — the next call resumes correctly, never from zero. |

## 3. Architecture

![Saathi system architecture](docs/architecture.png)

- **Caregiver** adds/edits a family member from the dashboard — by prescription photo or by hand.
- **Vision** (optional, Anthropic) reads a photographed prescription into a suggested medicine + schedule, which the caregiver always reviews and confirms before it's saved — never auto-applied.
- **Patient registry** persists family member profiles (JSON-backed) — this is separate from Qdrant's adherence *memory*, which tracks how the calls actually go over time.
- **Patient** speaks and listens through a browser call-simulator (mic input or typed text) once a call starts.
- **Orchestration** (FastAPI) runs the call state machine and parses the patient's intent.
- **Qdrant** stores adherence memory (payload, filtered by `patient_id`) and powers a real case-similarity vector search.
- **Tools** hold the escalation engine and the caregiver alert log.
- **Rime** (Coda model) speaks every response as Lyra (English) or Nadi (Hindi).

### Call workflow / state machine

![Saathi call workflow](docs/workflow.png)

### Adding a family member

![Saathi onboarding flow](docs/onboarding.png)

The escalation threshold is the deliberate hard problem this project
solves: a single missed dose is logged quietly; only a *pattern* of
consecutive misses (configurable, default 2) creates a caregiver alert.
An interruption or "call later" response is stored as `deferred` and
never counted as a miss — the next call picks up correctly instead of
duplicating or losing state.

## 4. Tech stack

| Piece | Choice | Why |
|---|---|---|
| Voice | **Rime**, Coda model, "Lyra"/"Nadi" personas | Calm, unhurried delivery suited to a trust-sensitive interaction; a consistent named voice per language. |
| Memory / retrieval | **Qdrant** | `patient_memory` collection — payload-filtered adherence memory + vector similarity search for "similar past cases." |
| Photo reading | **Anthropic vision** (optional) | Reads a photographed prescription into a suggested medicine + schedule — always caregiver-reviewed before saving, never auto-applied. |
| Patient registry | **JSON file** (`backend/patient_registry.py`) | Caregiver-added/edited family member profiles — deliberately simple for a prototype, see Limitations. |
| Backend | **FastAPI** (Python) | Call orchestration, intent parsing, escalation logic, patient registry, vision proxy. |
| Frontend | **Vanilla HTML/JS + Tailwind (CDN)** | Family dashboard, add/edit modal (photo + manual), call simulator: mic input (Web Speech API) with a typed-text fallback, live memory panel, alert feed. |

---

## 5. Setup & run

### Requirements
- Python 3.10+
- (Optional but required for the real demo) a [Rime API key](https://docs.rime.ai/docs/introduction)
- No Qdrant account needed — local embedded mode is the default.

### Install

```bash
git clone <this-repo-url>
cd saathi
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set `RIME_API_KEY` to your real key. Optionally set
`ANTHROPIC_API_KEY` too, to enable automatic prescription-photo
reading (the "Upload prescription photo" flow works either way — this
key just fills the fields in automatically instead of by hand).
Everything else has a working default (Qdrant runs in local embedded
mode — no server, no account).

### Run

```bash
uvicorn backend.main:app --reload
```

Open **http://localhost:8000** — pick a demo patient, press **Start
Check-in Call**, and either use the 🎤 button (Chrome/Edge, needs mic
permission) or type a reply like `yes I took it`, `no not yet`, or
`call me later`. Watch the **Qdrant — Patient Memory** panel update
live, and try missing a dose twice in a row to see the escalation
banner and the caregiver alert appear.

If `RIME_API_KEY` is not set, the app still runs end-to-end — the UI
clearly labels every turn as **fallback mode** and speaks it with the
browser's built-in voice instead of Rime. A real `RIME_API_KEY` is
required for the actual submission demo, since VoxForge requires Rime
speech to drive the core experience.

### Language support (English + Hindi)

Each demo patient has a `language` field (`en` or `hi`). Pick the
Hindi patient (**Demo Patient D**) from the dropdown to try it:

- Greetings and replies are generated from Devanagari-script templates
  in `backend/i18n.py`, not transliterated Hindi — this is what a Hindi
  Rime voice expects for correct pronunciation.
- The mic button automatically switches the browser's speech
  recognition to `hi-IN` for Hindi patients, so a spoken reply like
  "नहीं ली" is captured and understood correctly (Chrome returns native
  Devanagari script for `hi-IN`, not Romanized text — `classify_intent`
  in `backend/orchestrator.py` matches both).
- **Before your real demo**, listen to both confirmed Hindi Coda
  voices — `nadi` and `taru` — at <https://app.rime.ai> and pick
  whichever fits better; `RIME_HINDI_SPEAKER` in `.env` defaults to
  `nadi`. Re-check <https://docs.rime.ai/docs/voices> if this ever
  stops working, since Rime's catalog can change over time.
- Adding a third language: add a key to `TEXT` in `backend/i18n.py`
  with the same template names, add its code to `RIME_LANG_CODES` and
  `BROWSER_SPEECH_LANG`, add a demo patient with that `language`. No
  other file needs to change.

### Mic not working?

The 🎤 button uses the browser's built-in `SpeechRecognition` API,
which **only works in Chrome or Edge** — it silently does nothing in
Firefox/Safari. If the mic doesn't work:

1. Confirm you're on Chrome or Edge.
2. Click the 🔒/ⓘ icon in the address bar → make sure **Microphone**
   is set to **Allow** for `localhost:8000`.
3. Check your OS-level microphone permissions for the browser.
4. The **text box works identically** to the mic — it sends the exact
   same text to the exact same backend logic — so you're never blocked
   from testing or demoing the flow while sorting out mic permissions.

### Regenerate the architecture/workflow diagrams

```bash
python3 scripts/render_diagrams.py
```

### Run the tests

```bash
python -m pytest -v
```

Tests run against a temporary, isolated local Qdrant instance (see
`tests/conftest.py`) — they never touch your real `qdrant_data/`
directory and never require a Rime API key. They cover:

- Escalation firing only after the *consecutive*-miss threshold, never on a single miss
- Patient memory isolation (payload filtering by `patient_id`, and rejecting cross-patient session use)
- Recovery: a deferred call doesn't increment `missed_count` and the next greeting reflects it
- A bounded number of clarifying re-asks instead of looping forever
- The app running correctly end-to-end with no Rime key configured
- A full HTTP smoke test through the real FastAPI app (`tests/test_api.py`)

---

## 6. API reference (quick)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Rime/Vision/Qdrant configuration status |
| GET | `/api/patients` | List all family members (demo + caregiver-added) |
| POST | `/api/patients` | Add a family member `{display_name, relation, language, medicine, schedule_time, risk_level}` |
| PATCH | `/api/patients/{id}` | Fix a dose time / edit any field — only fields provided are changed |
| POST | `/api/prescription/parse` | Read a prescription photo `{image_b64, media_type}` → suggested medicine + schedule |
| POST | `/api/call/start` | Begin a check-in call `{patient_id}` |
| POST | `/api/call/respond` | Continue a call `{session_id, patient_id, text}` |
| GET | `/api/patients/{id}/memory` | Current Qdrant memory snapshot |
| GET | `/api/alerts` | Caregiver alerts generated so far |

---

## 7. Limitations

*(what this prototype does **not** prove — see also `docs/`)*

- Calls are simulated through a browser mic/text box, not a real PSTN telephone line — no live IVR/telephony integration yet.
- Caregiver escalation is logged and shown in the UI, not sent as a real SMS/call in this build.
- Intent parsing (`orchestrator.classify_intent`) is rule-based keyword matching, not a proper NLU model or LLM call — good enough for a clear demo script, not for open-ended speech.
- The Qdrant similarity search uses a small deterministic hashed bag-of-words embedding (see `qdrant_store.embed_text`), not a real sentence-embedding model — a placeholder chosen to keep the whole project dependency-free and instantly reproducible. Swap in a real embedding API for production.
- Session state lives in an in-memory Python dict (`orchestrator.SESSIONS`) — it does not survive a server restart and does not scale across multiple worker processes. A real deployment should move this to Redis or similar.
- The patient registry (`backend/patient_registry.py`) is a single local JSON file — fine for a prototype/demo, but has no concurrent-write safety and no migrations. A real deployment needs a proper database.
- Prescription photo reading (`backend/vision_client.py`) is decision support, not a medical device: it suggests a medicine name and schedule from the photo, but the caregiver always sees and can edit those fields before saving — nothing is ever auto-applied without a human looking at it. Without `ANTHROPIC_API_KEY` set, the photo is still shown but every field must be typed in by hand.
- Photo reading was tested on clearly legible prescriptions/labels — handwriting, damaged labels, or non-English/non-Hindi prescriptions have not been specifically evaluated.
- All patient data is synthetic (`backend/data/seed_patients.py`) — no real personal or medical information was used anywhere in this project.
- Speech recognition accuracy across regional accents/dialects has not been rigorously tested.
- Hindi support covers exactly two languages (English, Hindi) with hand-written Devanagari templates for a fixed set of call turns — not open-ended Hindi generation, and not other Indian languages yet. The Hindi Rime voice defaults to `nadi` (confirmed real Coda voice as of 2026-08-09, see README §5) — listen to it alongside the alternative `taru` before your demo and pick by ear.
- Code-switching (mixing Hindi and English mid-sentence, common in real speech) is not specifically handled — `classify_intent` matches known phrases in either language but wasn't tested on mixed-language input.


## 8. Credits

- [Rime](https://docs.rime.ai/docs/introduction) — text-to-speech
- [Qdrant](https://qdrant.tech/documentation/) — vector search & memory
- Reference scaffolding inspected (not copied): [github.com/ankit1khare/rime-voice-agent](https://github.com/ankit1khare/rime-voice-agent)

## License

MIT — see `LICENSE`.
