"""
Document Parser Service
Processes raw documents into personalized study materials using LLM
"""

import os
import logging
import yaml
from datetime import date
from typing import Dict, Any, Optional
from pathlib import Path
import anthropic
import re

from llm_utils import MODEL_DEFAULT, llm_text

logger = logging.getLogger(__name__)


class DocumentParserService:
    """
    Parses documents into study materials considering:
    - User's general level and focus areas
    - Document type (verb lists, articles, etc.)
    - Learning objectives
    """

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = MODEL_DEFAULT  # Use Sonnet for document processing

    def parse_document(
        self,
        content: str,
        user_id: str,
        topic_hint: Optional[str] = None,
        user_instructions: Optional[str] = None,
        data_service = None
    ) -> Dict[str, Any]:
        """
        Parse a document into a study document with questions.

        Args:
            content: Raw document text
            user_id: User who uploaded it
            topic_hint: Optional topic name from user
            user_instructions: Optional specific instructions from user
            data_service: Service to load user config

        Returns:
            {
                "study_document": "markdown content",
                "topic": "topic-name",
                "questions": [...],  # for index update
                "tags": [...],
                "metadata": {...}
            }
        """
        try:
            # Load user context
            user_context = self._load_user_context(user_id, data_service)

            # Build parsing prompt
            prompt = self._build_parsing_prompt(
                content=content,
                user_context=user_context,
                topic_hint=topic_hint,
                user_instructions=user_instructions
            )

            logger.info(f"Parsing document for user {user_id}, topic hint: {topic_hint}")

            # Call LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}]
            )

            study_doc = llm_text(response)

            # Strip markdown code fence if Claude wrapped the output in one
            if study_doc.startswith("```"):
                lines = study_doc.split("\n")
                # Remove first line (```markdown or ```) and last line (```)
                study_doc = "\n".join(lines[1:-1]).strip()

            # Extract metadata from study document
            metadata = self._extract_metadata(study_doc)

            # Parse questions for index
            questions = self._extract_questions(study_doc, metadata["topic"])

            return {
                "study_document": study_doc,
                "topic": metadata["topic"],
                "questions": questions,
                "tags": metadata["tags"],
                "source": metadata.get("source", "uploaded document"),
                "metadata": metadata,
                "raw_source_content": content,
            }

        except Exception as e:
            logger.error(f"Error parsing document: {e}")
            raise

    def _load_user_context(self, user_id: str, data_service) -> Dict[str, Any]:
        """Load user's config to understand their level and focus areas"""
        context = {
            "level": "intermediate",
            "focus_areas": [],
            "learning_style": "balanced"
        }

        if not data_service:
            return context

        try:
            # Try to read user's config.yaml
            from services.local_file_service import LocalFileService
            if isinstance(data_service, LocalFileService):
                config_path = data_service.base_path / data_service._user_folder(user_id) / "config.yaml"
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        context.update({
                            "level": config.get("level", "intermediate"),
                            "focus_areas": config.get("focus_areas", []),
                            "learning_style": config.get("learning_style", "balanced")
                        })
                        logger.info(f"Loaded user context: {context}")
        except Exception as e:
            logger.warning(f"Could not load user config: {e}")

        return context

    def _build_parsing_prompt(
        self,
        content: str,
        user_context: Dict[str, Any],
        topic_hint: Optional[str],
        user_instructions: Optional[str]
    ) -> str:
        """Build LLM prompt for document parsing with user context"""

        from config.personality import get_system_prompt

        sophia_prompt = get_system_prompt()

        level_guidance = {
            "beginner": """
This learner is a beginner. Focus on:
- Clear, simple explanations
- Foundational concepts before advanced ones
- More Recall questions to build vocabulary
- Avoid assuming prior knowledge""",
            "intermediate": """
This learner is at intermediate level. Focus on:
- Balance between facts and understanding
- Connect new concepts to likely existing knowledge
- Equal mix of all question types
- Challenge them to apply knowledge""",
            "advanced": """
This learner is advanced. Focus on:
- Nuanced understanding and edge cases
- More Connect questions to build relationships
- Challenge them with complex applications
- Assume solid foundational knowledge"""
        }

        level = user_context.get("level", "intermediate")
        focus_areas = user_context.get("focus_areas", [])

        focus_section = ""
        if focus_areas:
            focus_section = f"\n**Learner's Focus Areas:** {', '.join(focus_areas)}\n" \
                           "If this document relates to their focus areas, emphasize those connections."

        user_instructions_section = ""
        if user_instructions:
            user_instructions_section = f"\n**Specific Instructions:** {user_instructions}\n"

        topic_section = ""
        if topic_hint:
            topic_section = f"\n**Suggested Topic:** {topic_hint}\n"

        return f"""{sophia_prompt}

You are processing a document to create personalized study materials.

## Learner Profile

**Level:** {level}
{level_guidance.get(level, "")}
{focus_section}

## Source Material

{content}

{topic_section}
{user_instructions_section}

## Your Task

Create a study document following this exact format:

```markdown
---
topic: "[identify the main topic - use lowercase with hyphens, e.g., 'portuguese-verbs' or 'ai-consciousness']"
source: "[title or description of source material]"
doc_type: "[paper | book | article | blog_post | note_set | lesson | transcript | other]"
authors: ["Author One", "Author Two"]
year: 2022
venue: "[journal / site / publisher / source venue if known]"
created: {date.today().isoformat()}
tags: ["tag1", "tag2", "tag3"]
subtopics: ["subtopic-1", "subtopic-2"]
disciplines: ["discipline-1", "discipline-2"]
schools_of_thought: ["school-1"]
theories: ["theory-1"]
key_concepts: ["concept-1", "concept-2", "concept-3"]
keywords: ["keyword-1", "keyword-2", "keyword-3"]
summary_short: "[one sentence summary of the core claim or contribution]"
---

# [Title]

## Learning Notes

### Core Idea

[State the central claim or purpose of the material in 2-4 clear sentences.]

### Why It Matters

[Explain why this material matters for understanding, practice, or future learning.]

## Key Concepts

- **Concept 1:** clear explanation
- **Concept 2:** clear explanation
[Continue as needed. Define important terms, not just list them.]

## Argument / Structure

[Show how the material is organized. For an argument, give the reasoning chain.
For a technical/procedural source, give the process or system structure.]

## Examples

[Include concrete examples, metaphors, or mini-scenarios that make the ideas easier to remember.]

## Connections

[Connect this material to related ideas, prior knowledge, or likely adjacent topics.]

## Open Questions / Watchpoints

[List ambiguities, assumptions, possible objections, or places the learner may need extra care.]

---

## Anki Questions

### Recall

**Q1:** [specific question testing factual knowledge]
**A1:** [concise, complete answer]

**Q2:** [question]
**A2:** [answer]

**Q3:** [question]
**A3:** [answer]

**Q4:** [question]
**A4:** [answer]

### Explain

**Q5:** [question testing understanding - "Why?" "How?" "What happens when?"]
**A5:** [explanation answer]

**Q6:** [question]
**A6:** [answer]

**Q7:** [question]
**A7:** [answer]

**Q8:** [question]
**A8:** [answer]

### Apply

**Q9:** [question testing practical usage - "How would you..." "What would you do if..."]
**A9:** [practical answer]

**Q10:** [question]
**A10:** [answer]

**Q11:** [question]
**A11:** [answer]

**Q12:** [question]
**A12:** [answer]

### Connect

**Q13:** [question about relationships - "How does X relate to Y?" "What connects..."]
**A13:** [relationship explanation]

**Q14:** [question]
**A14:** [answer]

**Q15:** [question]
**A15:** [answer]
```

## Guidelines

1. **Adapt to document type:**
   - Verb lists → Focus on Recall + Apply (usage examples)
   - Articles/essays → Focus on Explain + Connect (concepts and relationships)
   - Procedures/tutorials → Focus on Apply + Explain (steps and reasoning)
   - Theories/concepts → Focus on Explain + Connect (understanding and relationships)

2. **Question quality:**
   - Generate EXACTLY 15 questions (4+4+4+3 across categories)
   - Questions should be specific with clear, non-ambiguous answers
   - Answers should be 1-3 sentences, complete but concise
   - Avoid yes/no questions
   - Test understanding, not just memorization

3. **Tags:** Choose 2-5 relevant tags:
   - Language: vocabulary, grammar
   - Technical: procedure, command, formula, pattern
   - Conceptual: definition, principle, concept, relationship
   - Academic: argument, comparison, theory, example
   - Meta: technique, rule, person, history

4. **Topic naming:**
   - Use lowercase with hyphens (e.g., "rest-api-basics")
   - Be specific but concise (2-4 words max)
   - Should work well as a folder name

5. **Metadata filling:**
   - Fill what you can from the text
   - If a field is not clearly supported, leave it empty or use an empty list
   - Do not invent authors, year, venue, school, or theory

5. **Adapt difficulty to learner level ({level})**

Output ONLY the markdown study document. No other text."""

    def _extract_metadata(self, study_doc: str) -> Dict[str, Any]:
        """Extract frontmatter metadata from study document"""
        metadata = {
            "topic": "unknown",
            "tags": [],
            "source": "uploaded document",
            "doc_type": "",
            "authors": [],
            "year": None,
            "venue": "",
            "subtopics": [],
            "disciplines": [],
            "schools_of_thought": [],
            "theories": [],
            "key_concepts": [],
            "keywords": [],
            "summary_short": "",
            "title": "",
        }

        try:
            # Extract YAML frontmatter
            if study_doc.startswith("---"):
                parts = study_doc.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    raw_topic = str(frontmatter.get("topic", "") or "").strip()
                    # Sanitize: LLMs sometimes leak reasoning into the topic field.
                    # Enforce valid slug format and cap at 5 words.
                    slug = re.sub(r"[^a-z0-9\-]", "-", raw_topic.lower())
                    slug = re.sub(r"-{2,}", "-", slug).strip("-")
                    words = [w for w in slug.split("-") if w][:5]
                    clean_topic = "-".join(words) if words else "unknown"
                    metadata.update({
                        "topic": clean_topic,
                        "tags": self._clean_list(frontmatter.get("tags", [])),
                        "source": frontmatter.get("source", "uploaded document"),
                        "doc_type": str(frontmatter.get("doc_type", "") or "").strip(),
                        "authors": self._clean_list(frontmatter.get("authors", [])),
                        "year": self._coerce_int(frontmatter.get("year")),
                        "venue": str(frontmatter.get("venue", "") or "").strip(),
                        "subtopics": self._clean_list(frontmatter.get("subtopics", [])),
                        "disciplines": self._clean_list(frontmatter.get("disciplines", [])),
                        "schools_of_thought": self._clean_list(frontmatter.get("schools_of_thought", [])),
                        "theories": self._clean_list(frontmatter.get("theories", [])),
                        "key_concepts": self._clean_list(frontmatter.get("key_concepts", [])),
                        "keywords": self._clean_list(frontmatter.get("keywords", [])),
                        "summary_short": str(frontmatter.get("summary_short", "") or "").strip(),
                    })
        except Exception as e:
            logger.warning(f"Could not parse frontmatter: {e}")

        metadata["title"] = self._extract_title(study_doc)
        return metadata

    def _extract_questions(self, study_doc: str, topic: str) -> list:
        """Extract questions from study document for index update"""
        questions = []

        try:
            lines = study_doc.split('\n')
            current_category = None
            current_q_num = None
            current_q_text = None
            current_answer = None

            for line in lines:
                line = line.strip()

                # Detect category headers
                if line in ["### Recall", "### Explain", "### Apply", "### Connect"]:
                    current_category = line.replace("### ", "")
                    continue

                # Detect questions
                if line.startswith('**Q') and ':**' in line:
                    # Start tracking new question (saved only when its answer is found)
                    current_q_num = line.split(':**')[0].replace('**', '')
                    current_q_text = line.split(':**', 1)[1].strip()
                    current_answer = None

                elif line.startswith('**A') and ':**' in line:
                    # Save the question when we hit its answer
                    current_answer = line.split(':**', 1)[1].strip()
                    if current_q_num and current_q_text and current_category:
                        questions.append({
                            "id": f"{topic}.md#{current_q_num}",
                            "text": current_q_text,
                            "answer": current_answer,
                            "category": current_category,
                            "tags": [],
                            "mastery": 0.0,
                            "last_reviewed": None,
                            "next_review": None,
                            "interval": 1,
                            "easiness": 2.5,
                            "reps": 0,
                            "created": date.today().isoformat()
                        })
                        current_q_num = None
                        current_q_text = None
                        current_answer = None

        except Exception as e:
            logger.warning(f"Could not extract questions: {e}")

        logger.info(f"Extracted {len(questions)} questions from study document")
        return questions

    def _extract_title(self, study_doc: str) -> str:
        """Extract the first markdown H1 title from the study document."""
        for raw_line in study_doc.splitlines():
            line = raw_line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _clean_list(self, value: Any) -> list[str]:
        """Normalize frontmatter scalars/lists into a string list."""
        if not value:
            return []
        raw_items = value if isinstance(value, list) else [value]
        cleaned = []
        for item in raw_items:
            text = str(item or "").strip()
            if text:
                cleaned.append(text)
        return list(dict.fromkeys(cleaned))

    def _coerce_int(self, value: Any) -> Optional[int]:
        """Convert optional numeric frontmatter fields."""
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip())
        except Exception:
            return None

    def find_matching_topic(self, topic: str, tags: list, existing_topics: list) -> dict:
        """
        Check if a new document belongs in an existing topic folder.

        Returns:
            {"type": "match", "folder": str}    — clearly belongs in existing folder
            {"type": "possible", "folder": str} — probably belongs but not certain
            {"type": "new", "folder": None}     — should be a new folder
        """
        if not existing_topics:
            return {"type": "new", "folder": None}

        existing_list = "\n".join(f"- {t}" for t in existing_topics)

        prompt = f"""You are organizing study materials into topic folders.

New document topic: "{topic}"
New document tags: {tags}

Existing topic folders:
{existing_list}

Does this new document belong in one of the existing folders?

Rules:
- "match:[folder]" — clearly belongs (same subject, subtopic, or closely related aspect)
  Examples: "ai-selfhood" → "match:ai-consciousness", "portuguese-irregular-verbs" → "match:portuguese-verbs"
- "possible:[folder]" — might belong but you're not certain (loosely related, overlapping)
  Examples: "cognitive-science" when "ai-consciousness" exists — related but distinct enough to ask
- "new" — no existing folder fits well

Respond with ONLY one of these exact formats:
  match:folder-name
  possible:folder-name
  new"""

        try:
            response = self.client.messages.create(
                model=MODEL_DEFAULT,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            answer = llm_text(response).lower().strip('"')
            logger.info(f"Topic matching: '{topic}' → '{answer}'")

            if answer.startswith("match:"):
                folder = answer[6:].strip()
                if folder in existing_topics:
                    return {"type": "match", "folder": folder}
            elif answer.startswith("possible:"):
                folder = answer[9:].strip()
                if folder in existing_topics:
                    return {"type": "possible", "folder": folder}

            return {"type": "new", "folder": None}

        except Exception as e:
            logger.warning(f"Topic matching failed: {e}")
            return {"type": "new", "folder": None}
