# AI Viva Simulator

An interactive, AI-powered viva voce examination simulator. Upload your project documentation and face a rigorous AI examiner that asks adaptive, medium-to-hard questions and provides detailed feedback.

---

## Features

- **RAG-powered questions** grounded in your uploaded project documents (PDF, DOCX, TXT, Markdown)
- **Adaptive examination** — difficulty increases/decreases based on your performance
- **Deep correction engine** — step-by-step explanations for wrong or incomplete answers
- **Voice mode** — speak your answers via microphone (Groq Whisper STT) with browser TTS for questions
- **Structured scoring** — 100-point rubric (Technical Correctness 40%, Depth 30%, Project-specific 20%, Completeness 10%)
- **Final performance report** — topic-wise scores, misconceptions, revision topics, practice questions
- **Dark, responsive UI** — works on desktop and mobile

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask 3.x |
| LLM | Groq API (`llama-3.3-70b-versatile`) |
| STT | Groq Whisper (`whisper-large-v3-turbo`) |
| TTS | Browser SpeechSynthesis API |
| RAG | sentence-transformers + FAISS |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX), stdlib (TXT/MD) |
| Database | SQLite via SQLAlchemy 2.x |
| Config | python-dotenv |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (no framework) |

> **Python compatibility note:** The application is developed and tested with Python 3.11+. Python 3.14 is supported where all dependencies are compatible; however, `faiss-cpu` and `sentence-transformers` may require Python ≤ 3.12 depending on your platform. If you encounter issues, create a virtual environment with Python 3.11.

---

## Windows Setup (Step-by-Step)

### 1. Prerequisites

- Python 3.11 or 3.12 (recommended), available from [python.org](https://www.python.org/downloads/)
- A [Groq API key](https://console.groq.com) (free tier available)

### 2. Clone / Navigate to project

```cmd
cd d:\project1
```

### 3. Create and activate a virtual environment

```cmd
python -m venv venv
venv\Scripts\activate
```

### 4. Install dependencies

```cmd
pip install -r requirements.txt
```

> **Note:** The first run will download the `all-MiniLM-L6-v2` embedding model (~90 MB) automatically.

### 5. Configure environment variables

```cmd
copy .env.example .env
```

Edit `.env` with Notepad or VS Code:

```
GROQ_API_KEY=gsk_your_actual_key_here
FLASK_SECRET_KEY=some-long-random-string
```

### 6. Run the application

```cmd
python run.py
```

Open your browser at: **http://localhost:5000**

---

## Running Tests

```cmd
python -m pytest tests/ -v
```

Test coverage includes:
- Document parsing (TXT, Markdown, DOCX)
- Technology auto-detection
- Chunk overlap verification
- Vector store isolation (cross-project contamination prevention)
- All REST API endpoints (projects, sessions, speech)
- LLM JSON safety parser (fenced code, trailing commas, prose)
- Speech service edge cases (empty audio, oversized audio, missing key)
- Frontend route rendering

---

## Project Structure

```
d:\project1\
├── run.py                    ← Entry point: python run.py
├── app_factory.py            ← Flask application factory
├── config.py                 ← Environment-based configuration
├── requirements.txt
├── .env.example              ← Template; copy to .env and fill
├── .gitignore
├── README.md
│
├── app/
│   ├── models/
│   │   └── database.py       ← SQLAlchemy models (Project, VivaSession, Question)
│   ├── rag/
│   │   ├── document_parser.py ← PDF/DOCX/TXT/MD parsing + chunking
│   │   └── vector_store.py   ← FAISS index (per-project isolation)
│   ├── llm/
│   │   └── examiner.py       ← Question generation, answer evaluation, report
│   ├── speech/
│   │   └── transcription.py  ← Groq Whisper STT
│   ├── routes/
│   │   ├── projects.py       ← /api/projects endpoints
│   │   ├── sessions.py       ← /api/sessions endpoints
│   │   └── speech.py         ← /api/speech/transcribe
│   ├── templates/
│   │   ├── index.html        ← Dashboard / upload
│   │   ├── viva.html         ← Examination screen
│   │   └── report.html       ← Final report
│   └── static/
│       ├── css/main.css      ← Dark theme stylesheet
│       └── js/
│           ├── main.js       ← Dashboard logic
│           ├── viva.js       ← Exam + voice logic
│           └── report.js     ← Report rendering
│
├── tests/
│   ├── conftest.py
│   └── test_viva_simulator.py
│
├── uploads/                  ← Uploaded project documents (git-ignored)
└── faiss_indexes/            ← Per-project FAISS indexes (git-ignored)
```

---

## Required Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | **Yes** | — | Groq API key from console.groq.com |
| `FLASK_SECRET_KEY` | Yes (prod) | dev key | Flask session secret |
| `GROQ_LLM_MODEL` | No | `llama-3.3-70b-versatile` | Groq chat model |
| `GROQ_WHISPER_MODEL` | No | `whisper-large-v3-turbo` | Groq STT model |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | Local sentence-transformer model |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Maximum file size in MB |
| `CHUNK_SIZE` | No | `800` | Words per RAG chunk |
| `CHUNK_OVERLAP` | No | `150` | Word overlap between chunks |
| `WEIGHT_TECHNICAL_CORRECTNESS` | No | `40` | Rubric weight (must sum to 100) |
| `WEIGHT_DEPTH_OF_REASONING` | No | `30` | Rubric weight |
| `WEIGHT_PROJECT_SPECIFIC` | No | `20` | Rubric weight |
| `WEIGHT_COMPLETENESS` | No | `10` | Rubric weight |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/projects` | Upload document |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/<id>` | Get project details |
| GET | `/api/projects/<id>/status` | Poll processing status |
| DELETE | `/api/projects/<id>` | Delete project |
| POST | `/api/sessions` | Start viva session |
| GET | `/api/sessions/<id>` | Get session info |
| GET | `/api/sessions/<id>/question` | Get current/next question |
| POST | `/api/sessions/<id>/answer` | Submit answer |
| GET | `/api/sessions/<id>/history` | Full Q&A history |
| GET | `/api/sessions/<id>/report` | Final performance report |
| DELETE | `/api/sessions/<id>` | Delete session |
| POST | `/api/speech/transcribe` | Transcribe audio (multipart) |

---

## Known Limitations

1. **Scanned PDFs**: Text cannot be extracted from image-only PDFs. The app will warn you. Use a PDF with selectable text or convert with an OCR tool first.
2. **Groq API key required**: All AI features (question generation, evaluation, STT) require a valid `GROQ_API_KEY`. Without it, the server runs but AI calls will return a clear error.
3. **Embedding model download**: First run downloads ~90 MB of embedding model weights. Subsequent runs use the cached model.
4. **Concurrent users**: SQLite with WAL mode supports moderate concurrency. For production with many users, migrate to PostgreSQL.
5. **Audio format**: Voice recording uses the browser's native `MediaRecorder` (WebM/Opus). Most modern browsers support this natively.

---

## Security Notes

- API keys are kept server-side only; never sent to the browser.
- Uploaded document content is treated as **untrusted data** — it cannot override AI system prompts.
- File paths are sanitised; uploads use UUID-prefixed filenames.
- Raw audio is not stored persistently after transcription.
