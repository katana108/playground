# Playground For Agent Architectures

This repository is a comparative workspace for four conversational agents with different internal structures.

The research question is narrow on purpose:

- when four agents receive the same corpus and similar classes of reflective probes over repeated sessions,
- which architectures show the strongest signs of second-order self-modeling, self-narrative development, synthesis, and theory-of-mind-like behavior?

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

Educational tutor built from the real Sofico project and adapted for this study.

Important characteristics:

- long-term user modeling
- explicit teacher bootstrap
- explicit learner notebook
- learner reflection is already real in the source project
- drafted self-model and dreaming documents already exist
- strongest candidate for research-driven synthesis across sessions
- for this study, may also be extended with research or search steps that are logged explicitly

This repo now contains copied and adapted material from the real Sofico project

### `Sage`

Minimal neurosymbolic agent.

Important characteristics:

- explicit `self_model`
- explicit `user_model`
- explicit `world_model`
- explicit `modulators`, needs, urges and decision making
- explicit `revision_log`
- designed to make its internal state legible

Sage is split into:

- a full 10-stage target architecture
- a smaller 5-stage prototype that should be buildable first

### `Socrates`

Lightweight reflective research agent.

Important characteristics:

- still treated as an agent, not just a single prompt string
- rich philosophical voice and background knowledge
- access to the same corpus and online research
- good at posing questions and noticing contradictions
- lighter structure than Sofico or Sage
- no rich explicit user-model, world-model, or dreaming layer by default
- useful for testing whether a strong role, memory, and research loop can produce reflective behavior without deeper internal modules

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
- mirror-test-like recognition of prior traces
  A mirror-test-like probe means showing the agent an earlier trace, reflection, or answer without attribution and asking whether it recognizes it as its own, and why.
- simple theory-of-mind-like judgments in multi-agent interaction
- corpus integration and synthesis across ideas, notes, and sessions

Architecture-specific focus:

- Sofico is the main offline synthesis / dreaming condition
- Sage is the main explicit motivational-state condition
- Socrates is the main lightweight reflective-agent condition
- Smith is the floor condition

## Experimental Shape

Working shape:

1. Build all four agents first.
2. Run repeated one-to-one sessions with each agent over about one week.
3. Give all four agents access to the same corpus.
4. Use similar classes of probes rather than forcing identical wording.
5. Save state snapshots, summaries, reflection outputs, and revision traces.
6. Run a shorter multi-agent phase over roughly 2 to 3 shared sessions across about 3 days.
7. End with final self-overviews and cross-agent reflections.


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

## Theoretical Grounding

Working ingredients for the theoretical frame:

- computational functionalism
  The study compares what different functional organizations do, rather than making claims about mysterious inner essence.
- self-model theory
  This includes lines of thought associated with Metzinger, where the self is treated as a model the system constructs and uses.
- recursive self-reference and strange-loop style ideas
  These matter because the study is interested in agents representing and revising something about their own representations.
- motivational architecture work
  Especially MetaMo, OpenPsi, and PSI-style modulation, which shape Sage and partly motivate the comparison.
- consciousness-indicator and marker approaches
  This includes work such as Butlin-style indicator thinking, where the question is not "is it conscious?" but "which signs are worth tracking?"
- psychological-style probes
  Mirror-test-like probes, contradiction handling, theory-of-mind-like judgments, and continuity of self-description are all being used as experimental stressors rather than as definitive proofs.

This theoretical frame is still under construction and should be tightened as the study design becomes more concrete.
