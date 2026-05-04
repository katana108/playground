# Sofi — AI Learning Companion

*Tutor — Helps people learn, retain, and grow*

Sofi is an AI tutor that lives in Slack. Upload any study material — PDFs, notes, articles — and she processes it into flashcards, then runs adaptive study sessions using spaced repetition. She remembers what you know, adapts to how you learn, and teaches in depth when you want to go further.

---

## What Sofi Does

| Feature | Description |
|---------|-------------|
| **Document processing** | Upload a PDF or text file → Sofi extracts notes and generates ~15 study questions |
| **Spaced repetition** | SM-2 algorithm schedules reviews at optimal intervals (same as Anki) |
| **Personalized quiz sessions** | AI grades your answers, gives feedback, adapts to your style |
| **Explanation mode** | Walk through material chunk by chunk with check-ins and Q&A |
| **Learner profile** | Onboarding sets your teaching style, motivation, and pacing preferences |
| **Conversation memory** | Session summaries, weekly learning reports, psychological profile |
| **Progress tracking** | Mastery by topic, weak areas, questions due today |

---

## Quick Start

### 1. Set up environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your keys
```

Required variables:

| Variable | What it is |
|----------|------------|
| `SLACK_BOT_TOKEN` | Slack bot OAuth token (starts with `xoxb-`) |
| `SLACK_APP_TOKEN` | Slack app-level token (starts with `xapp-`) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GITLAB_ACCESS_TOKEN` | GitLab personal access token (for learner data storage) |
| `GITLAB_URL` | Your GitLab instance URL |
| `SOFI_USE_LOCAL_FILES` | Set to `true` to use local files instead of GitLab (default: `true`) |

### 3. Run Sofi

```bash
python src/main.py
```

---

## Architecture

```
sofi/
├── src/
│   ├── main.py                          # Entry point
│   ├── slack_bot.py                     # Slack event routing (LLM-first intent classification)
│   ├── handlers/
│   │   ├── study_handler.py             # Quiz sessions (SM-2 + AI grading)
│   │   ├── upload_handler.py            # File upload and document processing
│   │   ├── explanation_handler.py       # Chunk-by-chunk explanation sessions
│   │   ├── progress_handler.py          # Progress and mastery stats
│   │   └── onboarding_handler.py        # First-time setup and profile updates
│   ├── services/
│   │   ├── session_response_service.py  # LLM calls, intent classification, routing
│   │   ├── document_parser_service.py   # Raw content → study document + questions
│   │   ├── file_extraction_service.py   # PDF, DOCX, TXT, HTML text extraction
│   │   ├── sm2_service.py               # SM-2 spaced repetition algorithm
│   │   ├── grading_service.py           # AI grades learner answers (0-5)
│   │   ├── profile_service.py           # Learner profile and personalized prompts
│   │   ├── conversation_memory_service.py # Session summaries, weekly reports
│   │   ├── gitlab_service.py            # GitLab storage backend
│   │   └── local_file_service.py        # Local file storage backend
│   └── config/
│       ├── personality.py               # Archetype voices and system prompts
│       └── educational_constitution.py  # Core teaching principles
├── learners/
│   └── {learner-name}/                  # One folder per learner
│       ├── profile.yaml                 # Learner profile and preferences
│       ├── memory.yaml                  # Session history and psychological profile
│       ├── topics/                      # Study documents organized by topic
│       │   └── {topic}/
│       │       ├── _index.yaml          # SM-2 data for all questions in topic
│       │       └── {document}.md        # Study notes + Anki questions
│       └── sessions/                    # Session logs
├── k8s/                                 # Kubernetes deployment manifests
├── docs/                                # Documentation
│   ├── learning-system.md               # How the learning system works
│   ├── parsing-prompt.md                # How Sofi processes documents
│   └── templates/                       # Copy-paste templates for learner repos
└── planning/
    └── business-plan.md
```

---

## How It Works

### Routing

Every message goes through LLM-based intent classification — no keyword matching. Sofi uses `classify_intent` to determine whether the user wants to quiz, explain, upload, check progress, customize, or just chat.

### Storage

Sofi supports two backends, configured via `SOFI_USE_LOCAL_FILES`:

- **Local files** (`true`) — learner data lives in `learners/` folder. Good for development and self-hosting.
- **GitLab** (`false`) — learner data stored in GitLab repositories. Good for teams.

Both backends implement the same interface, so switching is a one-line config change.

### Learner Profile

On first message, Sofi runs a 5-question onboarding to learn:
- Teaching archetype (wise mentor / martial arts master / patient teacher / research advisor)
- What motivates the learner (curiosity / achievement / play / social contribution)
- How they handle mistakes
- Preferred explanation chunk size
- Metaphor preferences

Everything Sofi says is filtered through this profile.

---

## Deploying to Kubernetes

See [`k8s/`](k8s/) for deployment manifests. Sofi runs as a single-container deployment. Learner data can be stored on a PVC (see `k8s/pvc.yaml`) or in GitLab.

---

## Documentation

- [USER_GUIDE.md](USER_GUIDE.md) — End-user guide (how to use Sofi in Slack)
- [docs/learning-system.md](docs/learning-system.md) — How the learning system works
- [docs/parsing-prompt.md](docs/parsing-prompt.md) — How Sofi processes documents
- [docs/templates/](docs/templates/) — Templates for study documents, indexes, configs
- [planning/business-plan.md](planning/business-plan.md) — Business plan and roadmap

---

## License

MIT
