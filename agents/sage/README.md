# Sage

Sage is the minimal neurosymbolic condition in the study.

## Why Sage Matters

Sage is where the study can most directly ask:

- what happens when self-model, user-model, and world-model are explicit objects?
- what happens when needs and modulators are visible rather than hidden inside prompt style?
- what happens when revision is logged directly rather than inferred from dialogue?
- can a motivational framework make the agent more interpretable, more corrigible, and therefore easier to align?

Here `revision` means an explicit saved change in one of Sage's internal structures.
Examples:

- a self-model update
- a user-model update
- a world-model update
- a need estimate changing after new evidence
- a modulator shift
- a memory or action-preference update tied to a specific interaction

## Three Documents In This Folder

`full-10-stage-architecture.md`

- the larger motivational target
- useful for the long-term design

`prototype-5-stage.md`

- the smaller version to build first
- keeps the essential cycle but removes extra machinery

`build-plan.md`

- implementation order
- risk control
- what can be omitted without breaking the experiment

## Strategic Rule

Sage should be the smallest architecture in the set that still has explicit inner objects and explicit revision.
