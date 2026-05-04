# Sofi V2 Implementation Phases

Last updated: 2026-04-20

## Purpose

This is the main planning document for Sofi V2.

It turns the research notes, architecture discussion, and product goals into a milestone sequence.

The goal is not to copy any single framework.
The goal is to build a tutoring agent that feels alive because it has temporal coherence:

- it remembers what mattered
- it updates its view of the learner over time
- it knows what it is currently doing
- it can use its real capabilities reliably

Metaphor:

We are not trying to write Sofi prettier lines.
We are trying to give her a spine, a memory, and a working desk.

## Core Principle

The main technical property we want is:

**temporal coherence**

Sofi should behave consistently with her own history over time, not just react to the last message.

That means early milestones should prioritize:

- stable teacher identity
- explicit student model
- explicit self-model
- explicit study artifacts
- current focus
- memory updates with revision
- reflection
- orchestration

More than:

- prompt cosmetics
- advanced scheduling
- multi-channel infrastructure
- fancy background systems before the core loop works

## Standard Terms

These are the software terms I recommend we use.

### Orchestrator

The control layer.

It:

1. receives the user turn
2. loads relevant context
3. decides what needs to happen
4. chooses which capability/tool to use
5. updates state and memory
6. produces the final reply

This is software architecture, not just one prompt.

### Tool

A callable function or interface the orchestrator can invoke.

Examples:

- parse a document
- explain an artifact
- create cards
- update the student model
- run review

So yes: a tool is basically a callable application function.

### Capability

A user-facing ability implemented by one or more tools plus rules/context.

Examples:

- "Sofi can explain what you uploaded"
- "Sofi can create notes and cards"
- "Sofi can run spaced repetition review"

A capability is what the product can do.
A tool is one of the mechanical parts used to do it.

### Handler

The current app's older workflow controller pattern.

Examples in the current codebase:

- `onboarding_handler.py`
- `curriculum_handler.py`
- `explanation_handler.py`
- `study_handler.py`

In V2, some handler logic will be reused, but the orchestrator should become the main owner of turn flow.

### Service

Reusable backend logic that is not itself the main conversational owner.

Examples:

- memory service
- profile service
- SM-2 scheduler
- document parsing service

### Bootstrap Files

Stable files loaded as foundational context.

For Sofi this means:

- teacher identity file
- student model file(s)
- maybe capability declarations or policy files

So yes, `SOUL.md` is a good name for the teacher bootstrap file.
We are partly moving in this direction already with the planning specs, but we are **not yet** runtime-loading a proper SOUL/bootstrap identity file.

### Skill

A capability bundle:

- tool(s)
- rules/prompt fragments
- required context
- contract for inputs/outputs

We are **not** using a formal skill system in Sofi yet.
My recommendation is:

- milestone 1: build a capability registry and tool contracts
- milestone 2 or 3: formalize some of those as skills if it still feels useful

That is the cleaner order.

## What We Already Have And Will Preserve

Keep and reuse:

- SM-2 review logic
- upload + parsing pipeline
- curriculum/study-plan generation logic
- explanation flow
- quiz/review flow
- learner profile and memory services where useful

We are restructuring the control system, not throwing away the useful machinery.

## Research Ideas We Are Actually Using

From the research notes, these are the ideas I recommend we adopt.

### Adopt in simplified form early

- stable teacher identity file (`SOUL.md`-style)
- explicit student model separate from teacher model
- explicit self-model separate from teacher identity
- current focus as an active hierarchical path
- structured memory updates with `ADD / UPDATE / NOOP`
- reflection that turns observations into beliefs
- separate stored history from LLM context view

### Adopt later in richer form

- memory scoring by recency + importance + relevance
- scheduled dreaming / deep synthesis / weekly REM-style passes
- principled compaction with multiple triggers
- a richer task tree beyond the active path
- formal skill bundles if the capability registry alone becomes too loose

### Not first-priority for Sofi

- multi-channel session-key architecture
- infrastructure patterns that matter mainly for large gateway systems
- overly elaborate background jobs before the tutoring loop is reliable

## Inner Continuity Addition

This is now part of the V2 direction.

The current distinction is:

- `SOUL.md` = stable core identity
- `SELF_MODEL.md` = conscious self-observation
- `DREAMING.md` = offline associative synthesis

Why this matters:

- it gives Sofico an explicit introspection layer instead of only a teacher model
- it supports demo goals around self-model revision, dreaming synthesis, and introspective consistency
- it gives a cleaner place for self-improvement observations than either `SOUL` or the student model

First implementation rule:

- create the documents and planned triggers now
- do not deeply wire them into runtime behavior yet
- integrate them after the current tutoring slice is more stable

## Milestone 1 — First Working V2 Brain

This is the first real target.

It should give Sofi:

- one stable identity
- one explicit student model
- one explicit domain/artifact layer
- one current focus
- one orchestrator-driven turn loop
- memory that can actually evolve

### 1. Teacher Bootstrap File

Build now:

- a stable teacher identity file, ideally `SOUL.md`
- separate from learner data
- separate from routing logic
- separate from capability declarations

Why now:

- this becomes the canonical source of "who Sofi is"
- stops rebuilding identity from fragile profile fragments

### 2. Student Model V1

Build now:

- one explicit student model structure
- likely sections:
  - identity
  - goals_and_constraints
  - stated_preferences_about_self
  - inferred_profile
  - progress_patterns
  - relationship_memory
  - metadata

Why now:

- this is the learner notebook
- without it, Sofi keeps meeting the same person as if it were the first day of school

### 3. StudyArtifact Model V1

Build now:

- explicit artifact records with ids and links

Examples:

- uploaded source
- parsed notes
- flashcards
- quiz set
- lesson
- study guide
- study plan

Why now:

- this is how Sofi stops losing track of what she already made

### 4. CurrentFocus Active Path

Build now:

- a hierarchical active path, not just one loose variable

Example:

- root goal
- current module
- current lesson
- current action

My recommendation:

- build the active path first
- do not try to build a fully general task-memory engine yet

Why:

- it gives most of the value with much less complexity

### 5. Capability Registry

Build now:

- explicit list of what Sofi can do
- each capability should declare:
  - what it does
  - what inputs it needs
  - what artifacts/state it may read
  - what it returns

Examples:

- explain
- parse document
- create notes/cards
- build or update study plan
- run review
- show progress
- research when needed

Why now:

- right now Sofi often has working code but a weak self-model

### 6. Student Memory Update Engine

Build now:

- after a meaningful session, extract candidate learner updates
- each candidate becomes:
  - `ADD`
  - `UPDATE`
  - `NOOP`

My recommendation:

- do **not** implement hard `DELETE` in milestone 1
- use revision, supersession, or archival instead

Why:

- deletion is dangerous early
- tutoring memory should be revisable before it becomes destructive

### 7. Reflection Pass

Build now in a simple version:

- after meaningful sessions or enough accumulated observations
- synthesize observations into higher-level beliefs

Examples:

- "the learner avoids apply questions when uncertain"
- "examples before abstraction help this learner recover confidence"

Why now:

- this is what turns a log into a living model

Important:

I agree with you that reflection belongs in milestone 1.
I do **not** think the advanced dreaming system belongs in milestone 1.

### 8. Orchestrator Turn Loop

Build now:

- orchestrator loads:
  - teacher model
  - student model
  - current focus
  - relevant artifacts
  - active conversation state
- orchestrator decides:
  - reply directly
  - explain
  - parse/upload
  - create notes/cards
  - build/update plan
  - review
  - research

Why now:

- this is the real brain

### 9. Stored History vs Context View

Build now:

- store more than we send
- keep the full useful record on disk
- send only the relevant view to the LLM

Why now:

- otherwise the context window becomes either too dumb or too bloated

My recommendation:

- milestone 1 should include a simple, principled separation here
- milestone 3 can make compaction much more sophisticated

## Milestone 2 — Memory Depth And Skill Shaping

This is where Sofi starts becoming deeper, not just more stable.

### 1. Dreaming / Reflection System V2

Build here:

- richer reflection schedule
- maybe session-count-based first
- later clock-based if still useful

Examples:

- light consolidation
- deeper synthesis of recurring patterns
- weekly lookback

Why here:

- first we need stable memory objects worth dreaming about

### 2. Formal Skill Bundles

Build here if needed:

- package capabilities as skills
- each skill can include:
  - tool contract
  - context requirements
  - prompt fragments
  - output contract

Why here:

- first build the capability registry
- then formalize it into reusable bundles if the system benefits

### 3. Richer Student Memory Semantics

Build here:

- decide whether `DELETE` becomes a true operation
- add contradiction handling and superseded-memory rules

Why here:

- better after we see real memory behavior

### 4. Better Retrieval Logic

Build here:

- move beyond simple relevance selection
- improve how student beliefs and artifacts enter context

Why here:

- retrieval quality matters more once the memory corpus grows

## Milestone 3 — Efficiency And Long-Horizon Coherence

This is where we make Sofi cheaper, cleaner, and more scalable.

### 1. Principled Compaction

Build here:

- explicit compaction triggers
- preserve full history on disk
- compress only the LLM context view

Why here:

- important, but it depends on the earlier storage/context split already existing

### 2. Memory Scoring V2

Build here:

- recency
- importance
- relevance
- weighted retrieval into context

Why here:

- this is powerful, but it sits on top of stable memory and reflection

My pushback:

- I would not block milestone 1 on a full vector-and-ranking memory system
- a lighter first version is enough to start making Sofi coherent

### 3. Richer CurrentFocus Tree

Build here:

- fuller parent/child tree
- better navigation across goals, modules, lessons, and sub-actions

Why here:

- active path first, richer tree later

## What We Are Deliberately Not Doing First

I want this written clearly:

We are **not** making these milestone-1 blockers:

- multi-channel architecture
- full OpenClaw-style gateway infrastructure
- full advanced dreaming schedule
- hard delete memory semantics
- fully general task-memory engine
- heavy compaction system before storage/context separation exists

These may become useful later, but they are not the first bones.

## Recommended Milestone Order

If I reduce everything to the real spine, my recommendation is:

1. `SOUL.md` teacher bootstrap file
2. student model V1
3. study artifact model V1
4. current focus active path
5. capability registry
6. student memory update engine (`ADD / UPDATE / NOOP`)
7. reflection pass V1
8. orchestrator turn loop
9. stored-history vs context-view split
10. milestone-2 dreaming / skills / richer memory
11. milestone-3 compaction / scoring / richer task tree

## Questions To Resolve Before Implementation

These are the only questions I think are still worth your answer before we start coding this milestone path.

1. For milestone 1 reflection, do you want the trigger to be:
   - after every meaningful study session
   - or after every N meaningful sessions

My recommendation:

- after every meaningful study session
- but skip trivial chats and tiny one-turn interactions

2. For the first student memory update engine, are you comfortable with:
   - `ADD`
   - `UPDATE`
   - `NOOP`
   - and a "superseded" flag instead of true delete

My recommendation:

- yes
- that is safer than early hard deletion

3. For milestone 1 skills, do you want to:
   - just build the capability registry first
   - or formalize skills immediately

My recommendation:

- capability registry first
- formal skills in milestone 2 unless we discover we truly need them earlier
