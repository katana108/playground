# Sofico

Sofico is the educational tutor condition in this study.

This folder is intentionally grounded in the real Sofico project rather than written as pure speculation. The goal is to keep one foot in actual source material and one foot in the experiment.

## Why Sofico Matters

Sofico is the strongest current example of an agent in this set that already has:

- a stable teacher bootstrap
- an explicit learner model
- a reflection mechanism
- a documented self-model layer
- a documented dreaming layer

That does not mean all of these are already wired together in runtime. It means the ingredients exist in a more concrete way than they do for the other conditions.

## Copied Source Docs In This Repo

To avoid relying on external paths, copied source docs now live directly in this repo under `agents/sofico/copied-source/`.

Included copies:

- `SOUL.md`
- `IDENTITY.md`
- `TEACHING.md`
- `SELF_MODEL.md`
- `DREAMING.md`
- `STUDENT_MODEL.md`

## Real Sofico Source Material Behind These Notes

Teacher bootstrap:

- `/Users/amikeda/Smithy/sofi/src/orchestrator/bootstrap/SOUL.md`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/bootstrap/IDENTITY.md`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/bootstrap/TEACHING.md`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/bootstrap/teacher_model.yaml`

Learner modeling and reflection:

- `/Users/amikeda/Smithy/sofi/src/orchestrator/student_model.py`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/student_profile/STUDENT_MODEL.md`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/student_profile/student_model.yaml`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/reflection_engine.py`

Self and dreaming:

- `/Users/amikeda/Smithy/sofi/src/orchestrator/self_model/SELF_MODEL.md`
- `/Users/amikeda/Smithy/sofi/src/orchestrator/self_model/DREAMING.md`

Planning and state:

- `/Users/amikeda/Smithy/sofi/planning/working-context.md`
- `/Users/amikeda/Smithy/sofi/planning/sofi-v2-implementation-phases.md`
- `/Users/amikeda/Smithy/sofi/planning/sofi-v2-milestones.md`

## What The Files In This Folder Do

`bootstrap-and-soul.md`

- copied and organized material from the bootstrap identity files
- shows what Sofico already claims about herself as a teacher

`self-reflection.md`

- copied and organized material from the self-model and reflection files
- shows what is already explicit and what is still missing

`dreaming-and-offline-synthesis.md`

- copied and organized material from the dreaming document
- turns it into an experiment-facing plan

`current-vs-future.md`

- keeps the line clear between what is already real and what is still planned

## What To Be Careful About

Sofico can easily become the most impressive agent in the set simply because she already has more engineering behind her. That is useful, but it is also a scientific hazard.

The discipline here is:

- use the real source material
- mark documented features separately from runtime features
- do not count design intent as observed evidence
