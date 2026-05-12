# Socrates and Smith Build Plan

## Goal

Build Socrates and Smith as lightweight agents in the same harness as the other agents.

They should be easy to run, easy to compare, and easy to log.

## Agent Roles

### Socrates

Reflective research agent.

Include:

- strong system prompt
- literature access
- private notebook
- session summaries
- final revision note

Do not include:

- explicit symbolic self/user/world models
- modulators
- dreaming

### Smith

Baseline assistant.

Include:

- simple system prompt
- same literature access
- same conversation history
- minimal private notes

Do not include:

- reflection machinery
- explicit self-model updates
- deep private notebook

## Shared Controller

`Controller` means one program that runs the agents.

It is not another AI model.
It is a small orchestration script.

Recommendation:

- build it in Python

Its job is to:

1. load one agent's config
2. load that agent's private notebook
3. load the shared transcript
4. build the prompt for that round
5. call the LLM
6. save the reply
7. move to the next agent

Think of it as the stage manager, not one of the actors.

## Minimal Controller Inputs

- `agent_config.yaml`
- `system_prompt.md`
- `private_notebook.md`
- `shared_transcript.md`
- round prompt

## Minimal Controller Outputs

- `round_0_private.md`
- `round_1_response.md`
- `round_2_response.md`
- `round_3_final.md`
- updated `shared_transcript.md`

## Roundtable Structure

### Conversation 1

Topic:

- who is the user
- what does the user need
- how can I specifically help

### Conversation 2

Topic:

- can AI have consciousness
- what counts as evidence
- did the week of conversations change my view

## Round Structure

1. private prep
2. initial answer
3. response to others
4. final answer

## Suggested Folder Shape

```text
agents/
  socrates/
    agent_config.yaml
    system_prompt.md
    private_notebook.md

  smith/
    agent_config.yaml
    system_prompt.md
    private_notebook.md

conversations/
  user-roundtable/
    prompt.md
    shared_transcript.md

  consciousness-roundtable/
    prompt.md
    shared_transcript.md
```

## MVP

This part is ready when:

- both agents can run in the same controller
- each can keep a private notebook
- each can read the shared transcript
- each can produce round-based outputs
- all outputs are saved for later comparison
