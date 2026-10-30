/* ═══════════════════════════════════════════════════════
   report.js – Final performance report page
   ═══════════════════════════════════════════════════════ */
"use strict";

const SESSION_ID = window.SESSION_ID;

function toast(msg, type = "info", duration = 4000) {
  const icons = { success: "✅", error: "❌", info: "ℹ️", warn: "⚠️" };
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type]||"ℹ️"}</span><span class="toast-msg">${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

function escapeHtml(str) {
  return String(str||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function makeList(container, items, emptyMsg) {
  if (!items || !items.length) {
    container.innerHTML = `<li style="color:var(--text-muted);font-size:0.9rem">${emptyMsg}</li>`;
    return;
  }
  container.innerHTML = items.map(i => `<li>${escapeHtml(i)}</li>`).join("");
}

async function loadReport() {
  try {
    const res = await fetch(`/api/sessions/${SESSION_ID}/report`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load report.");
    renderReport(data);
  } catch (err) {
    toast(err.message, "error");
    document.getElementById("bigScore").textContent = "Error";
    document.getElementById("execSummary").textContent = err.message;
  }
}

function renderReport(data) {
  const report = data.report || {};
  const session = data.session || {};
  const questions = data.questions || [];

  // Hero
  const score = report.overall_score || session.overall_score || 0;
  document.getElementById("bigScore").textContent = `${Math.round(score)}`;
  document.getElementById("gradeBadge").textContent = report.grade || gradeFromScore(score);
  document.getElementById("reportTitle").textContent = `Performance Report`;
  document.getElementById("execSummary").textContent = report.executive_summary || "";

  // Stats
  const correct = questions.filter(q => q.correctness === "correct").length;
  const partial = questions.filter(q => q.correctness === "partial").length;
  const incorrect = questions.filter(q => q.correctness === "incorrect").length;
  document.getElementById("reportQuestions").textContent = questions.length;
  document.getElementById("reportCorrect").textContent = correct;
  document.getElementById("reportPartial").textContent = partial;
  document.getElementById("reportIncorrect").textContent = incorrect;

  // Topic performance
  const topicContainer = document.getElementById("topicPerformance");
  const topics = report.topic_performance || [];
  if (topics.length) {
    topicContainer.innerHTML = topics.map(t => {
      const sc = Math.round(t.score || 0);
      const cls = t.assessment === "strong" ? "strong" : t.assessment === "adequate" ? "adequate" : "weak";
      return `<div class="topic-row">
        <div class="topic-label">
          <span class="topic-name">${escapeHtml(t.topic)}</span>
          <span class="topic-score">${sc}/100</span>
        </div>
        <div class="topic-bar"><div class="topic-bar-fill ${cls}" style="width:${sc}%"></div></div>
      </div>`;
    }).join("");
  } else {
    // Build from questions if LLM didn't return topics
    const topicMap = {};
    questions.forEach(q => {
      if (!topicMap[q.topic]) topicMap[q.topic] = [];
      topicMap[q.topic].push(q.score || 0);
    });
    topicContainer.innerHTML = Object.entries(topicMap).map(([topic, scores]) => {
      const avg = scores.reduce((a,b)=>a+b,0)/scores.length;
      const cls = avg >= 70 ? "strong" : avg >= 40 ? "adequate" : "weak";
      return `<div class="topic-row">
        <div class="topic-label">
          <span class="topic-name">${escapeHtml(topic)}</span>
          <span class="topic-score">${Math.round(avg)}/100</span>
        </div>
        <div class="topic-bar"><div class="topic-bar-fill ${cls}" style="width:${Math.round(avg)}%"></div></div>
      </div>`;
    }).join("") || "<p style='color:var(--text-muted)'>No topic data available.</p>";
  }

  // Lists
  makeList(document.getElementById("strongAreas"), report.strong_areas, "No specific strengths identified.");
  makeList(document.getElementById("weakAreas"), report.weak_areas, "No specific weaknesses identified.");
  makeList(document.getElementById("misconceptions"), report.repeated_misconceptions, "No repeated misconceptions.");
  makeList(document.getElementById("revisionTopics"), report.revision_topics, "No specific revision topics.");

  // Practice questions
  const pq = document.getElementById("practiceQuestions");
  const practiceQs = report.practice_questions || [];
  if (practiceQs.length) {
    pq.innerHTML = practiceQs.map(q => `
      <div class="practice-q">
        <div class="practice-q-text">${escapeHtml(q.question || q)}</div>
        ${q.difficulty ? `<div class="practice-q-meta">Difficulty: ${escapeHtml(q.difficulty)} · ${escapeHtml(q.reason || "")}</div>` : ""}
      </div>`).join("");
  } else {
    pq.innerHTML = "<p style='color:var(--text-muted);font-size:0.9rem'>No practice questions available.</p>";
  }

  // Examiner comments
  document.getElementById("examinerComment").textContent = report.examiner_comments || "No examiner comments.";

  // Question review
  const reviewContainer = document.getElementById("questionReview");
  if (questions.length) {
    reviewContainer.innerHTML = questions.map((q, i) => {
      const sc = q.score || 0;
      const scoreColor = sc >= 70 ? "var(--success)" : sc >= 40 ? "var(--warn)" : "var(--error)";
      const fb = q.feedback || {};
      return `<div class="review-item">
        <div class="review-item-header">
          <span class="review-q-num">Q${i+1}</span>
          <span class="review-q-topic">${escapeHtml(q.topic || "")}</span>
          <span class="badge badge-${q.difficulty||'medium'}">${q.difficulty||'medium'}</span>
          <span class="review-q-score" style="color:${scoreColor}">${sc}/100</span>
        </div>
        <div class="review-q-text">${escapeHtml(q.question_text)}</div>
        ${q.student_answer ? `<div class="review-a-text"><strong>Your answer:</strong> ${escapeHtml(q.student_answer.slice(0,300))}${q.student_answer.length > 300 ? "…" : ""}</div>` : ""}
        ${fb.correct_reasoning ? `<div class="review-a-text" style="border-left:3px solid var(--accent)"><strong>Correct reasoning:</strong> ${escapeHtml(fb.correct_reasoning.slice(0,250))}…</div>` : ""}
      </div>`;
    }).join("");
  } else {
    reviewContainer.innerHTML = "<p style='color:var(--text-muted)'>No questions to review.</p>";
  }
}

function gradeFromScore(score) {
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 70) return "B";
  if (score >= 60) return "C";
  if (score >= 50) return "D";
  return "F";
}

loadReport();
