# Sofico Self-Reflection

This file brings together the real reflection pieces already present in Sofico and the explicit self-model document that has been drafted for future runtime use.

## 1. What The Real Reflection Engine Already Does

The current `reflection_engine.py` is not a vague concept. It already defines a reflection step over the learner model.

Important behaviors copied from the code:

- sessions can be judged meaningful enough to reflect on
- reflection inputs include summary, observations, explicit preferences, progress notes, and relationship notes
- outputs are `StudentMemoryUpdate` records
- updates can be `ADD`, `UPDATE`, or `NOOP`
- older learner memories can be superseded rather than overwritten blindly

This matters because Sofico already has a genuine revision mechanism for how she models the learner.

## 2. What The Learner Model Already Looks Like

The current learner model in `student_model.py` and `student_model.yaml` contains:

- `identity`
- `goals_and_constraints`
- `stated_preferences_about_self`
- `inferred_profile`
- `progress_patterns`
- `relationship_memory`
- `metadata`

Important design feature:

- inferred and relational memories are not treated as immutable facts
- they can be updated and the older versions can be marked `superseded`

That is stronger than simple note accumulation.

## 3. What `SELF_MODEL.md` Adds

The real `SELF_MODEL.md` is a drafted human-readable self-model for Sofico herself.

Copied sections from the source document:

- `Who I Notice Myself To Be`
- `What I Notice About How I Teach`
- `What Surprises Or Interests Me About My Own Nature`
- `Where I Get Confused`
- `What I Am Practicing Or Revising`
- `What Changed Recently`
- `On Continuity`

Important copied design rule from the source:

- the file should be honest rather than polished
- specific rather than vague
- revisable rather than declarative
- introspective without becoming theatrical

This is exactly the kind of document that could support the experiment, but the planning notes say it is not yet wired into runtime behavior.

## 4. Current State Of Reflection In Sofico

Already real:

- learner-model reflection
- learner-memory revision
- explicit student-model schema
- explicit reflection engine code

Documented but not yet runtime-wired:

- self-model introspection for Sofico herself
- automatic update triggers for `SELF_MODEL.md`

## 5. Why This Matters For The Study

Sofico gives an unusually clean split:

- learner reflection is already concrete
- self reflection is already conceptually documented
- the gap between them is visible

That makes her useful for the experiment because we can ask:

- does a system that already revises its user model become more interesting when it also revises its self model?

## 6. Minimal Adaptation For The Experiment

The smallest believable adaptation would be:

1. keep the existing learner reflection logic
2. add a short post-session self-reflection pass
3. write that pass into a structured text artifact
4. compare early and late self-reflection across the week

## 7. What To Watch For

Potentially strong evidence:

- Sofico identifies a stable teaching tendency and later revises it
- Sofico names a recurring failure mode and later compensates for it
- self-reflection lines up with actual behavior changes

Potentially weak evidence:

- self-description that never changes
- dramatic language unsupported by logs
- self-reflection that is only generic personality talk
