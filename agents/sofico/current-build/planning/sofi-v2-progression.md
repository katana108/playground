# Sofi V2 Progression

Last updated: 2026-04-13

## What Sofi Has Now

Sofi already has important working pieces:

- conversational chat routing
- onboarding/customization
- document upload and parsing
- explanation flow
- curriculum / study-plan generation
- quiz / spaced repetition with SM-2
- learner profile and memory files

So this is not a blank-slate project. The parts exist.

## What Is Broken

The main problem is not lack of features. It is lack of clean coordination.

Current pain points:

- too many handlers compete for the same message
- conversational behavior and capability behavior are not joined cleanly
- Sofi sometimes forgets or denies capabilities that already exist
- exact wording and stale state still create loops or confusion
- artifacts like notes, cards, lessons, and uploaded files are not treated as first-class shared objects

In short:

Sofi can do many things, but she does not yet have one reliable brain that knows what she has, what the user means, and what tool to use next.

## What We Keep

We want to preserve as much of the existing system as possible.

Keep:

- SM-2 review logic
- upload/parsing pipeline
- curriculum generation logic
- explanation flow
- quiz flow
- learner profile and memory services

We are not trying to throw away the machine. We are trying to rebuild the control panel.

## What We Restructure

We plan to add a clean orchestration layer above the current handlers/services.

This orchestration layer will:

1. read the incoming turn
2. load the relevant state
3. determine intent
4. determine current focus
5. choose the right capability
6. update state and artifacts
7. produce the final conversational reply

This is a software architecture layer, not “just a better prompt” and not a separate agent personality.

## New Explicit Models

Two important missing models should become explicit first:

### 1. CurrentFocus

This answers:

- what are we talking about right now?
- which file / lesson / plan / topic does “this” refer to?

Examples:

- active uploaded PDF
- active lesson
- active curriculum
- active topic under explanation

### 2. StudyArtifact

This is any saved learning object Sofi creates or uses.

Examples:

- uploaded source file
- parsed notes
- flashcards / Anki-style cards
- quiz set
- generated lesson
- study guide

Right now these exist in folders and workflows, but not as a clean shared model.

## Recommended Direction

Build a new orchestration subsystem inside this repo and wrap the existing capabilities behind it.

Suggested principle:

- one Sofi
- one orchestrator
- many capabilities behind it

This is closer to how well-designed agent systems work: one source of truth for routing and state, not many half-independent flows.

## First V2 Build Step

Start by defining:

- orchestrator interface
- CurrentFocus model
- StudyArtifact model

Then connect existing capabilities through thin wrappers/adapters:

- document parsing
- explanation
- curriculum
- review / quiz

The goal is not to replace features first.
The goal is to make them legible, connected, and reliable.

