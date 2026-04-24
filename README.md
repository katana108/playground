# Playground For Agent Architectures

This repository is a comparative workspace for four conversational agents with different internal structures.

The research question is narrow on purpose:

- when four agents receive the same corpus and similar classes of reflective probes over repeated sessions,
- which architectures show the strongest signs of second-order self-modeling, self-narrative development, memory revision, offline synthesis, and theory-of-mind-like behavior?

This repo is meant to be edited as the experiment evolves. It is not only a code repository. It is also the lab notebook, protocol draft, architecture map, and evidence-planning folder.

## Repository Map

Top-level folders:

- `agents/`
  One folder per agent condition.
- `planning/`
  Study protocol, hypotheses, and implementation sequencing.
- `docs/`
  Comparison tables and summary documents.
- `examples/`
  Probe examples, roundtable prompts, and scene directions.
- `tests/`
  Evaluation rubric, logging expectations, and run conventions.

## The Four Agent Conditions

### `Sofico`

Educational tutor with explicit learner modeling, reflection, and a documented but not yet fully runtime-wired self/dreaming layer.

Important characteristics:

- long-term user modeling
- explicit teacher bootstrap
- explicit learner notebook
- reflection engine already exists in the real Sofico codebase
- self-model and dreaming documents already exist in the real Sofico codebase
- strongest candidate for research-driven synthesis across sessions

This repo now contains copied and adapted material from the real Sofico project so the notes can be edited here directly.

### `Sage`

Minimal neurosymbolic agent.

Important characteristics:

- explicit `self_model`
- explicit `user_model`
- explicit `world_model`
- explicit `modulators`
- explicit `revision_log`
- designed to make its internal state legible

Sage is split into:

- a full 10-stage target architecture
- a smaller 5-stage prototype that should be buildable first

### `Socrates`

Reflective prompt-centered agent.

Important characteristics:

- still treated as an agent, not just a single prompt string
- rich philosophical voice
- good at posing questions and noticing contradictions
- no strong symbolic self-model by default
- good contrast condition for testing whether style can mimic depth

### `Smith`

Baseline chatbot.

Important characteristics:

- same materials as the other agents
- minimal personality
- no explicit self-model
- no explicit offline synthesis
- useful as the floor condition

## Working Scientific Aim

The study does not try to prove consciousness.

It compares four architectures to see which ones produce more interesting and more inspectable developmental traces related to protoconsciousness research.

Main focus areas:

- second-order self-modeling
- self-narrative change
- revision rather than accumulation
- offline reflection or dreaming
- mirror-test-like recognition of prior traces
- simple theory-of-mind-like judgments in multi-agent interaction

## Experimental Shape

Working shape:

1. Run repeated one-to-one sessions with each agent over about one week.
2. Give all four agents access to the same corpus.
3. Use similar classes of probes rather than forcing identical wording.
4. Save state snapshots, reflection outputs, and revision traces.
5. End with a final roundtable among the agents.

The roundtable is the capstone scene, not the main evidence.
The main evidence should come from the accumulated traces.

## What To Read First

If you are new to the repo, read these in order:

1. `planning/study-design.md`
2. `planning/hypotheses.md`
3. `docs/agent-comparison.md`
4. `agents/sofico/README.md`
5. `agents/sage/README.md`
6. `examples/probe-directions.md`
7. `examples/agent-party.md`

## Source-Of-Truth Rule

For Sofico in particular, this repo should not invent capabilities that do not exist.

The playground copies and adapts material from the real Sofico project, especially:

- bootstrap identity
- learner model
- reflection engine
- self-model document
- dreaming document
- current planning notes

If a feature is only documented and not yet wired into runtime, say so explicitly.

## Current State

What is already here:

- the 4-agent research framing
- detailed Markdown notes for all four agents
- copied/adapted Sofico source material
- Sage target and prototype structure
- probe and roundtable plans
- first-pass study protocol and evaluation rubric

What still needs real implementation:

- Sage state and loop
- actual logging format
- consistent run harness across agents
- saved traces from real sessions
