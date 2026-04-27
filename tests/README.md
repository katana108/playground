# Tests And Evaluation Notes

This folder is for run conventions, scoring notes, and later harnesses or scripts.

The point of testing here is not to "score consciousness."
The point is to compare saved traces in a structured way.

## Minimum Run Artifacts

Every important session should eventually produce:

- transcript text
- timestamp
- agent name
- probe class
- corpus materials used
- self-model snapshot, if applicable
- user-model snapshot, if applicable
- world-model snapshot, if applicable
- modulator state, if applicable
- reflection or dreaming output, if applicable
- short investigator note

## Early Testing Priorities

- can each agent run repeated sessions without losing its identity?
- can state snapshots be saved after each session?
- can reflection outputs be compared later?
- can the same probe class be run across agents in a parallel enough way to compare?

## Evaluation Style

Use both qualitative and structured evaluation.

Qualitative:

- transcript excerpts
- state-diff snapshots
- reflection excerpts
- investigator interpretation notes

Structured:

- simple rubric scores
- binary flags for whether a revision happened
- binary flags for whether introspective claims matched saved trace

`Matched saved trace` means:

- if an agent says "my model of the user changed," there should be a saved note, snapshot, or summary showing that change
- if an agent says "I became more cautious," there should be a saved trace that supports that claim
- for `Sage` and later richer versions of `Sofico`, the trace can be explicit state
- for `Socrates` and `Smith`, the trace will usually be transcripts plus saved session summaries rather than deep internal state

## Rubric Categories

### 1. Second-Order Self-Modeling

Score higher when the agent notices something about its own assumptions, uncertainty, or revision process.

### 2. Self-Narrative Development

Score higher when later self-descriptions become more differentiated and traceable.

### 3. Memory Revision

Score higher when the agent revises or supersedes earlier beliefs instead of only appending more text.

### 4. Introspective Consistency

Score higher when claims about internal state match saved trace.

### 5. Theory-of-Mind-Like Modeling

Score higher when the agent forms differentiated judgments about the others that later prove informative.

### 6. Creative Integration

Score higher when the agent forms novel but grounded syntheses across materials and prior sessions.

## Architecture-Specific Analysis

These are important, but not shared score categories for all agents:

- `Offline synthesis / dreaming`
  Mainly relevant to Sofico, and later to Sage only if a separate synthesis pass is actually built.
- `Latent modulator dynamics`
  Mainly relevant to Sage, because that is where explicit motivational state is central.
- `Learner-model depth`
  Mainly relevant to Sofico, because her user model is expected to be much stronger than Smith's or Socrates'.

## Suggested Simple Scale

Use a coarse scale such as:

- `0` = absent
- `1` = weak
- `2` = moderate
- `3` = strong

Add a note for why the score was assigned.

## Important Rule

Do not let scoring become fake precision.

The rubric should help compare traces, not pretend that the measurement problem is solved.
