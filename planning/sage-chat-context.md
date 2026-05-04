# Sage Chat Context

## Purpose

This document is a handoff context pack for starting a separate chat focused only on building Sage.

It should help a new collaborator, assistant, or separate chat understand:

- what the broader project is
- what Sage is supposed to be
- which documents matter most
- which parts are settled
- which parts are still open

## Short Project Context

This repo is a comparative research playground for four conversational agent architectures:

- Sofico
- Sage
- Socrates
- Smith

The broader project is being prepared as a CIMC demo.

The goal is not to prove consciousness.
The goal is to compare which architectures produce richer and more traceable developmental patterns over repeated conversations.

Main research goals:

- self-modeling
- emotional context sensitivity
- revision instead of simple accumulation
- emergent behavior, especially where internal processing appears to change later behavior
- observer-theory-of-mind-like judgments for the human user and later for other agents

## What Sage Is Supposed To Be

Sage is the most explicitly architectural agent in the set.

She is meant to be:

- a simplified neurosymbolic conversational agent
- modulator-centered
- emotionally sensitive in a structured way
- more inspectable than a normal LLM-driven agent

Sage is not mainly about being the best conversationalist.
She is mainly about making internal motivational change legible.

## Current Design Emphasis

Right now the most important thing to focus on is:

- how modulators change in response to the user's emotional and conceptual state
- how those modulator changes alter later behavior
- how the LLM sits inside that loop

This means the separate Sage chat should not over-focus on generic model updates.
The strongest design question is:

- how can emotional and motivational state become structurally relevant before the response is generated?

## Minimal Practical Picture

At the smallest useful level, Sage should probably include:

- `self_model`
- `user_model`
- `world_model`
- `needs`
- `modulators`
- `memory_log`
- `revision_log`

But the center of gravity is not all state equally.
The center of gravity is:

- modulator reassessment
- action shaping
- traceable behavioral change

## LLM Integration Question

One of the biggest open questions is how the LLM should be integrated.

Current working idea:

- the LLM should not just be a free chatbot with personality pasted on top
- the LLM should be the component that interprets, updates, and expresses state inside a stronger loop

Important practical question:

- which judgments are made by the LLM directly
- which state is stored outside the LLM
- how often modulators are reassessed
- whether action selection is explicit or only reconstructed after generation

## Current Open Questions

The main open questions for Sage are:

- how often each modulator should be reassessed
- how the user's emotional tone maps onto needs and modulators
- whether the first implementation should use separate passes or one combined pass
- how strongly the self-model should matter in the first version
- how explicit the action vocabulary should be
- whether the first version should include only online revision or also a small reflection pass
- how much of OmegaClaw or Hyperon should be treated as future alignment versus present dependency

## Important Source Documents

### Local Editable Docs

- [Repo README](/Users/amikeda/playground/README.md:1)
- [Sage folder README](/Users/amikeda/playground/agents/sage/README.md:1)
- [Sage build draft](/Users/amikeda/playground/planning/sage-build-draft.md:1)
- [Sage full 10-stage architecture](/Users/amikeda/playground/agents/sage/full-10-stage-architecture.md:1)
- [Sage 5-stage prototype](/Users/amikeda/playground/agents/sage/prototype-5-stage.md:1)
- [Consciousness conversation plan](/Users/amikeda/playground/planning/consciousness-conversation-plan.md:1)

### GitHub Links

- [Repo README on GitHub](https://github.com/katana108/playground/blob/main/README.md)
- [Sage README on GitHub](https://github.com/katana108/playground/blob/main/agents/sage/README.md)
- [Sage build draft on GitHub](https://github.com/katana108/playground/blob/main/planning/sage-build-draft.md)
- [Sage full 10-stage architecture on GitHub](https://github.com/katana108/playground/blob/main/agents/sage/full-10-stage-architecture.md)
- [Sage 5-stage prototype on GitHub](https://github.com/katana108/playground/blob/main/agents/sage/prototype-5-stage.md)
- [Consciousness conversation plan on GitHub](https://github.com/katana108/playground/blob/main/planning/consciousness-conversation-plan.md)

### Paper

- [Motivational architecture paper](/Users/amikeda/Downloads/A_Motivational_Architecture_for_Conversational_AGI__2_.pdf)

This paper is the main source for Sage's architecture.

## Current Architecture Direction

The present Sage direction is:

- keep the full 10-stage paper architecture as the conceptual target
- build a compressed 5-stage version first
- prioritize modulator-centered behavior over symbolic complexity
- use explicit traces so later claims about change can be checked

The 5-stage version currently looks like:

1. `Perceive`
2. `Model and Estimate Needs`
3. `Modulate and Appraise`
4. `Respond`
5. `Revise`

But this should be read as provisional rather than final.

## OmegaClaw And Hyperon Status

Current state of knowledge:

- Hyperon is publicly documented enough to treat as a future symbolic substrate
- OmegaClaw in this project is currently paper-grounded and wiki-pending
- public `OpenClaw` material on the web may describe a different project and should not be treated as automatically valid for this work

This means the separate Sage chat should be careful:

- do not assume public OpenClaw docs are the same as OmegaClaw
- wait for updated OmegaClaw / SageClaw / Qwestor material if available

## What A Separate Sage Chat Should Work On

The best use of a separate Sage-only chat is probably:

1. clarify the role of modulators
2. clarify how emotional cues update needs and modulators
3. decide how the LLM should be placed in the loop
4. decide which state objects must exist in version 1
5. define a minimal action vocabulary
6. define a minimal logging format
7. decide what can be real now versus deferred

## Suggested Prompt For A Separate Sage Chat

Use this as a starting point if helpful:

```text
I am building Sage as part of a comparative agent project for a CIMC demo. Sage is meant to be a simplified neurosymbolic conversational agent centered on explicit modulators, explicit self/user/world state, and traceable revision over time.

The most important thing is not generic model updating. The most important thing is how modulators change in response to the user's emotional and conceptual state, and how those changes alter behavior in ways that can be inspected later.

Please help me think through what the smallest real version of Sage could be, how the LLM should be integrated into the loop, how modulators should be reassessed, and what the minimal useful state, action, and logging structure should be.

Use the linked local and GitHub docs as source context, and treat OmegaClaw as paper-grounded and wiki-pending unless newer materials are provided.
```

## Notes

This handoff document should evolve.
It is supposed to make starting a new Sage-focused conversation easy and concrete.
