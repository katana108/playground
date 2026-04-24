# Playground For Agent Architectures

This repository is a working playground for comparing conversational agents with different architectures.

The current project focus is a comparative experiment about protoconsciousness-relevant signs in conversational agents, especially:

- second-order self-modeling
- self-narrative development
- memory revision
- offline reflection or "dreaming"
- mirror-test-like probes
- simple theory-of-mind-like behavior in multi-agent interaction

This is not yet a finished product repo. It is a research workspace: part implementation source, part architecture notebook, part experiment design.

## What Lives Here

- `agents/`
  Separate folders for each agent condition.
- `planning/`
  Study protocol, hypotheses, week-long test structure, and implementation planning.
- `docs/`
  Cross-agent comparison documents and submission-facing summaries.
- `examples/`
  Probe ideas, scene directions, and possible experiment structures.
- `tests/`
  Notes on how the experimental runs should be exercised and compared.

## The Four Agent Conditions

### `Sofico`

Educational tutor architecture.

Core identity:

- tracks the student over time
- asks calibration questions about what the learner understands
- forms unusual conceptual links
- is meant to ingest research materials and synthesize them
- is the strongest candidate for dreaming / offline synthesis in the current lineup

In this repo, Sofico documents should separate:

- what already exists in the current Sofico codebase
- what should be adapted into this playground
- what future architecture is desired but not yet built

### `Sage`

Minimal neurosymbolic architecture.

Core identity:

- explicit self-model
- explicit user-model
- explicit world-model
- explicit modulators when feasible
- explicit self-model revision over time

Sage is intentionally split into:

- a full future architecture based on the 10-stage motivational design
- a smaller 5-stage prototype that can realistically be built first

### `Socrates`

Reflective prompt-centered agent.

Core identity:

- still an agent, not just a paragraph prompt
- strong philosophical voice and self-reflective language
- no explicit symbolic self-model object like Sage
- useful as a contrast condition: can style alone create the appearance of deep introspection?

### `Smith`

Baseline conversational condition.

Core identity:

- plain chatbot
- same materials as the other agents
- minimal personality
- no explicit developmental machinery beyond prompt and ordinary conversation history

Smith matters because otherwise every improvement can hide inside style and theater.

## Scientific Aim

The aim is not to claim consciousness.

The aim is to compare four architectures and see which ones produce richer and more inspectable developmental traces relevant to future research on protoconsciousness.

Working focus:

- does explicit self-model revision matter?
- does offline reflection or dreaming matter?
- do prompt-centered agents sound deeper than they structurally are?
- what changes over repeated sessions rather than one-shot prompts?

## Planned Experimental Shape

Phase 1:

- each agent interacts over repeated sessions across about one week
- all agents get access to the same consciousness-related materials
- similar classes of probes are used across agents
- findings are collected from longitudinal traces, not single responses

Phase 2:

- final multi-agent conversation
- agents model one another
- agents discuss what they are, how they changed, and what they think the others are missing

The party at the end is the capstone, not the main evidence.

## How To Navigate This Repo

If you want:

- the big-picture map, start here in `README.md`
- the experiment design, go to [planning/study-design.md](/Users/amikeda/playground/planning/study-design.md:1)
- the core hypotheses, go to [planning/hypotheses.md](/Users/amikeda/playground/planning/hypotheses.md:1)
- the agent comparison matrix, go to [docs/agent-comparison.md](/Users/amikeda/playground/docs/agent-comparison.md:1)
- possible probe scenes, go to [examples/probe-directions.md](/Users/amikeda/playground/examples/probe-directions.md:1)
- the final roundtable ideas, go to [examples/agent-party.md](/Users/amikeda/playground/examples/agent-party.md:1)

For each agent:

- Sofico overview: [agents/sofico/README.md](/Users/amikeda/playground/agents/sofico/README.md:1)
- Sage overview: [agents/sage/README.md](/Users/amikeda/playground/agents/sage/README.md:1)
- Socrates overview: [agents/philosopher/README.md](/Users/amikeda/playground/agents/philosopher/README.md:1)
- Smith overview: [agents/baseline/README.md](/Users/amikeda/playground/agents/baseline/README.md:1)

## Strategy Notes

This playground should stay strategically narrow.

Bad strategy:

- trying to build a grand theory of machine consciousness in one month
- mixing too many uncontrolled differences between agents
- relying on vibes instead of saved traces

Good strategy:

- keep the compared conditions legible
- keep the evidence inspectable
- separate what is built now from what is aspirational
- collect traces that can be shown on screen later

## Status

Current status:

- documentation scaffold created
- Sofico notes linked to actual source documents in `/Users/amikeda/Smithy/sofi/`
- Sage planning seeded from the motivational paper and reduced prototype plan
- Socrates and Smith defined as contrast conditions

Implementation still to come.
