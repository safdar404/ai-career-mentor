# AI Career Mentor

**Your Personal AI Interviewer, Communication Coach & Career Development Partner.**

A Streamlit application that trains you for international AI engineering interviews. Six specialised AI agents interview you, correct your English, teach what you don't know, track your weaknesses, and report your progress from real stored data.

---

## Quick start (local)

Requirements: Python 3.11+ (tested on 3.12).

```bash
cd ai-career-mentor
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
# open .env and add ANTHROPIC_API_KEY and/or OPENAI_API_KEY
streamlit run app.py
```

Open http://localhost:8501, create your profile, and start with **Live AI Interview** or **English Communication Lab**.

Without any API key, the app still opens, and the dashboard, roadmap, projects and data export work. The AI features show setup instructions instead of failing.

### Which keys do I need?

| Key | Enables |
|---|---|
| `ANTHROPIC_API_KEY` | All coaching with Claude (default provider) |
| `OPENAI_API_KEY` | All coaching with OpenAI, **plus** voice transcription and the OpenAI voice |

One key is enough. With both, you choose the provider in **Settings**, and voice answers become available.

---

## Features

| Page | What it does |
|---|---|
| Dashboard | Readiness, technical, English, Python, GenAI, Agentic, problem-solving and confidence scores; daily trend; week-over-week change; strongest and weakest topics; repeated mistakes; training time; history |
| Live AI Interview | Choose role (8), difficulty (4), duration, category (6), company location and interviewer style. One question at a time, follow-ups on weak answers, adaptive difficulty, full scorecard per answer |
| English Communication Lab | Role-plays (stand-ups, client calls, recruiter screens and more). Corrections, a natural professional version, vocabulary, a practice sentence, and **Try again** with score comparison |
| Technical Assessment | Area-by-area testing across Python, libraries, ML, GenAI, Agentic AI, app development, Docker, automation, and Git/SQL/testing/security |
| Python Coding Lab | AI-generated challenges, syntax check, senior-engineer code review, improved code. Code is **not executed** (see Limitations) |
| Generative AI / Agentic AI Academy | Simple explanation, analogy and example, then you explain it back (Feynman technique) and get scored. Optional Roman Urdu summary |
| Project Presentation Trainer | Save your real projects, practise 30s / 1m / 3m / 5m pitches, and face tough questions from a senior interviewer |
| HR Interview Simulator | Behavioural and recruiter questions with STAR analysis. Improved answers use `[placeholders]` and never invent achievements |
| Weakness & Gap Analysis | Technical, communication and professional gaps; seen twice = priority; revision sessions; industry topics not yet assessed |
| Learning Roadmap | 90 days in six phases, with "you are here" tracking; **Adjust to my results** rewrites it from your data |
| Performance Reports | Area charts, communication skills, weekly reports compared with the previous week |
| Settings | Profile, provider, accent, voice, interviewer style, Urdu support, export or delete your data |

### The scorecard

Every interview answer is scored 0–10 on: technical accuracy, conceptual understanding, practical knowledge, English grammar, vocabulary, sentence structure, fluency and clarity, confidence, professional communication, and overall interview performance. That gives a total out of 100.

When a category doesn't apply (English Lab has no technical score; Coding Lab has no English score), it is marked "not assessed here" and the total is rescaled from the categories that were assessed. Nothing is filled in with made-up numbers.

---

## Architecture

```
                         Streamlit UI (app.py + page modules)
                                     |
                         Orchestrator (orchestrator.py)
     loads shared learner context from DB -> picks agents -> runs them -> saves results
        |            |             |            |            |              |
  Technical      English      Technical      Gap         HR & Career    Progress
  Interviewer    Coach        Mentor         Analyst     Coach          Manager
        \____________\____________|____________/____________/______________/
                                  |
                   LLM provider layer (llm.py)
                     Claude  |  OpenAI   (+ JSON repair, retries, clear errors)
                                  |
              Database (db.py, SQLAlchemy): SQLite or PostgreSQL
```

**How one answer is processed:**

1. The orchestrator loads your profile, open weaknesses and recent average from the database.
2. The Technical Interviewer (or the HR Coach for behavioural questions) and the English Coach evaluate the answer **in parallel**.
3. Their outputs are combined into the 10-category scorecard and saved. Topic, communication and daily statistics are updated.
4. The Gap Analyst extracts weaknesses using a fixed topic taxonomy (`topics.py`), so the same weakness always lands on the same key and repeats are counted reliably.
5. If you couldn't answer, the Technical Mentor teaches the concept and the next question re-tests it once.
6. Difficulty moves up after two strong answers and down after two weak ones.
7. When the session ends, the Progress Manager writes a summary from the stored results only.

Agents never call each other. They share context only through the database and the orchestrator.

### Project layout

All files sit in one folder, so the whole project uploads to GitHub in one step.

```
app.py              Streamlit entry point and navigation
api.py              Optional FastAPI service
config.py           Environment settings, log redaction of API keys
db.py               13 tables + repository functions, export/delete
llm.py              Claude/OpenAI providers, retries, JSON helper
agents.py           The six agents and their prompts
orchestrator.py     Session flow, scoring, teaching, adaptive difficulty
analytics.py        Deterministic stats for dashboard and reports
topics.py           Fixed topic taxonomy
voice.py            Speech-to-text, text-to-speech
theme.py            Custom CSS
components.py       Scorecard, feedback views, answer input, interview runner
dashboard.py, interview.py, english.py, coding.py, academy.py, projects.py,
gaps.py, roadmap.py, reports.py, settings_page.py     One module per page
test_*.py, fake_provider.py                           33 tests (no API calls)
.streamlit/config.toml                                Dark theme
```

### Database tables

`users`, `settings`, `conversations`, `interview_sessions`, `interview_questions`, `answer_evaluations`, `technical_skills`, `communication_skills`, `knowledge_gaps`, `learning_roadmaps`, `daily_progress`, `weekly_reports`, `projects`. Tables are created automatically on first run.

---

## Voice

| Feature | How | Needs |
|---|---|---|
| Spoken answers | Record, transcribe (OpenAI `whisper-1`), check the text, submit | `OPENAI_API_KEY` |
| Interviewer speaks with an accent | Browser speech synthesis (en-US, en-GB, en-CA, en-AU, en-NZ) | Nothing. Uses voices installed on your device |
| Natural AI voice | OpenAI TTS | `OPENAI_API_KEY` (no accent choice) |
| Replay corrected sentences | "Listen" buttons on every improved answer | Either voice option |

If your device lacks a particular accent voice, the browser uses its default voice and shows a note. Chrome and Edge usually include several English accents.

To add real-time voice later, implement a new provider beside `voice.py`. For phoneme-level pronunciation scoring, implement the `PronunciationProvider` interface.

---

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests use a deterministic fake model, so they need no API keys and cost nothing. They cover:

- the full interview flow, scorecard maths and the 10 categories
- repeated weakness becoming a priority
- weak answer triggering a lesson, then a re-test, then lower difficulty, with no infinite loop
- complete interviews opening with a self-introduction
- English Lab retries and Coding Lab static review
- reports refusing to run without real data
- session isolation between users, input validation, JSON repair
- data export and deletion
- the REST API's token protection
- every page rendering, plus end-to-end clicks through the real Streamlit app

### Manual checklist after adding your key

1. Live AI Interview → Junior AI Engineer, Beginner, Technical, 4 questions. Answer one well and one with "I don't know". You should see a lesson and then a re-check question.
2. English Lab → answer, then use **Try this reply again** and compare scores.
3. Settings → switch voice to Browser, choose British English, and return to the interview to hear the question.
4. With an OpenAI key: record an answer, transcribe, submit.
5. Gap Analysis → after a few answers, start a revision session.
6. Reports → generate a weekly report.

---

## Deployment

### Docker

```bash
cp .env.example .env    # add your keys
docker compose up --build
```

The app runs at http://localhost:8501, with the SQLite database kept in the `mentor-data` volume.

Optional services:

```bash
docker compose --profile api up        # REST API on 127.0.0.1:8000 (set API_TOKEN first)
docker compose --profile postgres up   # PostgreSQL
```

To use PostgreSQL, set this in `.env`:

```
DATABASE_URL=postgresql+psycopg://mentor:change-me@db:5432/mentor
POSTGRES_PASSWORD=change-me
```

Use a strong password and run `docker compose --profile postgres up`.

### Cloud

- **Streamlit Community Cloud:** push to a private GitHub repo (`.env` is git-ignored), set `app.py` as the entry point, and add your keys in the app's Secrets as environment variables. Its disk is not permanent, so use a hosted PostgreSQL (Neon, Supabase, Railway) via `DATABASE_URL`.
- **Any VM or container host** (Render, Railway, Fly.io, AWS, Azure): deploy the Dockerfile, set environment variables, and attach PostgreSQL or a persistent volume.
- **Microphone access** requires HTTPS on any public deployment. Localhost works without it.

### REST API

```bash
API_TOKEN=your-long-random-token uvicorn api:app --port 8000
curl -H "Authorization: Bearer your-long-random-token" http://localhost:8000/users
```

Endpoints: `GET /health` (public), `GET /users`, `GET /users/{id}/stats`, `GET /users/{id}/export`. Without `API_TOKEN`, everything except `/health` is disabled.

---

## Security

- API keys are read only from environment variables. They are never stored in the database, shown in the UI, or written to logs; a log filter redacts them if they appear.
- Answers are length-limited and wrapped as untrusted data in agent prompts, so instructions inside an answer are ignored.
- AI-generated text played by the browser voice is escaped before being placed in the player, which prevents script injection.
- Each browser session is bound to one user, and the orchestrator rejects answers to questions from another user's session.
- The Docker image runs as a non-root user, and the REST API binds to localhost only.
- This is a single-machine training app, not a multi-tenant SaaS: there are no passwords on profiles. Before exposing it publicly, put it behind authentication (a reverse proxy with login, or Streamlit's authentication).

---

## Limitations

- **Pronunciation and speaking speed are not measured.** Transcription returns text only. "Words to practise" are suggestions based on your wording. Pitch length is estimated from word count at about 130 words per minute.
- **Code is not executed.** Running untrusted code safely needs a sandbox. The review reasons about your code statically and says so; run the test cases yourself.
- **AI scores are judgements, not measurements.** They are consistent enough to track progress, but they vary between runs and between providers. Look at trends over many answers, not single scores.
- **Verified in development:** all 33 automated tests pass and the server boots. **Not yet verified:** live calls with real API keys, the Docker build, PostgreSQL, and microphone recording in a real browser. Run the manual checklist above after adding your key.

---

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (empty) | Claude access |
| `OPENAI_API_KEY` | (empty) | OpenAI access and voice |
| `DEFAULT_PROVIDER` | `anthropic` | Provider used when both keys exist |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Claude model |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OPENAI_STT_MODEL` | `whisper-1` | Transcription model |
| `OPENAI_TTS_MODEL` | `tts-1` | Voice model |
| `DATABASE_URL` | SQLite in `./data` | Database connection |
| `API_TOKEN` | (empty) | Enables the REST API |
| `MAX_ANSWER_CHARS` | `6000` | Answer length limit |
| `LLM_TIMEOUT_SECONDS` | `90` | Model request timeout |
| `LOG_LEVEL` | `INFO` | Logging level |

Tested with Python 3.12, Streamlit 1.66, anthropic 2.4, openai 3.42, SQLAlchemy 2.1, FastAPI 0.162.
