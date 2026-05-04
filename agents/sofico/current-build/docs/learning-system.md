# Sofi Learning System

How Sofi works — folder structure, question categories, spaced repetition, and interleaving.

---

## Quickstart

### Step 1: Upload your material

Drop any PDF or text file directly into the Slack DM with Sofi. She'll process it automatically.

### Step 2: Study

> *quiz me*

Sofi finds your due questions, mixes topics, and runs a session. She grades your answers and updates your progress.

### Step 3: Go deeper (optional)

> *explain [topic]*

Sofi walks you through the material chunk by chunk, with check-ins and Q&A.

---

## Learner Data Structure

Each learner has their own folder in the `learners/` directory:

```
learners/
└── {your-name}/
    ├── profile.yaml          # Your teaching preferences and archetype
    ├── memory.yaml           # Session history and psychological profile
    ├── config.yaml           # Session size, reminders, focus areas
    ├── topics/
    │   └── {topic-name}/
    │       ├── _index.yaml   # SM-2 data for every question in this topic
    │       └── {doc}.md      # Study notes + Anki questions
    └── sessions/
        └── {date}.md         # Session logs
```

**Topics** are created automatically when you upload a document. Sofi determines the topic from the content, then asks you to confirm or rename it.

---

## Question Categories

Every study document has questions in four categories. All four are used in each document.

| Category | What it tests | Example question |
|----------|---------------|-----------------|
| **Recall** | Facts, terms, definitions | "What is X?" |
| **Explain** | Understanding — why and how | "Why does X happen?" |
| **Apply** | Practical use in real situations | "How would you use X here?" |
| **Connect** | Relationships between ideas | "How does X relate to Y?" |

A typical document has ~15 questions: 4 Recall + 4 Explain + 4 Apply + 3 Connect.

### Subject tags

Questions can also have subject-specific tags. These are suggestions — use whatever fits your material:

`vocabulary` · `grammar` · `procedure` · `command` · `formula` · `definition` · `principle` · `pattern` · `rule` · `technique` · `argument` · `comparison` · `concept` · `relationship` · `example` · `history` · `person`

---

## Spaced Repetition (SM-2)

Sofi uses the SM-2 algorithm — the same one Anki uses — to schedule reviews at the right time.

### How grading works

After you answer a question, Sofi grades it 0–5:

| Score | Meaning |
|-------|---------|
| 5 | Perfect recall |
| 4 | Correct with minor hesitation |
| 3 | Correct with difficulty |
| 2 | Wrong, but the answer seemed easy |
| 1 | Wrong, but recognized the answer |
| 0 | Complete blackout |

### What happens next

- **Score < 3:** Question resets. You'll see it again tomorrow.
- **Score ≥ 3:** Interval grows. Questions you know well appear less often.

Example progression:
```
Review 1 → Review 2 → Review 8 → Review 20 → Review 50 → Review 125...
(days between reviews)
```

### What Sofi tracks per question

| Field | Meaning |
|-------|---------|
| `interval` | Days until next review |
| `easiness` | How fast intervals grow (1.3–2.5, starts at 2.5) |
| `reps` | Consecutive correct answers (resets on wrong answer) |
| `mastery` | Current mastery level (0.0–1.0) |
| `next_review` | Date of next scheduled review |

---

## Interleaving

Instead of studying one topic at a time, Sofi mixes questions from different topics in each session.

Research shows interleaving improves long-term retention compared to blocked practice.

### How Sofi builds a session

1. **Collect** — find all questions where `next_review ≤ today`
2. **Prioritize** — sort by lowest mastery (focus on weak areas)
3. **Balance** — include questions from all 4 categories where possible
4. **Shuffle** — alternate between different topics
5. **Limit** — cap at your preferred session size (default: 15)

Example session flow:
```
Git/Recall → Philosophy/Explain → Git/Apply → Python/Connect → Philosophy/Recall...
```

---

## Document Processing

When you upload a file, Sofi:

1. Extracts the text (PDF, DOCX, TXT, HTML all supported)
2. Checks if it might belong in an existing topic folder
3. Asks you to confirm the topic (or create a new one)
4. Generates a study document with notes + 15 questions
5. Saves the document and updates the topic's `_index.yaml`

Sofi can also walk you through generating notes on a topic interactively — say *explain [topic]* and at the end she'll save the explanation as a study guide.

See [parsing-prompt.md](parsing-prompt.md) for exactly how Sofi converts raw content into study documents.

---

## Explanation Mode

> *explain [topic]*

Sofi walks you through your notes section by section:

- Explains each chunk in your preferred style (narrative, logical steps, or examples-first)
- Does a quick comprehension check every 2 sections
- Answers questions mid-session
- Goes deeper on any section if you ask
- Ends with a summary you write yourself, then saves generated notes

---

## Learner Profile

Sofi adapts everything — explanations, quiz feedback, tone — to your profile.

Profile is set during onboarding and can be updated anytime by saying *customize*.

| Setting | Options |
|---------|---------|
| **Archetype** | Wise mentor · Martial arts master · Patient teacher · Research advisor |
| **Motivation** | Curiosity · Achievement · Play · Social contribution |
| **Mistake handling** | Direct correction · Gentle encouragement |
| **Chunk size** | Small · Medium · Large |
| **Explanation style** | Narrative · Logical steps · Examples-first |

---

## Memory

Sofi remembers across sessions:

- **Session summaries** — after each session, Sofi summarizes what happened, what you struggled with, and what you did well
- **Weekly reports** — every 7 days, a proactive report on patterns and trends
- **Psychological profile** — Sofi builds an understanding of your learning style, resistance patterns, and what strategies work for you

This context is used in every response to make teaching more relevant.

---

## Templates

See [templates/](templates/) for copy-paste templates:

- [study-document.md](templates/study-document.md) — Structure for study documents
- [_index.yaml](templates/_index.yaml) — Topic index format
- [config.yaml](templates/config.yaml) — Learner config
- [session.md](templates/session.md) — Session log format
