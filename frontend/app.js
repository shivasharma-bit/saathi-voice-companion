// Saathi frontend — family dashboard, add/edit modal (photo + manual),
// call simulator, memory panel with flash-highlight, similar-cases
// panel, sliding escalation alert, and the "orb" — a visual stand-in
// for Saathi's presence during a call. Vanilla JS, no build step.
// Talks to the FastAPI backend over /api/*.

const state = {
  patients: [],
  patientMemories: {},   // patient_id -> last known memory snapshot (for dashboard status + flash diff)
  sessionId: null,
  patientId: null,
  language: "en",
  callActive: false,
  escalationThreshold: 2,
  modalMode: "add",      // "add" | "edit"
  modalEditingId: null,
  photoBase64: null,
  photoMediaType: "image/jpeg",
};

// BCP-47 codes for the browser's SpeechRecognition / speechSynthesis
// APIs — must match backend/i18n.py::BROWSER_SPEECH_LANG.
const BROWSER_SPEECH_LANG = { en: "en-US", hi: "hi-IN" };
const LANGUAGE_LABEL = { en: "English", hi: "हिंदी" };

const el = (id) => document.getElementById(id);
const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function currentPatient() {
  return state.patients.find((p) => p.patient_id === state.patientId);
}

// ============================================================
// The orb — Saathi's visual presence. Three states: idle (gentle
// breathing), listening (patient is speaking, cool blue rim), and
// speaking (Saathi is speaking, warm waveform radiates outward).
// ============================================================
const WAVEFORM_BAR_COUNT = 28;
let waveformBars = [];

function initWaveform() {
  const root = el("waveform");
  root.innerHTML = "";
  waveformBars = [];
  for (let i = 0; i < WAVEFORM_BAR_COUNT; i++) {
    const angle = (360 / WAVEFORM_BAR_COUNT) * i;
    const wrap = document.createElement("div");
    wrap.className = "waveform-bar-wrap";
    wrap.style.setProperty("--angle", `${angle}deg`);
    const bar = document.createElement("div");
    bar.className = "waveform-bar";
    wrap.appendChild(bar);
    root.appendChild(wrap);
    waveformBars.push(bar);
  }
}

function setBarAmplitudePx(i, px) {
  const bar = waveformBars[i];
  if (bar) bar.style.setProperty("--amp", `${Math.max(0, px)}px`);
}

function resetBars() {
  waveformBars.forEach((_, i) => setBarAmplitudePx(i, 0));
}

function setOrbState(mode) {
  // mode: "idle" | "listening" | "speaking"
  const orb = el("orb");
  orb.classList.remove("is-idle", "is-listening", "is-speaking");
  orb.classList.add(`is-${mode}`);
  if (mode !== "speaking") resetBars();

  // The hero mic button's glowing pulse ring mirrors "listening".
  const micBtn = el("micBtn");
  micBtn.classList.toggle("is-active", mode === "listening");
}

// ---- real audio-reactive waveform (used for actual Rime audio) ----
let audioCtx = null;
let analyser = null;
let waveformRAF = null;

function ensureAudioContext() {
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    audioCtx = new AC();
  }
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

function driveWaveformFromAudioElement(audioEl) {
  const ctx = ensureAudioContext();
  if (!ctx) {
    driveSimulatedWaveform();
    return;
  }
  try {
    const source = ctx.createMediaElementSource(audioEl);
    const node = ctx.createAnalyser();
    node.fftSize = 64;
    source.connect(node);
    node.connect(ctx.destination);
    analyser = node;
  } catch (e) {
    console.warn("Audio analyser unavailable, using simulated waveform:", e);
    driveSimulatedWaveform();
    return;
  }

  const data = new Uint8Array(analyser.frequencyBinCount);
  const tick = () => {
    analyser.getByteFrequencyData(data);
    for (let i = 0; i < WAVEFORM_BAR_COUNT; i++) {
      const v = data[i % data.length] / 255;
      setBarAmplitudePx(i, 4 + v * 30);
    }
    waveformRAF = requestAnimationFrame(tick);
  };
  tick();
}

function stopWaveformDrive() {
  if (waveformRAF) {
    cancelAnimationFrame(waveformRAF);
    waveformRAF = null;
  }
  stopSimulatedWaveform();
  resetBars();
}

let simInterval = null;

function driveSimulatedWaveform() {
  if (prefersReducedMotion()) {
    waveformBars.forEach((_, i) => setBarAmplitudePx(i, 14));
    return;
  }
  let envelope = 10;
  simInterval = setInterval(() => {
    envelope += (Math.random() - 0.5) * 6;
    envelope = Math.max(6, Math.min(26, envelope));
    for (let i = 0; i < WAVEFORM_BAR_COUNT; i++) {
      const jitter = Math.random() * 14;
      setBarAmplitudePx(i, envelope * 0.6 + jitter);
    }
  }, 90);
}

function stopSimulatedWaveform() {
  if (simInterval) {
    clearInterval(simInterval);
    simInterval = null;
  }
}

// ============================================================
// init
// ============================================================
async function init() {
  initWaveform();
  await loadHealth();
  await loadFamily();
  await refreshAlerts();
  wireEvents();
  showDashboard();
}

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    state.escalationThreshold = data.escalation_threshold || 2;

    const rimeBadge = el("rimeBadge");
    rimeBadge.textContent = data.rime_configured ? "Rime: live" : "Rime: fallback mode";
    rimeBadge.className = "badge " + (data.rime_configured ? "badge-ok" : "badge-off");

    const visionBadge = el("visionBadge");
    visionBadge.textContent = data.vision_configured ? "Photo Reader: live" : "Photo Reader: manual entry";
    visionBadge.className = "badge " + (data.vision_configured ? "badge-ok" : "badge-off");

    const qBadge = el("qdrantBadge");
    qBadge.textContent = `Qdrant: ${data.qdrant_mode}`;
    qBadge.className = "badge badge-ok";
  } catch (e) {
    console.error(e);
  }
}

// ---------------- family dashboard ----------------
async function loadFamily() {
  const res = await fetch("/api/patients");
  state.patients = await res.json();

  // Pull each patient's current memory (if any) so the dashboard can
  // show a live status chip, not just a static list.
  await Promise.all(
    state.patients.map(async (p) => {
      try {
        const r = await fetch(`/api/patients/${p.patient_id}/memory`);
        if (r.ok) state.patientMemories[p.patient_id] = await r.json();
      } catch (e) { /* no memory yet — fine */ }
    })
  );

  renderFamily();
}

function initials(name) {
  return name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function statusChip(patientId) {
  const mem = state.patientMemories[patientId];
  if (!mem) return { label: "Not checked in yet", cls: "status-new" };
  if (mem.escalation_history && mem.escalation_history.length > 0) {
    return { label: "Needs attention", cls: "status-attention" };
  }
  if (mem.missed_count > 0) return { label: "Missed last dose", cls: "status-attention" };
  return { label: "On track", cls: "status-ontrack" };
}

function renderFamily() {
  const grid = el("familyGrid");
  grid.innerHTML = "";

  state.patients.forEach((p) => {
    const chip = statusChip(p.patient_id);
    const langTag = p.language === "hi" ? "हिंदी · Nadi" : "English · Lyra";
    const card = document.createElement("div");
    card.className = "family-card";
    card.innerHTML = `
      <div class="flex items-start justify-between mb-3">
        <div class="family-avatar">${initials(p.display_name)}</div>
        <span class="family-status-chip ${chip.cls}">${chip.label}</span>
      </div>
      <h3 class="font-bold text-slate-900 text-base leading-tight">${escapeHtml(p.display_name)}</h3>
      <p class="text-xs text-slate-400 font-medium mb-3">${escapeHtml(p.relation || "Family member")} · ${langTag}</p>
      <div class="text-sm text-slate-600 space-y-0.5">
        <p><span class="text-slate-400">Medicine:</span> ${escapeHtml(p.medicine)}</p>
        <p><span class="text-slate-400">Schedule:</span> ${escapeHtml(p.schedule_time)}</p>
      </div>
    `;
    card.addEventListener("click", () => enterCallView(p.patient_id));
    grid.appendChild(card);
  });

  const addCard = document.createElement("div");
  addCard.className = "add-family-card";
  addCard.innerHTML = `
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
    <span>Add family member</span>
  `;
  addCard.addEventListener("click", () => openModal("add"));
  grid.appendChild(addCard);
}

// ---------------- view switching ----------------
function showDashboard() {
  el("dashboardView").classList.remove("hidden");
  el("callView").classList.add("hidden");
  loadFamily();
}

function enterCallView(patientId) {
  state.patientId = patientId;
  const patient = currentPatient() || state.patients.find((p) => p.patient_id === patientId);
  state.language = (patient && patient.language) || "en";

  el("callPatientName").textContent = patient.display_name;
  el("callPatientSub").textContent = `${patient.relation || "Family member"} · ${patient.medicine} · ${patient.schedule_time}`;
  el("personaBadgeText").textContent = patient.language === "hi" ? "नादी (Nadi)" : "Lyra";

  clearTranscript();
  hideEscalationBanner();
  updateCaption("Press Start Check-in Call to begin.", null);
  setOrbState("idle");
  setCallControlsEnabled(false);
  state.callActive = false;
  state.sessionId = null;

  el("dashboardView").classList.add("hidden");
  el("callView").classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
}

function wireEvents() {
  el("homeBtn").addEventListener("click", showDashboard);
  el("backToFamilyBtn").addEventListener("click", showDashboard);
  el("startCallBtn").addEventListener("click", onStartCall);
  el("micBtn").addEventListener("click", onMic);
  el("textForm").addEventListener("submit", onTextSubmit);
  el("editPatientBtn").addEventListener("click", () => openModal("edit", state.patientId));
  el("escalationDismiss").addEventListener("click", hideEscalationBanner);

  // modal wiring
  el("modalClose").addEventListener("click", closeModal);
  el("modalCancel").addEventListener("click", closeModal);
  el("modalSave").addEventListener("click", saveModal);
  el("tabPhotoBtn").addEventListener("click", () => switchModalTab("photo"));
  el("tabManualBtn").addEventListener("click", () => switchModalTab("manual"));
  el("photoInput").addEventListener("change", onPhotoChosen);
  el("parsePhotoBtn").addEventListener("click", onParsePhoto);
  el("patientModal").addEventListener("click", (e) => {
    if (e.target.id === "patientModal") closeModal();
  });
}

// ---------------- transcript helpers ----------------
function clearTranscript() {
  el("transcript").innerHTML = '<p class="transcript-empty">The conversation will appear here as it happens.</p>';
}

function addBubble(who, text) {
  const t = el("transcript");
  const empty = t.querySelector(".transcript-empty");
  if (empty) empty.remove();
  const div = document.createElement("div");
  div.className = `bubble bubble-${who === "Saathi" ? "saathi" : "patient"}`;
  div.innerHTML = `${escapeHtml(text)}<div class="bubble-meta">${who}</div>`;
  t.appendChild(div);
  t.scrollTop = t.scrollHeight;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ---------------- caption (the live line under the orb) ----------------
function updateCaption(text, who) {
  el("caption").textContent = text;
  const meta = el("captionMeta");
  if (!who) { meta.innerHTML = "&nbsp;"; return; }
  const langLabel = LANGUAGE_LABEL[state.language] || "English";
  const whoClass = who === "Saathi" ? "who-saathi" : "who-patient";
  const personaOrPatient = who === "Saathi" ? el("personaBadgeText").textContent : "Patient";
  meta.innerHTML = `<span class="${whoClass}">${personaOrPatient}</span> · ${langLabel}`;
}

// ---------------- audio playback ----------------
function playTurn(turn) {
  if (turn.persona_name) el("personaBadgeText").textContent = turn.persona_name;
  updateCaption(turn.speaker_text, "Saathi");
  setOrbState("speaking");

  if (turn.audio_source === "rime" && turn.audio_b64) {
    el("fallbackNotice").classList.add("hidden");
    el("fallbackVoiceWarning").classList.add("hidden");
    const audio = new Audio("data:audio/wav;base64," + turn.audio_b64);
    audio.addEventListener("ended", () => { stopWaveformDrive(); setOrbState("idle"); });
    audio.addEventListener("error", () => { stopWaveformDrive(); setOrbState("idle"); });
    audio.play()
      .then(() => driveWaveformFromAudioElement(audio))
      .catch((e) => {
        console.warn("Audio playback blocked:", e);
        stopWaveformDrive();
        setOrbState("idle");
      });
  } else {
    el("fallbackNotice").classList.remove("hidden");
    speakWithBrowserFallback(turn.speaker_text);
  }
}

function speakWithBrowserFallback(text) {
  if (!("speechSynthesis" in window)) { setOrbState("idle"); return; }
  const targetLang = BROWSER_SPEECH_LANG[state.language] || "en-US";
  const targetPrefix = targetLang.split("-")[0];

  const pickVoiceAndSpeak = () => {
    const voices = window.speechSynthesis.getVoices();
    const match = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(targetPrefix));
    const warningEl = el("fallbackVoiceWarning");

    if (targetPrefix !== "en" && !match) {
      warningEl.textContent =
        `No ${targetPrefix.toUpperCase()} voice is installed on this device, so the offline fallback ` +
        `can't speak it correctly. Add a Hindi voice in Windows (Settings → Time & Language → Speech → ` +
        `Manage voices → Add voices → Hindi), or set a real RIME_API_KEY in .env for correct Hindi speech.`;
      warningEl.classList.remove("hidden");
    } else {
      warningEl.classList.add("hidden");
    }

    const u = new SpeechSynthesisUtterance(text);
    u.lang = targetLang;
    if (match) u.voice = match;
    u.onstart = () => driveSimulatedWaveform();
    u.onend = () => { stopWaveformDrive(); setOrbState("idle"); };
    u.onerror = () => { stopWaveformDrive(); setOrbState("idle"); };
    window.speechSynthesis.speak(u);
  };

  if (window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.onvoiceschanged = pickVoiceAndSpeak;
  } else {
    pickVoiceAndSpeak();
  }
}

// ---------------- memory / similar cases / alerts rendering ----------------
const MEMORY_ROW_LABELS = {
  patient_id: "patient_id",
  risk_level: "risk_level",
  missed_count: "missed_count",
  deferred: "deferred",
  last_confirmed: "last_confirmed",
  last_missed: "last_missed",
  escalation_history: "escalation_history",
};

function renderMemory(mem) {
  const box = el("memoryBox");
  const previous = state.patientMemories[mem.patient_id] || {};
  state.patientMemories[mem.patient_id] = mem;

  const rows = [
    ["patient_id", mem.patient_id],
    ["risk_level", mem.risk_level],
    ["missed_count", mem.missed_count],
    ["deferred", String(mem.deferred)],
    ["last_confirmed", mem.last_confirmed || "—"],
    ["last_missed", mem.last_missed || "—"],
    ["escalation_history", `${mem.escalation_history.length} alert(s)`],
  ];

  box.innerHTML = rows
    .map(([k, v]) => `<div class="memory-row" data-key="${k}"><span class="memory-key">${MEMORY_ROW_LABELS[k]}</span><span class="memory-val">${v}</span></div>`)
    .join("");

  // Flash-highlight any row whose value actually changed since the
  // last render, so a live memory update is visually unmistakable —
  // this is the moment the demo relies on judges actually seeing.
  const prevValues = {
    patient_id: previous.patient_id,
    risk_level: previous.risk_level,
    missed_count: previous.missed_count,
    deferred: previous.deferred !== undefined ? String(previous.deferred) : undefined,
    last_confirmed: previous.last_confirmed || "—",
    last_missed: previous.last_missed || "—",
    escalation_history: previous.escalation_history ? `${previous.escalation_history.length} alert(s)` : undefined,
  };
  rows.forEach(([k, v]) => {
    if (prevValues[k] === undefined) return; // first render for this patient — nothing to diff against
    if (String(prevValues[k]) !== String(v)) {
      const rowEl = box.querySelector(`.memory-row[data-key="${k}"]`);
      if (!rowEl) return;
      const isGoodChange = k === "missed_count" && Number(v) < Number(prevValues[k] ?? 0);
      rowEl.classList.remove("flash-changed", "flash-good");
      // restart the animation even if the same class was just applied
      void rowEl.offsetWidth;
      rowEl.classList.add("flash-changed");
      if (isGoodChange) rowEl.classList.add("flash-good");
    }
  });
}

function renderSimilar(cases) {
  const box = el("similarBox");
  if (!cases || cases.length === 0) {
    box.innerHTML = `<p class="muted">No similar cases yet in Qdrant.</p>`;
    return;
  }
  box.innerHTML = cases
    .map(
      (c) => `<div class="case-item">
        <b>${c.anon_id}</b> · similarity ${c.similarity}<br/>
        <span class="muted" style="color:#94a3b8">risk ${c.risk_level} · missed ${c.missed_count} · ${c.escalated ? "escalated" : "not escalated"}</span>
      </div>`
    )
    .join("");
}

async function refreshAlerts() {
  const res = await fetch("/api/alerts");
  const alerts = await res.json();
  const box = el("alertsBox");
  if (!alerts.length) {
    box.innerHTML = `<p class="muted">No alerts yet.</p>`;
    return;
  }
  box.innerHTML = alerts
    .map(
      (a) => `<div class="alert-item">
        <b>${escapeHtml(a.display_name)}</b> — ${escapeHtml(a.reason)}<br/>
        <span class="muted" style="color:#94a3b8">${new Date(a.created_at).toLocaleString()}</span>
      </div>`
    )
    .join("");
}

// ---------------- escalation banner ----------------
let escalationTimer = null;
function showEscalationBanner() {
  const banner = el("escalationBanner");
  banner.classList.add("is-visible");
  clearTimeout(escalationTimer);
  escalationTimer = setTimeout(hideEscalationBanner, 9000);
}
function hideEscalationBanner() {
  el("escalationBanner").classList.remove("is-visible");
  clearTimeout(escalationTimer);
}

// ---------------- call flow ----------------
function setCallControlsEnabled(enabled) {
  el("micBtn").disabled = !enabled;
  el("textInput").disabled = !enabled;
  el("sendBtn").disabled = !enabled;
}

async function onStartCall() {
  const patientId = state.patientId;
  clearTranscript();
  hideEscalationBanner();

  const res = await fetch("/api/call/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: patientId }),
  });
  if (!res.ok) {
    addBubble("Saathi", "(error starting call — check server logs)");
    return;
  }
  const turn = await res.json();
  state.sessionId = turn.session_id;
  state.callActive = true;

  addBubble("Saathi", turn.speaker_text);
  playTurn(turn);
  renderMemory(turn.memory_snapshot);
  renderSimilar(turn.similar_cases);
  setCallControlsEnabled(true);
}

async function sendPatientText(text) {
  if (!state.callActive || !state.sessionId) return;
  addBubble("Patient", text);
  updateCaption(text, "Patient");

  const res = await fetch("/api/call/respond", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId, patient_id: state.patientId, text }),
  });
  if (!res.ok) {
    addBubble("Saathi", "(error processing response — check server logs)");
    setOrbState("idle");
    return;
  }
  const turn = await res.json();
  addBubble("Saathi", turn.speaker_text);
  playTurn(turn);
  renderMemory(turn.memory_snapshot);
  renderSimilar(turn.similar_cases);

  if (turn.escalated) {
    showEscalationBanner();
    await refreshAlerts();
  }

  if (turn.stage === "CLOSED" || turn.stage === "DEFERRED") {
    state.callActive = false;
    setCallControlsEnabled(false);
  }
}

function onTextSubmit(e) {
  e.preventDefault();
  const input = el("textInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendPatientText(text);
}

// ---------------- mic (Web Speech API, optional) ----------------
function onMic() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition isn't supported in this browser. Please use the text box instead.");
    return;
  }
  const recog = new SpeechRecognition();
  recog.lang = BROWSER_SPEECH_LANG[state.language] || "en-US";
  recog.interimResults = false;
  recog.maxAlternatives = 1;

  const micBtn = el("micBtn");
  micBtn.disabled = true;
  setOrbState("listening");
  updateCaption("Listening…", "Patient");

  recog.onresult = (event) => {
    const text = event.results[0][0].transcript;
    sendPatientText(text);
  };
  recog.onerror = () => {
    setOrbState("idle");
    alert("Couldn't capture audio — please use the text box instead.");
  };
  recog.onend = () => {
    micBtn.disabled = !state.callActive;
  };
  recog.start();
}

// ============================================================
// Add / Edit family member modal
// ============================================================
function openModal(mode, patientId) {
  state.modalMode = mode;
  state.modalEditingId = patientId || null;
  state.photoBase64 = null;

  el("modalTitle").textContent = mode === "edit" ? "Fix dose time / details" : "Add a family member";
  el("photoPreview").classList.add("hidden");
  el("photoDropzoneText").classList.remove("hidden");
  el("parsePhotoBtn").disabled = true;
  el("parseStatus").classList.add("hidden");
  el("visionNote").classList.add("hidden");
  el("photoInput").value = "";

  if (mode === "edit" && patientId) {
    const p = state.patients.find((x) => x.patient_id === patientId);
    if (p) {
      el("fieldName").value = p.display_name;
      el("fieldRelation").value = p.relation || "Family member";
      el("fieldLanguage").value = p.language;
      el("fieldMedicine").value = p.medicine;
      el("fieldSchedule").value = p.schedule_time;
      el("fieldRisk").value = p.risk_level;
    }
    switchModalTab("manual");
  } else {
    el("fieldName").value = "";
    el("fieldRelation").value = "Mother";
    el("fieldLanguage").value = "en";
    el("fieldMedicine").value = "";
    el("fieldSchedule").value = "";
    el("fieldRisk").value = "normal";
    switchModalTab("photo");
  }

  el("patientModal").classList.remove("hidden");
}

function closeModal() {
  el("patientModal").classList.add("hidden");
}

function switchModalTab(tab) {
  const isPhoto = tab === "photo";
  el("tabPhoto").classList.toggle("hidden", !isPhoto);
  el("tabManual").classList.toggle("hidden", isPhoto);
  el("tabPhotoBtn").classList.toggle("modal-tab-active", isPhoto);
  el("tabManualBtn").classList.toggle("modal-tab-active", !isPhoto);
}

function onPhotoChosen(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  state.photoMediaType = file.type || "image/jpeg";

  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = reader.result; // "data:image/jpeg;base64,...."
    state.photoBase64 = dataUrl.split(",")[1];
    el("photoPreview").src = dataUrl;
    el("photoPreview").classList.remove("hidden");
    el("photoDropzoneText").classList.add("hidden");
    el("parsePhotoBtn").disabled = false;
  };
  reader.readAsDataURL(file);
}

async function onParsePhoto() {
  if (!state.photoBase64) return;
  const statusEl = el("parseStatus");
  statusEl.textContent = "Reading photo…";
  statusEl.classList.remove("hidden");
  el("parsePhotoBtn").disabled = true;

  try {
    const res = await fetch("/api/prescription/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_b64: state.photoBase64, media_type: state.photoMediaType }),
    });
    const data = await res.json();

    if (data.medicine) el("fieldMedicine").value = data.medicine;
    if (data.schedule_time) el("fieldSchedule").value = data.schedule_time;

    const noteEl = el("visionNote");
    if (data.confidence_note) {
      noteEl.textContent = data.confidence_note;
      noteEl.classList.remove("hidden");
    } else if (!data.configured) {
      noteEl.textContent = "Automatic photo reading isn't configured — please check the fields below against the photo.";
      noteEl.classList.remove("hidden");
    } else {
      noteEl.classList.add("hidden");
    }

    statusEl.classList.add("hidden");
    switchModalTab("manual");
  } catch (e) {
    statusEl.textContent = "Couldn't read the photo — please fill in the fields manually.";
  } finally {
    el("parsePhotoBtn").disabled = false;
  }
}

async function saveModal() {
  const payload = {
    display_name: el("fieldName").value.trim(),
    relation: el("fieldRelation").value,
    language: el("fieldLanguage").value,
    medicine: el("fieldMedicine").value.trim(),
    schedule_time: el("fieldSchedule").value.trim(),
    risk_level: el("fieldRisk").value,
  };
  if (!payload.display_name || !payload.medicine || !payload.schedule_time) {
    alert("Please fill in at least name, medicine, and schedule.");
    return;
  }

  const saveBtn = el("modalSave");
  saveBtn.disabled = true;
  try {
    let res;
    if (state.modalMode === "edit" && state.modalEditingId) {
      res = await fetch(`/api/patients/${state.modalEditingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      res = await fetch("/api/patients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    if (!res.ok) {
      alert("Couldn't save — please check the fields and try again.");
      return;
    }
    const saved = await res.json();
    closeModal();

    if (state.modalMode === "edit" && state.modalEditingId === state.patientId) {
      // We were editing the patient currently open in the call view —
      // refresh that header in place instead of forcing a navigation.
      await loadFamily();
      enterCallView(state.patientId);
    } else {
      await loadFamily();
      if (state.modalMode === "add") enterCallView(saved.patient_id);
    }
  } finally {
    saveBtn.disabled = false;
  }
}

init();
