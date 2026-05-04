# Sofi V2 Student Model Spec

Last updated: 2026-04-14

## Why This Exists

This document defines the **student model** as a distinct domain in Sofi's architecture.

My recommendation is that Sofi v2 should be built around three clear domains:

1. **Teacher model**
   Sofi's identity, teaching behavior, orchestration rules, and capabilities
2. **Student model**
   What Sofi knows about the learner and how the learner learns
3. **Domain knowledge**
   The actual study material, notes, plans, lessons, cards, uploaded files, and topic knowledge

My answer:

Yes, mostly.
I recommend thinking of domain knowledge as:

- the artifacts themselves
- plus the relationships between them

So not just "the files exist", but also:

- which notes came from which upload
- which cards came from which notes
- which lesson belongs to which plan
- which artifact is the current focus

Metaphor:

Sofi should not keep the teacher, the student, and the textbook in the same drawer.

## Goal Of The Student Model

The student model should help Sofi answer questions, plan learning, and teach more naturally by giving her a stable picture of the learner.

It is not just a settings file.
It is a living profile of the learner.

## What The Student Model Should Contain

### 1. Identity

Stable learner identity details.

Examples:

- learner name
- preferred way of being addressed
- current stage / level
- relevant background knowledge

### 2. Stated Preferences

Things the learner explicitly asked for.

Examples:

- preferred way of being addressed
- stated goals
- declared time constraints
- subject interests
- explicit dislikes or boundaries
- self-described confidence or comfort level

My answer:

I agree with your correction.
Teaching style belongs mostly in the teacher model, not the student model.
The student model should stay about the learner.

These are explicit and should have high priority.

### 3. Inferred Learning Profile

This is the AI-written learner interpretation layer.

Examples:

- likely learning style
- what helps them understand
- what tends to confuse them
- how much structure they seem to need
- how they respond to correction
- resistance or avoidance patterns
- what usually re-engages them

Important rule:

This layer should be treated as **inference**, not absolute truth.

It should be updateable and revisable.

My answer:

Agreed on regular updates.
My recommendation is:

- after meaningful study sessions
- after important learner disclosures
- after repeated evidence of a pattern

I do not recommend token count as the primary trigger.
Session/event-based updates are cleaner and more explainable.

### 4. Current Learning State

This is the learner's current position.

Examples:

- active subject
- active study plan
- current lesson
- current focus topic
- what was just studied
- what needs review next

My answer:

I mostly agree with your pushback.
I think this concept exists, but I no longer think it should be a primary student-model section.

Recommendation:

- move most of "current learning state" into orchestration state / current focus / domain knowledge
- keep only persistent learner-relevant state here if it matters across sessions

So this section should be minimized conceptually and not treated as a core student-model drawer.

### 5. Progress And Struggle Patterns

Patterns gathered over time.

Examples:

- topics they repeatedly miss
- topics they move through quickly
- retention weak spots
- confidence issues
- pacing issues

This helps Sofi become a real tutor rather than a stateless explainer.

My answer:

Strongly agreed.
Progress should be:

- part of the student model
- visible as a capability
- demonstrable to the learner

So yes: progress tracking is both memory and product behavior.

### 6. Relationship Memory

This is the conversational continuity layer.

Examples:

- notable goals
- relevant work/life context
- preferred study rhythm
- ongoing emotional context if relevant to learning

This should stay bounded and useful, not become a diary of everything.

My answer:

Partly agreed.

I agree that:

- goals belong in the main learner file
- preferred study rhythm is not important enough right now
- emotional context should start simple

My recommendation is to narrow this section to:

- trust / conversational comfort level
- ongoing emotional context when relevant to learning
- a few bounded relational notes that actually improve tutoring


## Suggested Structure

My recommendation is that the student model should eventually be represented as one clean object, even if it is saved across multiple files underneath.

Conceptual sections:

- `identity`
- `preferences`
- `inferred_profile`
- `progress_patterns`
- `relationship_memory`
- `metadata`

Updated recommendation:

- `identity`
- `goals_and_constraints`
- `stated_preferences_about_self`
- `inferred_profile`
- `progress_patterns`
- `relationship_memory`
- `metadata`

Keep most "current learning state" in orchestration/domain layers instead.

## Important Distinction

The student model is **not** the same as:

- the teacher model
- the current conversation state
- the study artifacts

It informs those things, but it is not identical to them.

### Teacher model

Answers:

- who is Sofi?
- how should she behave?
- what can she do?

### Student model

Answers:

- who is this learner?
- how do they learn best?
- what are they trying to do?
- what patterns matter for teaching them well?

### Domain knowledge

Answers:

- what are we actually studying?
- what files, notes, cards, plans, and lessons exist?

## How Sofi Should Use It

My recommendation:

Before producing a meaningful tutoring answer, Sofi should check the student model in the same way a good tutor glances at their notes before speaking.

That does not mean quoting it every time.
It means using it as background context.

Examples:

- for a normal explanation:
  use the learner's current level and inferred learning profile

- for a study plan:
  use the learner's goal, pace, and prior struggles

- for feedback:
  use the learner's sensitivity and relevant progress patterns

- for confusion like "explain this":
  use the student model plus current focus plus domain artifacts

## Updating Rules

The student model should be updated from two sources:

### 1. Explicit updates

If the learner clearly says something:

- "I only have 20 minutes a day"
- "I am a beginner"
- "I care about psychology and consciousness"
- "I get discouraged when I feel stupid"

that should update the explicit preference layer.

### 2. Inferred updates

If Sofi notices repeated patterns over time:

- the learner keeps needing examples before abstractions
- the learner does better with shorter chunks
- the learner gets discouraged after a certain type of correction

that can update the inferred profile layer.

Important rule:

Explicit learner statements should usually outrank inference.

## Suggested Safety Rule

My recommendation is that inferred student-model updates should be:

- concise
- evidence-based
- revisable
- never overly psychological or invasive

This is a tutor profile, not a therapy file.

## Integration With The Rest Of The Structure

This document fits into the v2 structure like this:

- **Teacher model**
  defined by the persona spec and future orchestrator prompt structure

- **Student model**
  defined here

- **Domain knowledge**
  represented by `StudyArtifact`, `CurrentFocus`, study plans, uploaded files, notes, cards, and lessons

The orchestrator should combine all three when deciding what to do and how to speak.

## Suggested Next Build Step

My recommendation is:

1. keep this as a design spec for now
2. next define the **teacher model spec** in parallel with this
3. then define how the orchestrator loads:
   - teacher model
   - student model
   - domain knowledge
4. only after that wire those into prompt building and turn handling

## Test Gate For This Step

This step is complete when:

- the student model is clearly separated from teacher model and domain knowledge
- we agree what belongs inside it
- we can use this as input to the future orchestration layer
