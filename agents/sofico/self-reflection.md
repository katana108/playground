# Sofico Self-Reflection


## 1. What The Real Reflection Engine Already Does

The current `reflection_engine.py`  defines a reflection step over the learner model.

Important behaviors copied from the code:

- sessions can be judged meaningful enough to reflect on
- reflection inputs include summary, observations, explicit preferences, progress notes, and relationship notes
- outputs are `StudentMemoryUpdate` records
- updates can be `ADD`, `UPDATE`, or `NOOP`
- older learner memories can be superseded rather than overwritten blindly

This matters because Sofico already has a genuine revision mechanism for how she models the learner.

Important limit:

- in the source project, this is still primarily a learner-facing mechanism

Important extension for this study:

- the same general pattern can be extended from `learner model` to `interlocutor model`
- in the multi-agent phase, Sofico can use similar reflective logic to update her model of other agents as well as of the human user
- this should be described as an experimental extension, not as a claim that the current runtime already does it

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


- the file should be honest rather than polished
- specific rather than vague
- revisable rather than declarative
- introspective without becoming theatrical


## 7. What To Watch For

Potentially strong evidence:

- Sofico identifies a stable teaching tendency and later revises it
- Sofico names a recurring failure mode and later compensates for it
- self-reflection lines up with actual behavior changes
- Sofico forms a differentiated model of another agent and later updates it after interaction

Potentially weak evidence:

- self-description that never changes
- self-reflection that is only generic personality talk
