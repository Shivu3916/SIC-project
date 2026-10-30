/* ═══════════════════════════════════════════════════════
   main.js – Dashboard / Landing page logic
   ═══════════════════════════════════════════════════════ */
"use strict";

// ── Utilities ──────────────────────────────────────────────
function toast(msg, type = "info", duration = 4000) {
  const icons = { success: "✅", error: "❌", info: "ℹ️", warn: "⚠️" };
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type] || "ℹ️"}</span>
                  <span class="toast-msg">${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// ── State ──────────────────────────────────────────────────
let selectedFile = null;
let currentProjectId = null;
let voiceMode = false;
let pollingTimer = null;

// ── DOM refs ───────────────────────────────────────────────
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const uploadForm = document.getElementById("uploadForm");
const fileName = document.getElementById("fileName");
const fileSize = document.getElementById("fileSize");
const clearFileBtn = document.getElementById("clearFileBtn");
const uploadBtn = document.getElementById("uploadBtn");
const processingStatus = document.getElementById("processingStatus");
const statusTitle = document.getElementById("statusTitle");
const statusMsg = document.getElementById("statusMsg");
const statusIcon = document.getElementById("statusIcon");
const progressFill = document.getElementById("progressFill");
const techTags = document.getElementById("techTags");
const projectsGrid = document.getElementById("projectsGrid");
const textModeBtn = document.getElementById("textModeBtn");
const voiceModeBtn = document.getElementById("voiceModeBtn");
const apiStatusBadge = document.getElementById("apiStatusBadge");

// ── Drag & drop ────────────────────────────────────────────
["dragenter", "dragover"].forEach(evt =>
  dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add("drag-over"); }));
["dragleave", "drop"].forEach(evt =>
  dropZone.addEventListener(evt, () => dropZone.classList.remove("drag-over")));

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});

dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

clearFileBtn.addEventListener("click", e => {
  e.stopPropagation();
  clearFile();
});

function handleFile(file) {
  const allowed = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain", "text/markdown", ""];
  const allowedExt = ["pdf", "docx", "txt", "md"];
  const ext = file.name.split(".").pop().toLowerCase();
  if (!allowedExt.includes(ext)) {
    toast(`Unsupported file type: .${ext}. Use PDF, DOCX, TXT, or MD.`, "error");
    return;
  }
  const maxBytes = 50 * 1024 * 1024;
  if (file.size > maxBytes) {
    toast("File too large. Maximum size is 50MB.", "error");
    return;
  }
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);

  // Pre-fill title from filename
  const titleInput = document.getElementById("projectTitle");
  if (!titleInput.value) {
    titleInput.value = file.name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " ")
      .replace(/\b\w/g, c => c.toUpperCase());
  }

  dropZone.style.display = "none";
  uploadForm.style.display = "flex";
}

function clearFile() {
  selectedFile = null;
  fileInput.value = "";
  document.getElementById("projectTitle").value = "";
  dropZone.style.display = "block";
  uploadForm.style.display = "none";
  processingStatus.style.display = "none";
}

// ── Mode toggle ────────────────────────────────────────────
textModeBtn.addEventListener("click", () => { voiceMode = false; textModeBtn.classList.add("active"); voiceModeBtn.classList.remove("active"); });
voiceModeBtn.addEventListener("click", () => { voiceMode = true; voiceModeBtn.classList.add("active"); textModeBtn.classList.remove("active"); });

// ── Upload & Process ───────────────────────────────────────
uploadBtn.addEventListener("click", async () => {
  if (!selectedFile) { toast("Please select a file first.", "warn"); return; }

  const title = document.getElementById("projectTitle").value.trim() || "My Project";
  const difficulty = document.getElementById("difficultySelect").value;
  const questionCount = parseInt(document.getElementById("questionCount").value);

  // Show loading state
  uploadBtn.querySelector(".btn-text").style.display = "none";
  uploadBtn.querySelector(".btn-spinner").style.display = "inline";
  uploadBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("title", title);

  try {
    const res = await fetch("/api/projects", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed.");

    currentProjectId = data.project.id;
    toast("Document uploaded! Processing now…", "success");

    // Show processing status
    uploadForm.style.display = "none";
    processingStatus.style.display = "flex";
    setProcessingStatus("processing", "Analysing document…", 30);

    // Poll status until ready
    pollStatus(currentProjectId, difficulty, questionCount);
  } catch (err) {
    toast(err.message, "error");
    uploadBtn.querySelector(".btn-text").style.display = "inline";
    uploadBtn.querySelector(".btn-spinner").style.display = "none";
    uploadBtn.disabled = false;
  }
});

function setProcessingStatus(status, msg, progress) {
  const icons = { processing: "⚙️", ready: "✅", failed: "❌" };
  statusIcon.textContent = icons[status] || "⏳";
  statusTitle.textContent = { processing: "Processing…", ready: "Ready!", failed: "Failed" }[status] || status;
  statusMsg.textContent = msg;
  progressFill.style.width = `${progress}%`;
}

async function pollStatus(projectId, difficulty, questionCount) {
  const maxAttempts = 120;
  let attempts = 0;

  const poll = async () => {
    if (attempts++ > maxAttempts) {
      setProcessingStatus("failed", "Processing timed out. Please try again.", 0);
      return;
    }

    try {
      const res = await fetch(`/api/projects/${projectId}/status`);
      const data = await res.json();

      if (data.status === "ready") {
        setProcessingStatus("ready", data.message, 100);
        renderTechTags(data.technologies || []);
        toast("Document processed! Starting viva…", "success");
        setTimeout(() => startSession(projectId, difficulty, questionCount), 1200);
        return;
      } else if (data.status === "failed") {
        setProcessingStatus("failed", data.message, 0);
        toast("Processing failed: " + data.message, "error");
        return;
      } else {
        const progress = data.status === "processing" ? 60 : 30;
        setProcessingStatus("processing", data.message || "Processing…", progress);
        pollingTimer = setTimeout(poll, 2000);
      }
    } catch (err) {
      pollingTimer = setTimeout(poll, 3000);
    }
  };

  poll();
}

function renderTechTags(techs) {
  techTags.innerHTML = "";
  techs.slice(0, 12).forEach(t => {
    const tag = document.createElement("span");
    tag.className = "tech-tag";
    tag.textContent = t;
    techTags.appendChild(tag);
  });
}

async function startSession(projectId, difficulty, questionCount) {
  try {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        difficulty: difficulty,
        total_questions: questionCount,
        voice_mode: voiceMode,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not start session.");
    window.location.href = `/viva/${data.session.id}`;
  } catch (err) {
    toast(err.message, "error");
  }
}

// ── Load projects list ─────────────────────────────────────
async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    const data = await res.json();
    renderProjects(data.projects || []);
  } catch (_) { /* silent */ }
}

function renderProjects(projects) {
  if (!projects.length) {
    projectsGrid.innerHTML = '<div class="empty-state">No projects yet. Upload one above to get started.</div>';
    return;
  }
  projectsGrid.innerHTML = "";
  projects.forEach(p => {
    const card = document.createElement("div");
    card.className = "project-card";
    const dotClass = { ready: "ready", processing: "processing", pending: "pending", failed: "failed" }[p.processing_status] || "pending";
    card.innerHTML = `
      <div class="project-card-header">
        <div class="project-card-title">${escapeHtml(p.title)}</div>
        <span class="project-card-type">${p.file_type.toUpperCase()}</span>
      </div>
      <div class="project-card-status">
        <span class="status-dot ${dotClass}"></span>
        <span>${p.processing_status === "ready" ? `${p.chunk_count} chunks indexed` : p.processing_status}</span>
      </div>
      <div class="project-card-meta">${formatBytes(p.file_size_bytes)} · ${formatDate(p.created_at)}</div>
      <div class="project-card-actions">
        ${p.processing_status === "ready" ?
          `<button class="btn btn-primary" onclick="openSessionConfig(${p.id})">Start Viva</button>` : ""}
        <button class="btn btn-ghost" onclick="deleteProject(${p.id}, this)">🗑 Delete</button>
      </div>`;
    projectsGrid.appendChild(card);
  });
}

window.openSessionConfig = function(projectId) {
  // Simple inline session start with defaults
  const difficulty = "medium";
  const questionCount = 10;
  startSession(projectId, difficulty, questionCount);
};

window.deleteProject = async function(projectId, btn) {
  if (!confirm("Delete this project and all its data?")) return;
  try {
    const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    toast("Project deleted.", "info");
    loadProjects();
  } catch (err) {
    toast(err.message, "error");
  }
};

// ── API status check ───────────────────────────────────────
async function checkApiStatus() {
  try {
    // We just try to load projects; if the server is up, API is working
    const res = await fetch("/api/projects");
    if (res.ok) {
      apiStatusBadge.className = "badge badge-ok";
      apiStatusBadge.textContent = "API Ready";
    }
  } catch (_) {
    apiStatusBadge.className = "badge badge-error";
    apiStatusBadge.textContent = "Server Error";
  }
}

// ── Helpers ────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// ── Init ───────────────────────────────────────────────────
checkApiStatus();
loadProjects();
