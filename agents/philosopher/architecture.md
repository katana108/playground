# Socrates Architecture

Socrates should still be treated as an agent, but with a much lighter architecture than Sage or Sofico.

## Minimal Architecture

Inputs:

- user message
- recent session memory
- same corpus as the other agents
- strong philosophical system prompt

Process:

1. read the current turn
2. interpret it through the Socratic persona
3. answer by probing assumptions and definitions
4. optionally save a lightweight session summary

Outputs:

- response text
- optional session-summary note

## What He Has

- strong stable persona
- access to the corpus
- memory of recent conversation
- explicit design pressure toward contradiction detection

## What He Does Not Have

- explicit symbolic self-model object
- explicit user-model object
- explicit world-model object
- explicit modulators
- serious offline dreaming layer

## Why This Is A Good Contrast Condition

If Socrates sounds highly self-aware despite weak explicit structure, that is scientifically useful.

It shows the difference between:

- introspective language
- introspective architecture

## Failure Mode To Watch

Socrates may produce elegant self-analysis that is not anchored in any inspectable state.
That is not useless. It is one of the exact comparison points the study is meant to expose.
