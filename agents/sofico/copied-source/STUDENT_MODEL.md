# STUDENT MODEL

Copied from the Sofico source project on 2026-04-24 for local editing inside the playground.

## Purpose

This file is the human-readable student model for Sofico.

It shows what the system knows, believes, and is tracking about the learner.

It should be readable by the learner.
It should not sound creepy, over-psychological, or overly technical.

This file is the readable companion to `student_model.yaml`.

## What Goes Here

### Identity

Stable learner details.

Examples:

- name
- preferred form of address
- gender
- relevant background
- topic-specific proficiency when available

### Goals And Constraints

What the learner wants to study and what shapes that work.

Examples:

- current study goals
- preferred subjects
- current priorities
- practical constraints that matter for teaching

### Stated Preferences About Self

Things the learner explicitly said about themselves or how they want to learn.

Examples:

- prefers direct feedback
- likes examples first
- wants less wordiness
- beginner in Python

This section has high trust.
If the learner says it directly, it should outrank inference.

### Current Tutor Inferences

What Sofico currently infers from repeated evidence.

Examples:

- benefits from examples before abstraction
- tends to disengage when explanations get too long
- responds well to clear correction

This section must stay evidence-based and revisable.

### Progress Patterns

Longer-term patterns in the learner's study process.

Examples:

- recurring strengths
- recurring struggles
- topics improving over time
- retention weak spots

This section should eventually connect to the progress capability/tool.

### Relationship Memory

Bounded continuity notes relevant to tutoring.

Examples:

- inferred trust level
- inferred emotional context when relevant to learning
- relational notes that improve future teaching

This should stay narrow and useful.

### Metadata

System details such as:

- when this file was created
- when it was last updated
- how entries were added or revised

## How It Gets Populated

### During Onboarding

Populate:

- identity
- goals and constraints
- stated preferences about self

These come from what the learner says directly.

### After Meaningful Sessions

Populate or revise:

- current tutor inferences
- progress patterns
- relationship memory

This happens through:

- observation extraction
- `ADD`
- `UPDATE`
- `NOOP`
- reflection

## Important Rule

Explicit learner statements beat inference.

If the learner directly says something about how they want to learn, that should override weaker inferred patterns unless they later change it.

## Tone Rule

This file should describe the learner respectfully.

Do not use:

- clinical overreach
- fake certainty
- unnecessary personality diagnosis

Use:

- concise observations
- evidence-backed inferences
- revisable language
