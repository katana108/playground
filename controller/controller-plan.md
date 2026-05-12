# Controller Plan

## Core Idea

Build:

- 4 separate agent runtimes
- 1 shared experiment harness

The harness is not an agent.
It runs the study around the agents.

## What Exists

Each agent stays separate:

- Sofico: own orchestrator and state
- Sage: own modulator-based loop
- Socrates: own prompt + notebook setup
- Smith: own baseline setup

## What The Harness Does

1. choose which agent is active
2. load that agent's state / notebook
3. send your message to that agent
4. save the reply
5. save updated notes / logs
6. later run agent-to-agent conversations

## Two Phases

### Phase 1: individual conversations

You talk separately to:

- Sofico
- Sage
- Socrates
- Smith

This phase lasts about 5 to 7 days.

### Phase 2: group conversations

Conversation A:

- what is the user like
- what does the user need
- how can each agent help

Conversation B:

- can AI have consciousness
- what counts as evidence
- did the week change their view

## Group Conversation Structure

Keep it simple:

1. private prep
2. public round 1
3. public round 2

Private prep is hidden.
Only rounds 1 and 2 are public.

## Agent Adapter

Each agent should expose one simple interface to the harness.

Example:

```text
run_turn(
  user_message,
  corpus,
  transcript,
  private_notebook,
  state
)
```

The interface is shared.
The internal architecture is not.

## What To Build

### 1. Agent adapters

One wrapper per agent so the harness can talk to it.
Version 1 can use manual adapters before the real runtimes are ready.

### 2. Individual conversation runner

Lets you choose an agent and talk to it.
Saves:

- transcript
- notebook
- state
- session summary

### 3. Group conversation runner

Loads saved weekly history and runs:

- user roundtable
- consciousness roundtable

### 4. Logging layer

Common saved outputs across all agents.

## Minimal File Shape

```text
controller/
  README.md
  controller-plan.md

conversations/
  sofico/
  sage/
  socrates/
  smith/
  roundtables/

agents/
  sofico/
  sage/
  socrates/
  smith/
```

## MVP

The harness is good enough when it can:

- run one separate conversation with each agent
- save each agent's own notes and state
- keep weekly history separate per agent
- run the 2 group conversations afterward

## Recommended Build Order

1. define agent adapter interface
2. build individual conversation runner
3. define saved file format
4. build roundtable runner
5. clean logs for analysis
