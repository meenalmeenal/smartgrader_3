# 🎓 SmartGrader — AI Answer Sheet Evaluator

Stack: Python + FastAPI (backend) · React (frontend)
Free AI: Gemini 2.5 Flash (OCR) + Llama 3.3 70B via Groq (Grading)

## 🆓 Get FREE API Keys

- Gemini: https://aistudio.google.com/app/apikey
- Groq:   https://console.groq.com/keys

## 🚀 Setup

### Backend (Terminal 1)

  cd backend
  python -m venv venv

  # Activate — Windows:
  venv\Scripts\activate

  # Activate — Mac/Linux:
  source venv/bin/activate

  # You will see (venv) in your terminal — that means it worked!

  pip install -r requirements.txt
  copy .env.example .env        (Windows)
  cp .env.example .env          (Mac/Linux)

  # Open .env and paste your GEMINI_API_KEY and GROQ_API_KEY

  uvicorn main:app --reload --port 5000

  # You will see: Uvicorn running on http://127.0.0.1:5000

### Frontend (Terminal 2 — click + in terminal panel)

  cd frontend
  npm install
  npm start

  # Browser opens at http://localhost:3000

## Troubleshooting

"ModuleNotFoundError: No module named fastapi"
  -> venv is not activated, run venv\Scripts\activate again

"GEMINI_API_KEY not set"
  -> Make sure .env file exists in backend folder

"pip is not recognized"
  -> Try: python -m pip install -r requirements.txt

## Confidence Score

  80-100%  AI is very sure         -> Accept grade
  55-79%   Some judgment call      -> Spot-check
  0-54%    Vague / ambiguous       -> Teacher review needed
