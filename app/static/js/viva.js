/* ═══════════════════════════════════════════════════════
   viva.js – Examination page logic
   Handles: question flow, text/voice answering, feedback display,
   speech synthesis, adaptive difficulty, session sidebar
   ═══════════════════════════════════════════════════════ */
"use strict";

const SESSION_ID = window.SESSION_ID;

// ── Shared utilities ───────────────────────────────────────
function toast(msg, type = "info", duration = 4500) {
  const icons = { success: "✅", error: "❌", info: "ℹ️", warn: "⚠️" };
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type] || "ℹ️"}</span>
                  <span class="toast-msg">${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

function escapeHtml(str) {
  return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function nl2br(str) {
  return escapeHtml(str).replace(/\n/g, "<br/>");
}

// ── State ──────────────────────────────────────────────────
let currentQuestion = null;
let voiceMode = false;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isSpeaking = false;
let speechMuted = false;
let sessionStats = { correct: 0, partial: 0, incorrect: 0, answered: 0, totalScore: 0 };
let questionHistory = [];

// ── DOM refs ───────────────────────────────────────────────
const questionText = document.getElementById("questionText");
const questionTopic = document.getElementById("questionTopic");
const progressLabel = document.getElementById("progressLabel");
const examProgressFill = document.getElementById("examProgressFill");
const difficultyBadge = document.getElementById("difficultyBadge");
const answerTextarea = document.getElementById("answerTextarea");
const charCount = document.getElementById("charCount");
const submitBtn = document.getElementById("submitBtn");
const skipBtn = document.getElementById("skipBtn");
const feedbackPanel = document.getElementById("feedbackPanel");
const answerSection = document.getElementById("answerSection");
const nextQuestionBtn = document.getElementById("nextQuestionBtn");
const finishExamBtn = document.getElementById("finishExamBtn");
const voiceUI = document.getElementById("voiceUI");
const micBtn = document.getElementById("micBtn");
const recordingStatus = document.getElementById("recordingStatus");
const transcriptionArea = document.getElementById("transcriptionArea");
const transcriptionText = document.getElementById("transcriptionText");
const ttsControls = document.getElementById("ttsControls");
const speakQuestionBtn = document.getElementById("speakQuestionBtn");
const muteBtn = document.getElementById("muteBtn");
const historyList = document.getElementById("historyList");
const scoreRing = document.getElementById("scoreRing");
const ringScore = document.getElementById("ringScore");
const sessionInfo = document.getElementById("sessionInfo");
const scoreDisplay = document.getElementById("scoreDisplay");

// ── Character count ────────────────────────────────────────
answerTextarea.addEventListener("input", () => {
  const len = answerTextarea.value.length;
  charCount.textContent = `${len} character${len !== 1 ? "s" : ""}`;
  submitBtn.disabled = len < 5;
});

// ── Load session & first question ─────────────────────────
async function initSession() {
  try {
    const res = await fetch(`/api/sessions/${SESSION_ID}`);
    if (!res.ok) throw new Error("Session not found.");
    const data = await res.json();
    const session = data.session;

    voiceMode = session.voice_mode;
    if (voiceMode) {
      voiceUI.style.display = "flex";
      ttsControls.style.display = "flex";
    }

    sessionInfo.textContent = `${session.difficulty.charAt(0).toUpperCase() + session.difficulty.slice(1)} · ${session.total_questions} Q`;
    sessionInfo.className = `badge badge-${session.difficulty}`;

    await fetchNextQuestion();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function fetchNextQuestion() {
  // Reset UI
  questionText.innerHTML = '<div class="skeleton-text"></div><div class="skeleton-text short"></div>';
  questionTopic.textContent = "";
  feedbackPanel.style.display = "none";
  answerSection.style.display = "flex";
  answerTextarea.value = "";
  charCount.textContent = "0 characters";
  submitBtn.disabled = true;
  transcriptionArea.style.display = "none";
  transcriptionText.value = "";

  try {
    const res = await fetch(`/api/sessions/${SESSION_ID}/question`);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Failed to load question.");
    }

    if (data.exam_complete) {
      showExamComplete();
      return;
    }

    if (!data.question) {
      throw new Error(data.error || "No question returned from server.");
    }

    currentQuestion = data.question;
    renderQuestion(currentQuestion);
  } catch (err) {
    toast("Failed to load question: " + err.message, "error");
    questionText.innerHTML = `<div style="color:var(--error);padding:0.75rem 0;">⚠️ ${escapeHtml(err.message)}</div><button class="btn btn-secondary" onclick="fetchNextQuestion()" style="margin-top:0.75rem">🔄 Retry Question</button>`;
  }
}

function renderQuestion(q) {
  questionText.textContent = q.question_text;
  questionTopic.textContent = q.topic || "";

  const diff = q.difficulty || "medium";
  difficultyBadge.textContent = diff.charAt(0).toUpperCase() + diff.slice(1);
  difficultyBadge.className = `badge badge-${diff}`;

  // Speak question if voice mode
  if (voiceMode && !speechMuted) speakText(q.question_text);

  updateProgressUI();
}

function updateProgressUI() {
  const total = parseInt(sessionInfo.textContent.match(/(\d+) Q/)?.[1] || "10");
  const answered = sessionStats.answered;
  const qNum = answered + 1;

  progressLabel.textContent = `Question ${qNum} / ${total}`;
  examProgressFill.style.width = `${(answered / total) * 100}%`;
}

// ── Submit answer ──────────────────────────────────────────
submitBtn.addEventListener("click", submitAnswer);
skipBtn.addEventListener("click", () => {
  answerTextarea.value = "(Skipped – no answer provided)";
  submitAnswer();
});

async function submitAnswer() {
  const answer = answerTextarea.value.trim();
  if (!answer || answer.length < 2) { toast("Please write an answer first.", "warn"); return; }
  if (!currentQuestion) return;

  submitBtn.querySelector(".btn-text").style.display = "none";
  submitBtn.querySelector(".btn-spinner").style.display = "inline";
  submitBtn.disabled = true;
  skipBtn.disabled = true;

  try {
    const res = await fetch(`/api/sessions/${SESSION_ID}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: currentQuestion.id, answer }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Submission failed.");

    // Update stats
    const fb = data.feedback;
    sessionStats.answered = data.questions_answered;
    sessionStats.totalScore = data.session_score;
    const correctness = fb.correctness || "";
    if (correctness === "correct") sessionStats.correct++;
    else if (correctness === "partial") sessionStats.partial++;
    else sessionStats.incorrect++;

    // Add to history
    questionHistory.push({
      index: data.question_index + 1,
      topic: currentQuestion.topic,
      score: data.score,
      correctness,
      text: currentQuestion.question_text,
    });

    renderFeedback(fb, data);
    updateSidebar(data);

    // Check if exam is complete after this answer
    if (data.questions_answered >= parseInt(sessionInfo.textContent.match(/(\d+) Q/)?.[1] || "10")) {
      nextQuestionBtn.style.display = "none";
      finishExamBtn.style.display = "inline-flex";
    }

    // Speak feedback summary if voice mode
    if (voiceMode && !speechMuted) {
      const summary = correctness === "correct"
        ? "Well done! " + (fb.understood_correctly?.[0] || "")
        : "Here's what to understand: " + (fb.correct_reasoning || "").slice(0, 200);
      speakText(summary);
    }

  } catch (err) {
    toast(err.message, "error");
    submitBtn.querySelector(".btn-text").style.display = "inline";
    submitBtn.querySelector(".btn-spinner").style.display = "none";
    submitBtn.disabled = false;
    skipBtn.disabled = false;
  }
}

// ── Render feedback ────────────────────────────────────────
function renderFeedback(fb, data) {
  answerSection.style.display = "none";
  feedbackPanel.style.display = "flex";

  const score = fb.score || 0;
  const badge = document.getElementById("feedbackScoreBadge");
  badge.textContent = `${score}/100`;
  badge.style.color = score >= 70 ? "var(--success)" : score >= 40 ? "var(--warn)" : "var(--error)";

  const correctnessBadge = document.getElementById("correctnessBadge");
  const c = fb.correctness || "incorrect";
  correctnessBadge.textContent = c.charAt(0).toUpperCase() + c.slice(1);
  correctnessBadge.className = `correctness-badge ${c}`;

  // Understood correctly
  const ul = document.getElementById("understoodList");
  ul.innerHTML = "";
  (fb.understood_correctly || []).forEach(item => {
    ul.innerHTML += `<li>${escapeHtml(item)}</li>`;
  });
  if (!ul.children.length) ul.innerHTML = "<li>No strengths identified for this answer.</li>";

  // Misconceptions
  const ml = document.getElementById("misconceptionsList");
  ml.innerHTML = "";
  (fb.misconceptions || []).forEach(item => {
    ml.innerHTML += `<li>${escapeHtml(item)}</li>`;
  });
  document.getElementById("misconceptionsSection").style.display = ml.children.length ? "flex" : "none";

  // Strengths tab (same as understood)
  document.getElementById("strengthsList").innerHTML = ul.innerHTML;

  // Correct reasoning
  document.getElementById("correctReasoning").innerHTML = nl2br(fb.correct_reasoning || "");

  // Detailed explanation
  const detailedEl = document.getElementById("detailedExplanation");
  const detailedSec = document.getElementById("detailedSection");
  if (fb.detailed_explanation) {
    detailedEl.innerHTML = nl2br(fb.detailed_explanation);
    detailedSec.style.display = "flex";
  } else {
    detailedSec.style.display = "none";
  }

  // Example/Analogy
  document.getElementById("exampleAnalogy").textContent = fb.example_or_analogy || "";

  // Model answer
  document.getElementById("modelAnswer").innerHTML = nl2br(fb.improved_answer || "No model answer provided.");

  // Follow-up
  const fuDiff = fb.follow_up_difficulty || "medium";
  document.getElementById("followUpDiff").textContent = fuDiff.toUpperCase();
  document.getElementById("followUpDiff").className = `follow-up-diff badge-${fuDiff}`;
  document.getElementById("followUpQuestion").textContent = fb.follow_up_question || "";

  // Evidence
  const ev = document.getElementById("evidenceList");
  ev.innerHTML = "";
  (fb.project_evidence || []).forEach(e => {
    ev.innerHTML += `<li>${escapeHtml(e)}</li>`;
  });
  if (!ev.children.length) ev.innerHTML = "<li>No direct evidence cited.</li>";

  // Reset to first tab
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
  document.querySelector(".tab-btn[data-tab='correction']").classList.add("active");
  document.getElementById("tab-correction").classList.add("active");
}

// ── Tab switching ──────────────────────────────────────────
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${tab}`).classList.add("active");
  });
});

// ── Next question / Finish ─────────────────────────────────
nextQuestionBtn.addEventListener("click", fetchNextQuestion);

finishExamBtn.addEventListener("click", () => {
  window.location.href = `/report/${SESSION_ID}`;
});

// ── Sidebar ────────────────────────────────────────────────
function updateSidebar(data) {
  // Score ring
  const avg = data.session_score || 0;
  ringScore.textContent = `${avg}`;
  scoreDisplay.textContent = `Score: ${avg}`;

  const circumference = 201;
  const offset = circumference - (avg / 100) * circumference;
  scoreRing.style.strokeDashoffset = offset;
  scoreRing.style.stroke = avg >= 70 ? "var(--success)" : avg >= 40 ? "var(--warn)" : "var(--error)";

  // Stats
  const total = parseInt(sessionInfo.textContent.match(/(\d+) Q/)?.[1] || "10");
  document.getElementById("statQuestions").textContent = `${data.questions_answered}/${total}`;
  document.getElementById("statCorrect").textContent = sessionStats.correct;
  document.getElementById("statPartial").textContent = sessionStats.partial;
  document.getElementById("statIncorrect").textContent = sessionStats.incorrect;

  // History
  historyList.innerHTML = "";
  questionHistory.slice().reverse().forEach(h => {
    const item = document.createElement("div");
    item.className = `history-item ${h.correctness || ""}`;
    const scoreColor = h.score >= 70 ? "var(--success)" : h.score >= 40 ? "var(--warn)" : "var(--error)";
    item.innerHTML = `
      <span class="history-item-num">Q${h.index}</span>
      <span class="history-item-text" title="${escapeHtml(h.text)}">${escapeHtml(h.topic)}</span>
      <span class="history-item-score" style="color:${scoreColor}">${h.score}</span>`;
    historyList.appendChild(item);
  });
}

// ── Exam complete ──────────────────────────────────────────
function showExamComplete() {
  questionText.textContent = "Examination complete! All questions have been answered.";
  questionTopic.textContent = "COMPLETED";
  answerSection.style.display = "none";
  feedbackPanel.style.display = "flex";

  document.getElementById("feedbackScoreBadge").textContent = `${Math.round(sessionStats.totalScore)}/100`;
  document.getElementById("correctnessBadge").textContent = "Exam Complete";
  document.getElementById("correctnessBadge").className = "correctness-badge correct";
  document.getElementById("tab-correction").innerHTML = `
    <div class="feedback-section">
      <h4>Examination Summary</h4>
      <p class="feedback-text">You've completed all ${sessionStats.answered} questions.
      Click "Finish Exam" to view your full performance report.</p>
    </div>`;
  nextQuestionBtn.style.display = "none";
  finishExamBtn.style.display = "inline-flex";
}

// ── Voice: microphone recording ────────────────────────────
micBtn.addEventListener("click", toggleRecording);

async function toggleRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      uploadAudio();
    };

    mediaRecorder.start(200);
    isRecording = true;
    micBtn.classList.add("recording");
    micBtn.querySelector(".mic-icon").textContent = "⏹";
    recordingStatus.textContent = "Recording… click to stop";

  } catch (err) {
    const msg = err.name === "NotAllowedError"
      ? "Microphone permission denied. Please allow microphone access in your browser."
      : `Could not access microphone: ${err.message}`;
    toast(msg, "error");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  isRecording = false;
  micBtn.classList.remove("recording");
  micBtn.querySelector(".mic-icon").textContent = "🎤";
  recordingStatus.textContent = "Processing audio…";
}

async function uploadAudio() {
  if (!audioChunks.length) {
    recordingStatus.textContent = "";
    toast("No audio recorded.", "warn");
    return;
  }

  const mimeType = mediaRecorder.mimeType || "audio/webm";
  const ext = mimeType.includes("ogg") ? "ogg" : "webm";
  const blob = new Blob(audioChunks, { type: mimeType });
  const formData = new FormData();
  formData.append("audio", blob, `recording.${ext}`);

  recordingStatus.textContent = "Transcribing…";

  try {
    const res = await fetch("/api/speech/transcribe", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || "Transcription failed.");
    }

    const transcript = data.transcript || "";
    if (!transcript.trim()) {
      toast("No speech detected. Please try again.", "warn");
      recordingStatus.textContent = "";
      return;
    }

    // Show editable transcription
    transcriptionArea.style.display = "flex";
    transcriptionText.value = transcript;
    transcriptionText.dispatchEvent(new Event("input"));

    // Sync to main answer box
    answerTextarea.value = transcript;
    answerTextarea.dispatchEvent(new Event("input"));
    recordingStatus.textContent = "✓ Transcribed (edit if needed)";

  } catch (err) {
    toast("Transcription error: " + err.message, "error");
    recordingStatus.textContent = "";
  }
}

// Sync transcription edits to main answer box
transcriptionText.addEventListener("input", () => {
  answerTextarea.value = transcriptionText.value;
  answerTextarea.dispatchEvent(new Event("input"));
});

// ── Speech synthesis (TTS) ─────────────────────────────────
function speakText(text) {
  if (speechMuted || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  utterance.pitch = 1.0;
  utterance.volume = 1.0;
  utterance.onstart = () => { isSpeaking = true; document.getElementById("ttsStatus").textContent = "Speaking…"; };
  utterance.onend = () => { isSpeaking = false; document.getElementById("ttsStatus").textContent = ""; };
  utterance.onerror = () => { isSpeaking = false; document.getElementById("ttsStatus").textContent = ""; };
  window.speechSynthesis.speak(utterance);
}

if (speakQuestionBtn) {
  speakQuestionBtn.addEventListener("click", () => {
    if (currentQuestion) speakText(currentQuestion.question_text);
  });
}

if (muteBtn) {
  muteBtn.addEventListener("click", () => {
    speechMuted = !speechMuted;
    muteBtn.textContent = speechMuted ? "🔕" : "🔇";
    muteBtn.title = speechMuted ? "Unmute" : "Mute speech";
    if (speechMuted) window.speechSynthesis.cancel();
  });
}

// ── Init ───────────────────────────────────────────────────
initSession();
