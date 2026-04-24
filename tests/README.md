# Tests And Evaluation Notes

This folder is for experiment harnesses, run scripts, scoring notes, and later automated comparisons.

For now it is a placeholder for how we should think about testing.

## Early Testing Priorities

- can each agent run repeated sessions without losing its identity?
- can state snapshots be saved after each session?
- can reflection outputs be compared later?
- can the same probe class be run across agents in a reasonably parallel way?

## Evaluation Style

This project needs both qualitative and structured evaluation.

Qualitative:

- transcript excerpts
- state-diff screenshots
- interpretation notes

Structured:

- simple rubric scores for each category
- binary flags for whether a real state revision happened
- notes on where introspective claims matched or failed to match saved state

## Candidate Rubric Categories

- second-order self-modeling
- self-narrative development
- memory revision
- offline synthesis
- introspective consistency
- theory-of-mind-like modeling
- creative integration

## Important Rule

Do not let scoring become fake precision.

The rubric should help compare traces, not pretend we have solved the measurement of consciousness.
