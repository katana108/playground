# Sage Build Draft

## Purpose

This document is a shareable draft for discussing how Sage could be built as a real experimental agent.

It is meant for:

- internal planning
- discussion with engineer collaborators
- later revision as the architecture becomes more concrete

This is not the final implementation spec.
It is the clearest practical bridge between the paper, the experiment, and a buildable first version.

## Short Thesis

Sage should be a minimal neurosymbolic conversational agent whose internal state is more explicit than a normal prompt-driven chatbot.


The main point is to build the smallest architecture that can leave meaningful footprints.

Those footprints should include:

- explicit self-model changes
- explicit user-model changes
- explicit need and modulator changes
- explicit memory and revision traces
- later changes in behavior that can be connected back to saved state

## Why Sage Exists In The Study

Sage is the condition where the study most directly asks:

- what changes when self, user, and world are explicit objects?
- what changes when motivation is modeled explicitly rather than hidden in style?
- what changes when emotional context affects internal state before response generation?

Sage is not meant to be the smoothest or most socially impressive agent.
It is meant to be the most inspectable.

## Core Design Claim

The build should preserve four distinctions:

- what Sage thinks about herself
- what Sage thinks about the user
- what Sage thinks about the current situation
- what motivational state is shaping the current response

But in this experiment, the real center of gravity is not abstract model updating by itself.
The real center of gravity is:

- how user emotion and situation activate needs
- how needs shift modulators
- how modulator change alters candidate responses
- how outcomes later reshape future behavior

If these collapse back into one prompt blob, the architecture loses its scientific value.

## Minimal Viable Sage

### State Objects

Minimum explicit objects:

- `self_model`
- `user_model`
- `world_model`
- `needs`
- `modulators`
- `memory_log`
- `revision_log`

### Overgoals

From the paper, Sage should also have two high-level balancing pressures:

- `individuation`
  continuity, safety, boundedness
- `transcendence`
  openness, growth, revision, exploration

These do not need a heavy mathematical implementation in version 1.
But they should be present conceptually.

### Need Vector

First-pass needs from the paper:

- competence
- uncertainty reduction
- affiliation
- affinity
- legitimacy
- nurturing
- aesthetic coherence

These do not need to be perfect.
They just need to be explicit and revisable.

### Latent Modulators

Use the paper's six latent modulators:

- valence
- arousal
- dominance
- resolution level
- focus
- exteroception

These are better than invented English labels because they are closer to the architecture in the paper.

Derived labels such as `gentle guidance mode` can later be projected from them if useful.

## Proposed Turn Loop

The buildable first loop should compress the larger 10-stage architecture into 5 stages:

1. `Perceive`
2. `Model and Estimate Needs`
3. `Modulate and Appraise`
4. `Respond`
5. `Revise`

### 1. Perceive

Inputs:

- current user message
- recent conversation
- recent saved traces

Outputs:

- salient features of the turn
- candidate updates to self, user, and world
- candidate user-emotion signals
- candidate need pressures
- candidate questions about which modulators may need to move

### 2. Model and Estimate Needs

Update:

- `self_model`
- `user_model`
- `world_model`
- `needs`

This stage is partly where the LLM does its interpretive work, but not as a free-floating chatbot.
The LLM is being used to make judgments inside an explicit loop.

This is where Sage answers:

- what do I now think about myself?
- what do I now think about the user?
- what kind of situation am I in?
- which needs are active right now?
- which goals are under the most pressure?
- which modulators are likely too low, too high, or otherwise misaligned for this situation?

### 3. Modulate and Appraise

Convert the current need vector into the latent modulator state.

All six modulators should be reassessed every turn.

Important outputs:

- current modulator vector
- modulator delta from the previous turn
- short reason for the delta
- short note on what modulator movement would better fulfill the active needs

Also produce a simple appraisal tuple:

```text
<situation_tags, salience_weights, attribution>
```

This stage matters because it is where emotion-like and motivation-like state becomes structurally relevant rather than just narrated.

### 4. Respond

Generate and select a response from a constrained action set.

The action set should remain typed and small.

Good initial actions:

- Mirror
- Clarify
- Empathize
- Reframe
- ChallengeBelief
- SuggestPractice
- SurfaceResource
- RetrievePattern
- SetBoundary
- StaySilent

This list comes from the Sage Lumina action set in the paper.
Treat it as a strong v1 schema, not as a final exhaustive ontology.

For version 1, Sage should ideally generate at least 3 candidate action-response versions and then choose the best one.

The chosen action should be logged, not just the final text.

### 5. Revise

After response generation, save:

- memory update
- revision note
- changed self, user, or world entries
- changed need or modulator entries
- post-user-reply need changes
- post-user-reply modulator changes
- action evaluation note
- optional short introspection note

This is where later developmental claims become possible.
It is also where self-improvement begins, because Sage should keep track of whether the selected action actually helped in that situation.



## Suggested Build Strategy

### Phase 1: Fake the structure honestly

Do not wait for a full symbolic stack.

Start with:

- YAML or JSON-like state objects
- prompt-based estimation of needs and modulators
- markdown or JSON logs
- constrained action vocabulary

This is like building the skeleton before worrying about skin and jewelry.

### Phase 2: Stabilize the trace

Before adding complexity, make sure:

- state is saved consistently
- revisions are legible
- actions are named consistently
- emotional cues produce detectable differences

### Phase 3: Add stronger symbolic hooks

Only after the trace is useful should deeper symbolic mechanisms be added.

Possible later additions:

- explicit action-context affinity memory
- stronger candidate selection logic
- multi-session self-observation
- later offline synthesis

## Hyperon And OmegaClaw Alignment

### Hyperon

Publicly grounded points from the OpenCog Hyperon wiki:

- Hyperon is still pre-alpha and experimental
- MeTTa is the successor language direction for Atomese
- AtomSpace remains the core graph-based knowledge representation layer
- the project is still heavily focused on foundational representation and language questions

What this means for Sage:

- Hyperon is relevant as a future symbolic substrate
- it is not a realistic dependency for version 1 of the experiment unless an existing internal stack already works

### OmegaClaw

The paper describes OmegaClaw as the agent substrate around:

- agent loop
- skill modules
- tool access
- persistent symbolic memory
- typed action execution

Important caution:

- the public `OpenClaw` docs currently on the web appear to describe a different project
- so Sage planning should not assume that public OpenClaw docs are automatically valid for OmegaClaw
- if a private or internal OmegaClaw wiki exists, that should become the source of truth once shared

### Practical Recommendation

For now:

- treat Hyperon as future symbolic alignment
- treat OmegaClaw as paper-grounded, wiki-pending infrastructure
- do not block the experiment on either one

Instead, design Sage so that her explicit state and action traces could later map onto:

- Hyperon / AtomSpace style storage
- MeTTa-friendly symbolic forms
- OmegaClaw style skill execution and persistent memory

## Proposed File / Module Shape

A minimal implementation could start with:

- `state_schema.yaml`
- `action_schemas.md`
- `modulator_estimation_prompt.md`
- `revision_prompt.md`
- `sample_trace.md`

Possible runtime modules:

- `sage_state.py`
- `sage_turn_loop.py`
- `sage_estimators.py`
- `sage_logging.py`

These names are placeholders, not requirements.

## What I Would Ask An Engineer Friend

These are the best feedback questions to get early:

- where should state live between sessions?
- should needs and modulators be estimated in one prompt or separate passes?
- should action selection be explicit and typed, or only logged after the fact?
- what is the smallest logging format that still gives meaningful traces?
- how much determinism do we want versus free-form generation?
- can we make emotional cues change behavior without making Sage melodramatic?
- where should symbolic compatibility hooks be placed so Hyperon or OmegaClaw can be added later?

## Open Questions

- should Sage version 1 include only online turn-by-turn revision, or also a small reflection pass?
- should derived labels like `gentle mode` appear in the interface, or only the six latent modulators?
- how much of the world model should include explicit statements like "I am a software agent acting through dialogue and tools"?
- should the user ever see the full Sage state, or only structured excerpts?
- how soon should research or retrieval be added as a selectable action?

## Bottom Line

The first good Sage is not the most complicated Sage.

The first good Sage is:

- explicit enough to inspect
- small enough to build
- emotional enough to differ from a generic LLM
- constrained enough that later behavior can be tied back to saved state

That is the version worth building first.
