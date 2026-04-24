# Sage Build Plan

This file is the practical build order for Sage.

## Minimum Viable Build

1. Define the state schema.
2. Define the per-turn update flow.
3. Save state snapshots after each important session.
4. Add a reflection pass after multiple sessions.
5. Add simple visual or textual diffs for saved evidence.

## First Implementation Targets

- `self_model`
- `user_model`
- `world_model`
- `modulators`
- `memory_log`
- `revision_log`

## Stretch Targets

- stronger modulator logic
- candidate-action layer
- richer offline synthesis
- better theory-of-mind-like modeling in the roundtable

## Risk Control

Do not overbuild symbolic machinery that cannot be shown in the saved traces.

Prefer:

- small real state
- clean logs
- interpretable updates

Over:

- giant conceptual machinery with no visible trace
