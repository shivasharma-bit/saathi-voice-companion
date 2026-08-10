# Contributor Guide — Saathi (StarForge 2026, VoxForge track)

This is the single reference doc for anyone joining this project mid-way.
Read this before touching code. If you're pasting context into an AI
assistant (ChatGPT, Claude, Copilot, etc.) to help you work on this repo,
paste this entire file to it first — see "Prompt to give your AI
assistant" at the bottom.

---

## 1. What this project is

**Event:** StarForge Hackathon 2026 (JSS University / E-Cell JSS,
co-presented by Pathway). Round 1 = PPT + 4-min video + public GitHub
repo + working prototype, judged on Innovation, Feasibility, Execution,
Impact, Presentation. Only ~80 of 700 teams advance from Round 1.

**Track chosen:** VoxForge — build a real voice product where Rime
speech is essential and Qdrant plays a meaningful role (not decoration).

**Our idea — "Saathi":** A voice AI that calls a patient (elderly /
low-literacy / living alone) to confirm they took today's medicine.
- **Rime** speaks the check-in and every reply, tone matched to risk.
- **Qdrant** stores each patient's adherence history (a real memory
  payload, filtered by `patient_id`) and does a real vector similarity
  search for "similar past cases."
- **The hard problem we solve deliberately:** a single missed dose is
  just logged quietly. Only a *pattern* of consecutive misses
  (configurable threshold, default 2) creates a caregiver escalation
  alert — so the product never cries wolf. A "call me later" or an
  interruption is remembered (`deferred` flag) and never miscounted as
  a miss — the next call resumes correctly instead of starting over.

**One-sentence pitch:** *A calm, memory-aware voice check-in that
never starts from zero and never cries wolf.*

Read `README.md` and `ARCHITECTURE.md` in the repo root for the full
write-up — this guide is about **how to work on the code**, not a
repeat of the product pitch.

---

## 2. Repo structure (what lives where)

```
saathi/
├── README.md              ← problem, solution, setup/run, API reference, limitations
├── ARCHITECTURE.md         ← deep component walkthrough + sequence diagram
├── CONTRIBUTOR_GUIDE.md    ← this file
├── LICENSE                 ← MIT
├── requirements.txt        ← Python deps
├── .env.example             ← copy to .env, fill in real values — NEVER commit .env
├── .gitignore
├── pytest.ini
├── docs/
│   ├── architecture.png    ← system diagram (regenerate via scripts/render_diagrams.py)
│   └── workflow.png        ← call state-machine diagram
├── backend/
│   ├── main.py              ← FastAPI app + all HTTP routes; also serves frontend/
│   ├── config.py             ← all settings, read from .env (never hardcode secrets)
│   ├── i18n.py               ← ⚠ ALL spoken text lives here (English + Hindi templates)
│   ├── models.py             ← Pydantic schemas (PatientProfile, PatientMemory, etc.)
│   ├── orchestrator.py       ← the call state machine — THE core logic file
│   ├── qdrant_store.py       ← Qdrant memory + case-similarity search
│   ├── rime_client.py        ← Rime TTS API wrapper
│   ├── vision_client.py      ← prescription-photo reading (Anthropic vision, optional)
│   ├── patient_registry.py   ← caregiver add/edit family member (JSON-backed, gitignored data file)
│   └── data/seed_patients.py ← synthetic demo patients (P001–P004)
├── frontend/
│   ├── index.html            ← family dashboard + call simulator + add/edit modal
│   ├── app.js                ← all frontend logic (vanilla JS, no build step)
│   └── styles.css            ← custom CSS layer on top of Tailwind (CDN, loaded in index.html)
├── tests/
│   ├── conftest.py           ← test setup (isolated temp Qdrant + patient store, no real keys needed)
│   ├── test_orchestrator.py  ← core logic tests (escalation, isolation, recovery, Hindi)
│   ├── test_api.py           ← HTTP-level smoke tests
│   ├── test_patient_registry.py ← caregiver add/edit + vision fallback tests
│   └── test_qdrant_store.py  ← vector search tests
└── scripts/
    ├── render_diagrams.py   ← regenerates docs/*.png
    └── run_dev.sh           ← one-command setup+run (Mac/Linux; see §4 for Windows)
```

**Golden rule:** if you're changing what Saathi says out loud, edit
`backend/i18n.py`, never hardcode a string inside `orchestrator.py`.
That file is deliberately the *only* place English/Hindi text lives —
keeping it there is what makes adding a third language a one-file change.

---

## 3. Current status (as of this handoff)

Done and tested:
- [x] Full call flow: greeting → confirmation → escalation logic → recovery
- [x] Qdrant patient memory (payload, isolated by `patient_id`) — real,
      not decorative
- [x] Qdrant case-similarity vector search (`find_similar_cases`)
- [x] Rime TTS integration, with graceful fallback to browser voice
      when `RIME_API_KEY` isn't set
- [x] English + Hindi (Devanagari script) bilingual support —
      greetings, replies, AND intent parsing (recognizes both
      Romanized and native-script Hindi replies)
- [x] Two named companion personas — **Lyra** (English) and
      **नादी/Nadi** (Hindi), shown in the UI and driving Rime's
      default speaker per language
- [x] Family dashboard: add a family member by prescription photo
      (Anthropic vision, graceful manual-entry fallback with no key)
      or by hand, and fix a dose time later in one tap
- [x] Caregiver-added patients are fully real — they persist
      (`backend/data/patients_store.json`, gitignored) and can
      actually receive check-in calls, same as the demo patients
- [x] Browser fallback voice now explicitly picks an installed Hindi
      voice if one exists, and shows a clear warning if it doesn't
      (instead of silently mispronouncing)
- [x] Polished demo-ready UI: pulsing hero mic button while listening,
      live flash-highlight on Qdrant memory panel changes, sliding
      caregiver escalation banner
- [x] 22 automated tests, all passing (`pytest -v`)
- [x] Architecture + workflow diagrams (`docs/*.png`)
- [x] Idea-submission PPT (6-slide official template)

Not done yet / known gaps — **see README §7 "Limitations" for the
full list**, but the most urgent for whoever picks this up next:
1. **No real `RIME_API_KEY` has been set yet.** Without it, every
   call uses the browser's offline fallback voice, not real Rime
   audio. This MUST be set before recording the demo video — get a
   key from rime.ai and put it in `.env` (never commit it).
2. **No `ANTHROPIC_API_KEY` has been set yet either.** Without it,
   prescription photo upload still works as a UI flow, but every
   field must be typed in by hand instead of auto-read from the
   photo. Optional, but worth having for the demo.
3. **`RIME_HINDI_SPEAKER` now defaults to `nadi`**, a confirmed real
   Hindi Coda voice (verified against Rime's live catalog on
   2026-08-09 — the other option is `taru`). Nobody on the team has
   listened to either yet to judge tone/fit for a calm medical
   check-in — do that at <https://app.rime.ai> before the demo and
   switch to `taru` in `.env` if it fits better.

Everything else (telephony, real SMS alerts, proper NLU/LLM intent
parsing, Redis session storage) is intentionally out of scope for the
prototype — see README §7, don't "fix" these unless the team decides
to expand scope.

---

## 4. Getting set up (step by step, Windows-first since that's what the team is using)

### 4.1 Clone the repo
```powershell
git clone https://github.com/shivasharma-bit/saathi-voice-companion.git
cd saathi-voice-companion\saathi
```

### 4.2 Install Python (3.11–3.13 recommended; 3.14 also confirmed working)
Download from [python.org/downloads](https://www.python.org/downloads/).
**On the first installer screen, check "Add python.exe to PATH"** —
this is the single most common setup failure. Close and reopen
PowerShell after installing so it picks up the new PATH.

Verify:
```powershell
python --version
```

### 4.3 Create and activate a virtual environment
```powershell
python -m venv .venv
.venv\Scripts\activate
```
Your prompt should now show `(.venv)` at the start. If activation
fails with an "execution of scripts is disabled" error, run this once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 4.4 Install dependencies
```powershell
pip install -r requirements.txt
```

### 4.5 Set up your local `.env`
```powershell
copy .env.example .env
notepad .env
```
Fill in `RIME_API_KEY` if you have one (ask the team lead). Leave
`QDRANT_MODE=local` — no Qdrant account needed, it runs embedded.
**Never commit your `.env` file** — it's already in `.gitignore`.

### 4.6 Run the tests first, before writing any new code
```powershell
python -m pytest -v
```
All 16 should say `PASSED`. If any fail on a fresh clone, something
is wrong with your environment, not the code — stop and debug this
before writing anything new.

### 4.7 Run the server
```powershell
uvicorn backend.main:app
```
(Deliberately **not** using `--reload` — on Windows it can cause a
"Storage folder already accessed" crash from Qdrant's embedded local
mode locking the same file twice. If you want auto-reload during
active development, delete `qdrant_data/` after any crash before
restarting: `Remove-Item -Recurse -Force .\qdrant_data`.)

Open **http://localhost:8000**. Stop the server with `Ctrl+C` — don't
just close the terminal window, or the Qdrant lock file can get stuck
(see the troubleshooting table below).

---

## 5. Working on the code — collaboration workflow

Since multiple people are now working on the same repo:

### 5.1 Always pull before starting work
```powershell
git checkout main
git pull
```

### 5.2 Work on a branch, not directly on `main`
```powershell
git checkout -b your-name/short-description-of-change
```
Example: `git checkout -b priya/telephony-integration`

### 5.3 Make your changes, then test before committing
```powershell
python -m pytest -v
```
Don't commit if any test fails, and don't remove/weaken a test to
make it pass — fix the actual bug, or ask the team first if you think
the test itself is wrong.

### 5.4 Commit with a clear message
```powershell
git add .
git commit -m "Short description of what changed and why"
```

### 5.5 Push your branch and open a Pull Request
```powershell
git push -u origin your-name/short-description-of-change
```
Then on GitHub: "Compare & pull request" → describe what you changed
→ someone else on the team reviews before merging to `main`. This
avoids two people's changes silently overwriting each other, which is
what happens if everyone pushes straight to `main`.

### 5.6 If you're not comfortable with git branches yet
At minimum, **always run `git pull` before you start editing**, and
**always run the tests before you push**. Talk to whoever's touching
the same files before you start, to avoid conflicting edits.

---

## 6. Problems we already hit and solved (don't rediscover these)

| Symptom | Cause | Fix |
|---|---|---|
| `python : command not found` / opens Microsoft Store | Python not installed, or installed without PATH | Reinstall from python.org, check "Add python.exe to PATH" on the first screen, reopen terminal |
| `cd : Cannot find path` | Wrong folder — the zip/clone often nests one extra folder deep | Run `dir -Name` to see what's actually there before `cd`-ing |
| `.venv\Scripts\activate` fails: "execution of scripts is disabled" | Windows PowerShell security default | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then retry |
| `pip install` fails on some packages | Very new Python version (e.g. 3.14) lacking prebuilt wheels for a dependency | Usually resolves itself as packages catch up; if stuck, install Python 3.12 instead and rebuild the venv |
| `RuntimeError: Storage folder ./qdrant_data is already accessed by another instance` | A previous server process (often from `--reload`) didn't release the Qdrant lock file, usually from closing the terminal instead of Ctrl+C | `Get-Process python* \| Stop-Process -Force`, then `Remove-Item -Recurse -Force .\qdrant_data`, then restart **without** `--reload` |
| Hindi speech sounds like "reading alphabets," not real Hindi | No `RIME_API_KEY` set → using the browser's offline fallback voice, which needs a Hindi voice installed on the OS (most Windows machines don't have one) | Get a real `RIME_API_KEY` (this is the actual fix); to test the fallback path meaningfully, install a Hindi voice via Windows Settings → Time & Language → Speech → Manage voices |
| Mic button does nothing | Only works in Chrome/Edge (uses `webkitSpeechRecognition`); needs mic permission granted for `localhost:8000` | Switch browser, or check the 🔒 icon in the address bar → Microphone → Allow. The text box always works as a fallback — same backend code path either way. |
| `git add .` prints "LF will be replaced by CRLF" warnings | Windows/Linux line-ending differences | Harmless, not an error — safe to ignore |

---

## 7. Where to look for specific things

- **"Why did the call escalate / not escalate?"** → `backend/orchestrator.py`,
  function `handle_response`, the `MISSED` branch. Threshold is
  `settings.ESCALATION_THRESHOLD` (`.env`, default 2 consecutive misses).
- **"How do I add a new phrase Saathi should understand?"** →
  `backend/orchestrator.py`, the `_LATER_PHRASES` / `_MISSED_PHRASES` /
  `_TAKEN_PHRASES` / `_TAKEN_WORDS` / `_MISSED_WORDS` lists near the
  top. Add both English and (if relevant) Devanagari Hindi forms.
- **"How do I change what Saathi says?"** → `backend/i18n.py`, the
  `TEXT` dict. Never edit spoken strings directly in `orchestrator.py`.
- **"How do I add a new demo patient?"** → `backend/data/seed_patients.py`.
  Keep it synthetic — no real names or real medical data, ever
  (hackathon rule for sensitive-domain data).
- **"How does Qdrant actually get used?"** → `backend/qdrant_store.py`.
  Two jobs: `get_patient_memory`/`save_patient_memory` (the payload
  memory) and `find_similar_cases` (the vector search). Read the
  module docstring at the top of the file first.
- **"How does the frontend talk to the backend?"** → `frontend/app.js`,
  functions `onStartCall` and `sendPatientText` — everything goes
  through `/api/call/start` and `/api/call/respond`. See `backend/main.py`
  for the full route list.
- **"I want to add a third language."** → `backend/i18n.py`: add a key
  to `TEXT` with the same template names, add its code to
  `RIME_LANG_CODES` and `BROWSER_SPEECH_LANG`. Then add a demo patient
  with that `language` in `seed_patients.py`, and add Latin/native
  keyword lists to `orchestrator.py`'s intent classifier if the new
  language needs them. No other file should need to change.

---

## 8. Before the demo video / final submission

- [ ] Real `RIME_API_KEY` set and confirmed working (check `/api/health`
      shows `"rime_configured": true`)
- [ ] Listened to `nadi` vs `taru` (both confirmed real Hindi Coda voices) at app.rime.ai and set the better-sounding one in `RIME_HINDI_SPEAKER`
- [ ] Full `pytest -v` run, all passing, screenshot saved as evidence
      for the "Working Proof" submission requirement
- [ ] `README.md` §8 "Team contributions" filled in with real names
- [ ] AI-assisted-coding disclosure filled in (README §8) — describe
      what the team reviewed/tested/modified, per hackathon rules
- [ ] `.env` confirmed NOT present in `git status` / not on GitHub
      (only `.env.example` should be tracked)
- [ ] Demo script walks through the 5 showcase moments (see README §2):
      Goal → Retrieve → Speak → Act → Recover — including missing a
      dose twice to show the escalation banner + alert

---

## 9. Prompt to give your AI assistant

If you're using an AI coding assistant to help you work on this repo,
paste this to it first:

> This is the Saathi project — a StarForge 2026 VoxForge hackathon
> voice AI prototype (medication reminder calls, Rime for speech,
> Qdrant for patient memory + case-similarity search). Read
> `CONTRIBUTOR_GUIDE.md`, `README.md`, and `ARCHITECTURE.md` in the
> repo root fully before suggesting any change. Spoken text lives only
> in `backend/i18n.py` — never hardcode English/Hindi strings
> elsewhere. The core state machine is `backend/orchestrator.py`. Run
> `pytest -v` after any change and do not consider a change complete
> until all tests pass. Preserve the existing escalation-threshold
> logic (only escalate on *consecutive* misses, never a single miss)
> and the `deferred` recovery behavior (a "call later" response must
> never increment `missed_count`) unless explicitly asked to change
> the product logic itself.
