# Sage Dev Brief

## Goal

Build Sage as a small experimental agent for the study.

Main point:

- explicit internal state
- explicit modulator change
- response selection shaped by that change
- readable logs

This is not full OmegaClaw.
It is a buildable Sage v1.

## What Sage Must Show

For each turn, Sage should:

1. detect the user's emotional and conceptual state
2. estimate active needs
3. update modulators
4. generate at least 3 candidate responses
5. choose one and log why
6. save the updated state

## Core State

```yaml
self_model:
  role:
  current_self_description:
  active_limits:
  tensions:
  recent_revisions:

user_model:
  emotional_state:
  confusion_points:
  needs:
  trust_level:
  recurring_patterns:

world_model:
  current_task:
  topic:
  constraints:
  risk_level:
  available_actions:

needs:
  competence:
  uncertainty_reduction:
  affiliation:
  affinity:
  legitimacy:
  nurturing:
  aesthetic_coherence:

modulators:
  valence:
  arousal:
  dominance:
  resolution_level:
  focus:
  exteroception:
```

## Turn Loop

1. `Perceive`
Read user input, prior state, recent memory.

2. `Estimate`
Update self, user, world, and needs.

3. `Modulate`
Recompute all 6 modulators and log deltas.

4. `Respond`
Generate 3 candidates, score them, choose one.

5. `Revise`
Save state, save trace, update preferences for future turns.

## LLM Role

The LLM is not the whole agent.
It is one component inside the loop.

Use it for:

- interpreting user input
- estimating needs
- helping update state
- generating response candidates
- maybe scoring candidates

Do not use it as the only memory.

## Required Output Per Turn

Save:

- input
- state before
- needs before / after
- modulators before / after
- 3 candidate responses
- selected response
- reason for selection
- state after

## MVP Acceptance Criteria

Sage v1 is good enough if:

- one turn loads prior state
- user emotion affects needs
- needs affect modulators
- modulators affect response choice
- 3 candidates are generated
- one candidate is selected with a reason
- the full trace is saved

## Out Of Scope

- full Hyperon reasoning
- full dreaming system
- web app
- deployment
- multi-agent orchestration inside Sage

## Suggested Build Order

1. state schema
2. single-turn loop
3. candidate generation + selection
4. logging
5. multi-turn persistence
6. optional reflection pass

## Questions For The Dev

- Which state should be plain YAML/JSON versus Python objects?
- Should candidate scoring be rule-based, LLM-based, or mixed?
- What is the simplest clean logging format?
- Should v1 use one LLM pass or several smaller passes?
