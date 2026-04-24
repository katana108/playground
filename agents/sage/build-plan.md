# Sage Build Plan

This file is the practical build order for Sage.

## Minimum Viable Build

1. Define the state schema.
2. Define the five-stage turn loop.
3. Save one state snapshot per important session.
4. Save one revision log per important session.
5. Add a small offline reflection pass.

## First Implementation Targets

- `self_model`
- `user_model`
- `world_model`
- `modulators`
- `memory_log`
- `revision_log`

These six objects are enough to make Sage legible.

## Suggested First Files

- `state_schema.yaml`
- `sample_state.yaml`
- `reflection_prompt.md`
- `sample_trace.md`

These files do not exist yet, but they would make the architecture much easier to reason about.

## Stretch Targets

- richer modulator logic
- candidate-action layer
- better post-turn evaluation
- stronger offline synthesis
- roundtable-specific theory-of-mind-like notes

## Risk Control

Do not try to build a grand symbolic system before there is a saved trace worth looking at.

Prefer:

- small real state
- clear diffs
- one believable reflection pass

Over:

- abstract machinery with no evidence trail
