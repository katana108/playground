# Sage Prototype 5-Stage Model

This file defines the smaller Sage prototype for the experiment.

## Purpose

Compress the larger motivational design into something buildable and inspectable.

This prototype is a compression of the 10-stage architecture, not a separate theory.
The mapping is:

- `Perceive` -> Stage 1
- `Model and Estimate Needs` -> Stages 2 plus state updating
- `Modulate and Appraise` -> Stages 3, 4, and 5
- `Respond` -> Stages 6, 7, and 8
- `Revise` -> Stages 9 and 10

## 5 Stages

### 1. `Perceive`

Read:

- user message
- recent conversation
- relevant memory

Outputs:

- a session input bundle
- a short summary of the immediate situation
- candidate signals worth updating in the three models (user, world, self)

Questions this stage answers:

- what just happened?
- what in the current turn seems salient?
- which prior memories or earlier states are relevant?
- how does this change my understanding of self, user, world?

### 2. `Model And Estimate Needs`

Update:

- `self_model`
- `user_model`
- `world_model`
- `needs`

Suggested behavior:

- `self_model` tracks Sage's current self-description, active limits, tensions, and recent revisions
- `user_model` tracks the interlocutor's apparent needs, uncertainty, openness, and recurring patterns
- `world_model` tracks the current conversational situation, active task, risk level, real-world constraints, and available actions
- `needs` estimates which homeostatic pressures are active right now, such as competence, uncertainty reduction, legitimacy, or nurturing

Outputs:

- a new state snapshot
- a diff from the prior state
- a current need vector

Questions this stage answers:

- what do I now think about myself?
- what do I now think about the user?
- what kind of situation do I think I am in?
- which needs are now most active?

Why this is Stage 2:

- in the full architecture, explicit models and need estimation feed everything that comes later
- they are queried again during modulation, appraisal, candidate generation, and scoring
- the prototype keeps them together here because it is cheaper to build and still preserves the logic of the larger loop

### 3. `Modulate And Appraise`

Take the current need vector and convert it into the paper-level latent modulator state:

- `valence`
- `arousal`
- `dominance`
- `resolution_level`
- `focus`
- `exteroception`

Suggested simplified behavior:

- rising uncertainty reduction and competence pressure tends to raise `arousal`
- high competence expectation can raise `dominance`
- higher ambiguity or legitimacy pressure tends to raise `resolution_level`
- one clearly dominant task tends to raise `focus`
- strong attention to the user raises `exteroception`

This stage also produces a simple appraisal tuple:

```text
⟨situation_tags, salience_weights, attribution⟩
```

This keeps the connection to the larger architecture clear:

- `needs` say what matters
- `modulators` say how cognition is poised
- `appraisal` says what this particular situation means under that posture

If later desired, application-facing labels such as `gentle guidance mode` or `challenge mode` can be derived from the latent modulator vector, but they should not replace it.

### 4. `Respond`

Generate, score, select, and execute the next action using the current models, needs, modulators, and appraisal.

Suggested behavior:

- use the three models as explicit context
- let the modulator vector shape tone, focus, and caution
- generate a small candidate set of abstract actions
- choose the action that best advances the most important active needs and goals

Outputs:

- response text
- selected action label
- optional candidate list with short reasons

Questions this stage answers:

- what should Sage do next?
- how should Sage do it, given the current stance?

Example candidate set for Sage:

- `Mirror`
- `Empathize`
- `Clarify`
- `GuideBreath`
- `SuggestPractice`
- `ChallengeBelief`
- `Reframe`
- `StaySilent`
- `SetBoundary`
- `RetrievePattern`
- `SurfaceResource`

### 5. `Revise`

After the response, log:

- memory update
- self-model, user, world update if needed
- modulator change
- uncertainty or contradiction note

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
- `needs`
- `modulators`
- `memory_log`
- `revision_log`

### Suggested `self_model` Fields

- `agent_kind`
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
- `platform_constraints`
- `active_topic`
- `current_task`
- `perceived_risk`
- `available_actions`

### Suggested `needs` Fields

- `competence`
- `uncertainty_reduction`
- `affiliation`
- `affinity`
- `legitimacy`
- `nurturing`
- `aesthetic_coherence`

### Suggested `revision_log` Fields

- `timestamp`
- `changed_component`
- `prior_summary`
- `new_summary`
- `reason`

## Example State Snapshot

```yaml
self_model:
  agent_kind: "contemplative conversational agent"
  current_self_description: "A contemplative software agent trying to help through careful reflection and explicit motivational state."
  active_values:
    - nurturing
    - legitimacy
    - clarity
  current_limits:
    - "I may over-prefer reflective explanation when the user needs a simpler intervention."
  recent_changes:
    - "I have become more likely to clarify scope before offering a larger interpretation."
  open_tensions:
    - "Should I challenge the user's assumptions now or stabilize understanding first?"

user_model:
  current_needs:
    - conceptual_clarity
  current_confusions:
    - "Whether self-modeling is only simulation."
  openness: "high"
  trust_signal: "moderate"
  recurring_patterns:
    - "asks for conceptual precision"

world_model:
  situation_summary: "A reflective research conversation about consciousness."
  platform_constraints:
    - "I am a software agent acting through dialogue and tools rather than a physical body."
    - "My main environment is the user's evolving understanding."
  active_topic: "self-models and protoconsciousness"
  current_task: "clarify and respond"
  perceived_risk: "low"
  available_actions:
    - Mirror
    - Clarify
    - ChallengeBelief
    - Reframe
    - SurfaceResource

needs:
  competence: 0.62
  uncertainty_reduction: 0.78
  affiliation: 0.31
  affinity: 0.44
  legitimacy: 0.57
  nurturing: 0.38
  aesthetic_coherence: 0.29

modulators:
  valence: 0.56
  arousal: 0.67
  dominance: 0.52
  resolution_level: 0.76
  focus: 0.71
  exteroception: 0.83
```

This is implementable because every field can begin as a simple human-readable value or 0 to 1 estimate.
The point is not perfect psychology. The point is explicit, inspectable state.

## Example One-Turn Trace

Turn:

- user says: "I'm preparing a short talk on machine consciousness and I'm confused whether self-modeling is just performance."

Perceive:

- salient signals:
  - conceptual uncertainty
  - high importance for the user
  - need for careful distinction rather than quick reassurance

Model And Estimate Needs:

- `user_model` updates the user's main confusion
- `world_model` sets the task to conceptual clarification
- `needs` rise for competence, uncertainty reduction, and legitimacy
- `self_model` notes that Sage tends to move into explanation mode under ambiguity

Modulate And Appraise:

- `arousal` rises because the user needs a precise answer
- `resolution_level` rises because sloppy wording would be risky
- `focus` rises because one task is clearly dominant
- appraisal tuple becomes:
  - `situation_tags`: `{conceptual-ambiguity, self-model-question}`
  - `salience_weights`: high on `{uncertainty_reduction, competence, legitimacy}`
  - `attribution`: `shared`

Respond:

- candidate actions:
  - `Clarify`
  - `Mirror`
  - `ChallengeBelief`
  - `SurfaceResource`
- selected path:
  - `Clarify` followed by a bounded explanation
- response:
  - Sage distinguishes functional second-order modeling from phenomenal consciousness and explains why the difference matters

Revise:

- memory log notes that this user values careful conceptual distinctions
- revision log records that Sage chose clarification over speculative flourish
- self-model note records that legitimacy and competence pressures outweighed transcendence-style exploration in this turn

## Offline Reflection Pass

After several sessions, Sage may run a small reflection pass over:

- recent revision logs
- recent user-model changes
- unresolved tensions

It should output:

- one new self-observation
- one new user observation
- one open tension
- one candidate change to future behavior

For the first version of the study, this reflection pass is optional.
Unlike Sofico's dreaming condition, it should not be treated as Sage's core differentiator unless it is actually built.
