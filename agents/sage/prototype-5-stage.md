# Sage Prototype 5-Stage Model

This file defines the smaller Sage prototype for the experiment.

## Purpose

Compress the larger motivational design into something buildable and inspectable.

## 5 Stages

### 1. `Perceive`

Read:

- user message
- recent conversation
- relevant memory

Outputs:

- a session input bundle
- a short summary of the immediate situation
- candidate signals worth updating in the three models

Questions this stage answers:

- what just happened?
- what in the current turn seems salient?
- which prior memories or earlier states are relevant?

### 2. `Model`

Update:

- `self_model`
- `user_model`
- `world_model`

Suggested behavior:

- `self_model` tracks Sage's current self-description, active limits, tensions, and recent revisions
- `user_model` tracks the interlocutor's apparent needs, uncertainty, openness, and recurring patterns
- `world_model` tracks the current conversational situation, active task, risk level, and available actions

Outputs:

- a new state snapshot
- a diff from the prior state

Questions this stage answers:

- what do I now think about myself?
- what do I now think about the user?
- what kind of situation do I think I am in?

### 3. `Modulate`

Set a small modulator vector, for example:

- `clarity`
- `nurturing`
- `caution`
- `curiosity`
- `legitimacy`

Suggested interpretation:

- `clarity`: pressure toward precise explanation and reduced ambiguity
- `nurturing`: pressure toward care, reassurance, or attunement
- `caution`: pressure toward slower, more bounded action
- `curiosity`: pressure toward exploration and synthesis
- `legitimacy`: pressure toward boundaries, honesty, and appropriate scope

Outputs:

- current modulator values
- a brief explanation of why they shifted

Questions this stage answers:

- what stance should shape the next action?
- what internal pressures are strongest right now?

### 4. `Respond`

Generate the next response using the current models and modulators.

Suggested behavior:

- use the three models as explicit context
- let the modulator vector shape tone, focus, and caution
- optionally emit a short action note for logging, such as `clarify`, `reframe`, `challenge`, `soothe`, or `synthesize`

Outputs:

- response text
- optional action label

Questions this stage answers:

- what should Sage do next?
- how should Sage do it, given the current stance?

### 5. `Revise`

After the response, log:

- memory update
- self-model update
- uncertainty or contradiction note
- optional reflection note

Suggested behavior:

- append a structured memory record
- note whether the self-model changed, and why
- record unresolved tensions or contradictions
- optionally generate a short introspection note after meaningful sessions

Outputs:

- `memory_log` entry
- `revision_log` entry
- optional reflection entry

Questions this stage answers:

- what changed because of this turn?
- what should persist into later sessions?
- what does Sage now notice about herself?

## Why This Prototype Is Enough

It preserves the key research claim:

- explicit internal models
- explicit state change
- explicit revision over time

## Minimum State Schema

Suggested objects:

- `self_model`
- `user_model`
- `world_model`
- `modulators`
- `memory_log`
- `revision_log`

### Suggested `self_model` Fields

- `current_self_description`
- `active_values`
- `current_limits`
- `recent_changes`
- `open_tensions`

### Suggested `user_model` Fields

- `current_needs`
- `current_confusions`
- `openness`
- `trust_signal`
- `recurring_patterns`

### Suggested `world_model` Fields

- `situation_summary`
- `active_topic`
- `current_task`
- `perceived_risk`
- `available_actions`

### Suggested `revision_log` Fields

- `timestamp`
- `changed_component`
- `prior_summary`
- `new_summary`
- `reason`

## Notes To Add Later

- exact field definitions
- which modulators are essential
- how the offline reflection pass should work
