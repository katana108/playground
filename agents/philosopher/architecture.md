# Socrates Architecture

Socrates should be treated as a real agent, but with a much lighter architecture than Sage or Sofico.

## Minimal Architecture

Socrates sits in the middle of the comparison:

- more agentic than Smith
- lighter than Sofico
- less structurally explicit than Sage

He can share part of the same general agent loop as the others while omitting the heavier internal modules.

Inputs:

- user message
- recent session memory
- same corpus as the other agents
- strong philosophical system prompt
- online research access

Optional lightweight saved objects:

- `session_summary`
- `research_note`
- `stance_note`

Process:

1. read the current turn
2. retrieve recent conversation, shared corpus context, and if relevant recent research notes
3. interpret the situation through the Socratic role
4. answer by probing assumptions, definitions, and hidden contradictions
5. optionally save a lightweight session summary or stance note

Outputs:

- response text
- optional session-summary note
- optional research note
- optional stance note

## What He Has

- strong stable persona
- access to the corpus
- access to online research
- memory of recent conversation
- explicit design pressure toward contradiction detection
- a real continuing agent loop rather than a one-shot chat prompt

## What He Does Not Have

- explicit symbolic self-model object
- explicit user-model object
- explicit world-model object
- explicit modulators
- a serious offline dreaming layer
- a rich motivational action-selection architecture

## Why This Is A Good Contrast Condition

If Socrates sounds highly reflective despite lighter structure, that is scientifically useful.

It shows the difference between:

- introspective language and saved summaries
- introspective architecture with deeper explicit state

## Failure Mode To Watch

Socrates may produce elegant self-analysis that is not anchored in much more than transcripts and lightweight notes.
That is not useless. It is one of the exact comparison points the study is meant to expose.
