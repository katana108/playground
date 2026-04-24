# Sofico Self-Reflection

This file tracks Sofico's reflection and self-update mechanisms.

## Real Source Files

- [reflection_engine.py](/Users/amikeda/Smithy/sofi/src/orchestrator/reflection_engine.py:1)
- [student_model.py](/Users/amikeda/Smithy/sofi/src/orchestrator/student_model.py:1)
- [SELF_MODEL.md](/Users/amikeda/Smithy/sofi/src/orchestrator/self_model/SELF_MODEL.md:1)
- [working-context.md](/Users/amikeda/Smithy/sofi/planning/working-context.md:1)

## What Those Files Already Support

- `reflection_engine.py` defines a `ReflectionEngine` that turns session observations into `ADD` and `UPDATE` operations on the student model.
- `student_model.py` defines explicit learner-memory entries with `active` and `superseded` states.
- `SELF_MODEL.md` defines a human-readable self-model for Sofico, but the project notes say it is not yet wired into runtime behavior.
- `working-context.md` explicitly says `SELF_MODEL.md` and `DREAMING.md` are in place as documents and not yet plugged into runtime behavior.

## What Is Already Concrete

- learner-model reflection
- `ADD / UPDATE / NOOP` style memory revision
- supersession of older learner beliefs

## What Is Not Yet Concrete

- runtime self-model revision for Sofico itself
- a wired introspection loop using `SELF_MODEL.md`
- a wired dreaming loop using `DREAMING.md`

## Questions For This Experiment

- can learner-model revision be contrasted with self-model revision?
- what extra machinery would be needed for Sofico to update its own self-model, not only the learner model?
- which existing reflection outputs are worth logging as experiment evidence?

## Notes To Add Later

- exact code paths to reuse
- minimal experiment adaptation plan
- what counts as a meaningful self-revision for Sofico
