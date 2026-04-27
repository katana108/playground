# Sage Build Plan

This file is the practical build order for Sage.

## Minimum Viable Build

1. Define the state schema `X = (G, N, M, W, S, U)`.
2. Define the five-stage turn loop.
3. Save one state snapshot per important session.
4. Save one revision log per important session.
5. Add the smallest usable action-selection layer.
6. Only add a small reflection pass if time allows.

## First Implementation Targets

- `self_model`
- `user_model`
- `world_model`
- `needs`
- `modulators`
- `memory_log`
- `revision_log`

These objects are enough to make Sage legible.

## Suggested First Files

- `state_schema.yaml`
- `sample_state.yaml`
- `sample_needs_and_modulators.yaml`
- `action_schemas.md`
- `reflection_prompt.md`
- `sample_trace.md`

These files do not exist yet, but they would make the architecture much easier to reason about.

## Stretch Targets

- richer need-to-modulator aggregation
- candidate-action layer with typed abstract actions
- better post-turn evaluation
- optional reflection pass
- roundtable-specific theory-of-mind-like notes

## Risk Control

Do not try to build a grand symbolic system before there is a saved trace worth looking at.

Prefer:

- small real state
- clear diffs
- one believable action selection story

Over:

- abstract machinery with no evidence trail
