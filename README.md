# 🎓 SmartGrader — AI-Powered Answer Sheet Evaluator

> Automatically grade handwritten or typed exam answer sheets using a **hybrid similarity + LLM pipeline**. Upload an answer sheet image/PDF and an answer key, and get per-question marks, keyword analysis, and teacher-style feedback in seconds.

---

## ✨ Features

- 📸 **OCR via Gemini 2.5 Flash** — extracts text from handwritten/typed answer sheets and PDFs
- 🔍 **Hybrid Similarity Engine** — BM25 + Fuzzy + Semantic Cosine (sentence-transformers) for deterministic keyword scoring
- 🤖 **LLM Grading via Groq (Llama 3.3 70B)** — conceptual feedback and mark suggestion, blended 70/30 with similarity score
- ✅ **MCQ Support** — exact option-letter matching, bypasses similarity scoring
- 📊 **Confidence Scoring** — 40–95% confidence based on sim/LLM agreement; flags low-confidence answers for teacher review
- 📝 **Structured Exam Support** — define sections, questions, sub-parts, and marks via a JSON structure
- 🌐 **React Frontend** — clean UI for uploading files, setting strictness, and viewing graded results

---

## 🏗️ Architecture

```
smartgrader_3/
├── backend/
│   ├── main.py          # FastAPI app — OCR, answer extraction, grading pipeline
│   ├── similarity.py    # Hybrid BM25 + Fuzzy + Cosine similarity engine
│   └── .env             # Your API keys (not committed)
├── frontend/
│   ├── src/
│   │   ├── App.js       # Main React app
│   │   └── components/  # UI components
│   └── package.json
├── requirements.txt     # Python backend dependencies
└── .env.example         # Template for API keys
```

### Grading Pipeline

```
Answer Sheet (image/PDF)
        ↓
   Gemini OCR (extracts raw text)
        ↓
   Groq LLM — extracts per-question answers from OCR text
        ↓
   Similarity Engine (similarity.py)
        ├── BM25 score (exact word match)
        ├── Fuzzy score (misspelling-tolerant)
        └── Cosine score (semantic meaning via sentence-transformers)
                ↓
          blended_multiplier → sim_marks (70% weight)
        ↓
   Groq LLM — conceptual feedback + suggested_marks (30% weight, capped ±1)
        ↓
   final marks_awarded + confidence score + needs_review flag
```

---

## 🆓 Get FREE API Keys

| Service | Purpose | Link |
|---|---|---|
| **Gemini 2.5 Flash** | OCR (answer sheet + key) | https://aistudio.google.com/app/apikey |
| **Groq (Llama 3.3 70B)** | Answer extraction + grading feedback | https://console.groq.com/keys |

Both services have generous free tiers — no credit card required.

---

## 🚀 Setup & Run

### Prerequisites

- Python 3.10+
- Node.js 18+

---

### Backend (Terminal 1)

```bash
# 1. Clone / navigate to project root
cd smartgrader_3

# 2. Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Set up your .env file
copy .env.example backend\.env        # Windows
cp .env.example backend/.env          # Mac/Linux

# Open backend/.env and paste your API keys

# 5. Start the backend API
cd backend
uvicorn main:app --reload --port 5000
```

You should see:
```
[similarity] Loading embedding model (multi-qa-mpnet-base-dot-v1)...
[similarity] Model ready.
INFO:     Uvicorn running on http://127.0.0.1:5000
```

> **Note:** The first startup downloads the `multi-qa-mpnet-base-dot-v1` sentence-transformer model (~420 MB). This is a one-time download.

---

### Frontend (Terminal 2)

```bash
cd frontend
npm install
npm start
```

Browser opens at **http://localhost:3000**

---

## ⚙️ Configuration

### `backend/.env`

```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

### Strictness Modes

Set via the UI dropdown. Controls similarity thresholds:

| Mode | Present threshold | Partial threshold |
|---|---|---|
| **Strict** | ≥ 0.80 | ≥ 0.60 |
| **Moderate** (default) | ≥ 0.70 | ≥ 0.45 |
| **Lenient** | ≥ 0.60 | ≥ 0.35 |

---

## 📊 Confidence Score Guide

| Score | Meaning | Recommended Action |
|---|---|---|
| **80 – 95%** | High agreement between similarity engine and LLM | Accept grade |
| **55 – 79%** | Some uncertainty | Spot-check |
| **40 – 54%** | Low confidence (vague/ambiguous answer) | Teacher review needed |

Answers with confidence < 55% are automatically flagged with `needs_review: true`.

---

## 📦 Dependencies

### Backend (`requirements.txt`)

| Package | Purpose |
|---|---|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server |
| `python-multipart` | File upload support |
| `python-dotenv` | Load `.env` API keys |
| `httpx` | Async HTTP client (Gemini + Groq calls) |
| `Pillow` | Image processing / PDF page stitching |
| `PyMuPDF` (`fitz`) | PDF → image rendering |
| `rapidfuzz` | Fast fuzzy string matching |
| `sentence-transformers` | Semantic cosine similarity embeddings |
| `rank-bm25` | BM25 keyword relevance scoring |

### Frontend

| Package | Purpose |
|---|---|
| `react` 18 | UI framework |
| `axios` | HTTP requests to backend |
| `react-scripts` | CRA build toolchain |

---

## 🛠️ Troubleshooting

| Error | Fix |
|---|---|
| `ModuleNotFoundError: No module named fastapi` | Virtual env not activated — run `venv\Scripts\activate` |
| `GEMINI_API_KEY not set` | Check that `backend/.env` exists and has your key |
| `pip is not recognized` | Use `python -m pip install -r requirements.txt` |
| `Groq 401 Unauthorized` | Re-check your `GROQ_API_KEY` in `.env` — no extra spaces or quotes |
| `Gemini 429 Rate Limit` | Free tier limit hit — wait ~60s and retry |
| First run is slow | Sentence-transformer model is downloading (~420 MB) — normal, one-time |

---

## 🔌 API Reference

### `GET /api/health`
Returns `{"status": "ok", "message": "SmartGrader API running"}`

### `POST /api/grade`

| Field | Type | Description |
|---|---|---|
| `answerSheet` | file | Student's answer sheet (image or PDF) |
| `answerKey` | file | Teacher's answer key (image or PDF) |
| `subject` | string | Subject name for LLM context (e.g. `Biology`) |
| `studentName` | string | Optional — used in summary report |
| `strictness` | string | `strict` / `moderate` / `lenient` |
| `answerKeyText` | string | Optional raw text — skips OCR for the key |
| `structure` | JSON string | Question structure with marks (see below) |

**Response:**
```json
{
  "success": true,
  "extractedText": "...",
  "gradedQuestions": [
    {
      "display_label": "Section A Q1",
      "marks_awarded": 3,
      "marks_available": 5,
      "confidence": 78,
      "needs_review": false,
      "feedback": "...",
      "keywords_present": ["..."],
      "keywords_missing": ["..."]
    }
  ],
  "summary": {
    "grade": "B",
    "total_obtained": 28,
    "total_max": 40,
    "percentage": 70,
    "overall_comment": "...",
    "strengths": ["..."],
    "improvements": ["..."]
  }
}
```

---

## 📄 License

MIT — free for personal and educational use.
