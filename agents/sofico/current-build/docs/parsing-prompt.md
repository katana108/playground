# Parsing Prompt

How Sofi converts raw source material into a study document.

This documents the prompt used in `src/services/document_parser_service.py`. If you want to change how documents get processed, that's the file to edit.

---

## What the prompt does

When you upload a file, Sofi sends the raw text to the LLM with a structured prompt asking it to produce a study document in a specific format. The prompt is personalized to your learner level and any focus areas you've set.

---

## The prompt structure

```
[Sofi's voice / system prompt]

You are processing a document to create personalized study materials.

## Learner Profile

Level: [beginner | intermediate | advanced]
[Level-specific guidance — see below]
[Focus areas if set: "Learner's Focus Areas: X, Y, Z"]

## Source Material

[Raw document text]

[Optional: "Suggested Topic: X" if user provided one]
[Optional: "Specific Instructions: X" if user added instructions]

## Your Task

Create a study document in this exact format:
[see Output Format below]

## Guidelines

[see Guidelines below]
```

---

## Level guidance

The prompt adapts based on the learner's level:

**Beginner**
- Simple explanations, no assumed prior knowledge
- More Recall questions to build vocabulary
- Foundational concepts before advanced ones

**Intermediate** (default)
- Balanced mix of all question types
- Connects new concepts to likely existing knowledge
- Challenges learner to apply knowledge

**Advanced**
- Nuanced understanding and edge cases
- More Connect questions to build relationships
- Complex applications, solid prior knowledge assumed

---

## Output format

The LLM is asked to produce this exact markdown structure:

```markdown
---
topic: "lowercase-with-hyphens"
source: "title or description of source material"
created: YYYY-MM-DD
tags: ["tag1", "tag2", "tag3"]
---

# Title

[Notes — summary of key concepts from the material, organized logically,
 adapted to the learner's level]

## Key Concepts

- Concept 1: explanation
- Concept 2: explanation

---

## Anki Questions

### Recall

**Q1:** [question]
**A1:** [answer]

**Q2:** [question]
**A2:** [answer]

**Q3:** [question]
**A3:** [answer]

**Q4:** [question]
**A4:** [answer]

### Explain

**Q5:** [question]
**A5:** [answer]

**Q6:** [question]
**A6:** [answer]

**Q7:** [question]
**A7:** [answer]

**Q8:** [question]
**A8:** [answer]

### Apply

**Q9:** [question]
**A9:** [answer]

**Q10:** [question]
**A10:** [answer]

**Q11:** [question]
**A11:** [answer]

**Q12:** [question]
**A12:** [answer]

### Connect

**Q13:** [question]
**A13:** [answer]

**Q14:** [question]
**A14:** [answer]

**Q15:** [question]
**A15:** [answer]
```

---

## Guidelines in the prompt

### 1. Adapt to document type

| Document type | Question emphasis |
|---------------|------------------|
| Verb lists / vocabulary | Recall + Apply (usage examples) |
| Articles / essays | Explain + Connect (concepts and relationships) |
| Procedures / tutorials | Apply + Explain (steps and reasoning) |
| Theories / concepts | Explain + Connect (understanding and relationships) |

### 2. Question quality rules

- Generate **exactly 15 questions** (4 + 4 + 4 + 3)
- Questions must be specific with clear, unambiguous answers
- Answers should be 1–3 sentences — complete but concise
- No yes/no questions
- Test understanding, not just memorization

### 3. Tags

Choose 2–5 from: `vocabulary` · `grammar` · `procedure` · `command` · `formula` · `definition` · `principle` · `pattern` · `rule` · `technique` · `argument` · `comparison` · `concept` · `relationship` · `example` · `history` · `person`

### 4. Topic naming

- Lowercase with hyphens: `rest-api-basics`, `portuguese-verbs`
- 2–4 words, specific but concise
- Works as a folder name

---

## Topic matching

Before saving, Sofi checks whether the new document belongs in an existing topic folder. A separate LLM call decides:

- **`match:folder-name`** — clearly belongs in an existing folder (same subject or subtopic)
- **`possible:folder-name`** — might belong, but not certain → asks the user
- **`new`** — no existing folder fits → creates a new one

Example: uploading a paper on "AI selfhood" when `ai-consciousness` already exists → returns `match:ai-consciousness`.

---

## Other prompts

The grading prompt (used during quiz sessions) and the session summary prompt (used after sessions end) are in `src/services/grading_service.py` and `src/services/conversation_memory_service.py` respectively.
