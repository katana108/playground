# Sage Full 10-Stage Architecture

This file restates the larger motivational architecture that inspired Sage.

The source for this file is the motivational architecture paper, adapted into a build-oriented summary rather than copied mechanically.

## Core State

The paper's implementation sketch centers on an explicit state of roughly this form:

- `G`
  goal state, including higher-order pressures such as individuation and transcendence
- `N`
  current conversational need levels
- `M`
  latent modulator state
- `W`
  world model
- `S`
  self model
- `U`
  user model

Two paper-level overgoals matter throughout the loop:

- `individuation`
  preserving continuity, safety, boundedness
- `transcendence`
  growth, exploration, openness to revision

## Stage Overview

### 1. `Perception`

Input:

- current user turn
- recent conversation
- relevant memory

Function:

- extract what just happened
- identify salient signals
- retrieve relevant memory and context for the current turn

In the paper, memory is not only loaded once at turn start.
The world, self, and user models are queried again later at multiple stages.

### 2. `Need Estimation`

Function:

- estimate dialogue-native homeostatic pressures for the agent

Paper-level need examples:

- competence
- uncertainty reduction
- affiliation
- affinity
- legitimacy
- nurturing
- aesthetic coherence

Output:

- a temporary need vector with current deficits or urgencies
- a ranking of which needs are most active in the present situation

### 3. `Cognitive Modulation`

Function:

- transform needs into an updated modulator profile that shapes how the agent is poised to respond

Canonical latent modulators from the paper:

- valence
- arousal
- dominance
- resolution level
- focus
- exteroception

What they roughly do:

- `valence`
  pleasure-pain axis
- `arousal`
  activation level and processing speed
- `dominance`
  approach-versus-avoidance tendency, strongly tied to anticipated reward and competence
- `resolution level`
  how broad, deep, and careful processing becomes
- `focus`
  stability of currently active goals, close to selection threshold
- `exteroception`
  balance of attention between external dialogue and internal reflection

Important paper distinction:

- needs influence what the agent is trying to regulate
- modulators influence how the agent is poised to think and act

Derived labels such as `teaching mode` or `citation rigor` can later be projected from the latent modulator vector, but they are not primitive paper-level modulators.

### 4. `Pre-Action Feeling / State Readout`

Function:

- create a readable summary of the current internal stance before action

This is useful because it gives the architecture an interpretable pre-response state rather than only a hidden vector.

In the paper, feelings are readouts of the current need-plus-modulator posture.
They are not yet the post-action evaluation of success or failure.

### 5. `Appraisal`

Function:

- interpret the situation through the modulated stance and past experience

Paper-oriented output:

- `situation_tags`
- `salience_weights`
- `attribution`

So Stage 5 produces a tuple like:

```text
⟨situation_tags, salience_weights, attribution⟩
```

In practice this means:

- the same user input may be interpreted differently depending on current internal state and history of conversation
- the appraisal result becomes a structured input to candidate generation rather than disappearing into a hidden blob

### 6. `Candidate Generation`

Function:

- produce possible next actions, not only one response

The paper emphasizes abstract conversational actions rather than token-level choices.

Sage Lumina examples from the paper:

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

`StaySilent` matters because in a contemplative architecture, silence can be a deliberate selected action rather than a failure to respond.

### 7. `Scoring And Selection`

Function:

- weigh the candidates
- blend a fast urgency-dominant path with a slower multi-goal deliberative path

Paper sketch:

```text
lambda_t = sigmoid(alpha * urgency + beta * arousal - gamma * resolution_need)

For each candidate action a:
  fast_score(a) = how well a fits the dominant need and current feeling
  slow_score(a) = how well a advances weighted goals while respecting constraints
  blended_score(a) = lambda_t * fast_score(a) + (1 - lambda_t) * slow_score(a)

Choose the action with the highest blended score.
```

Interpretation:

- when urgency and arousal are high, the fast path matters more
- when careful processing is needed, the slow path matters more
- the chosen action should satisfy the most important goals and needs cumulatively, not just locally


### 8. `Action Execution`

Function:

- generate the actual response or selected act

### 9. `Post-Action Evaluation And Learning`

Function:

- evaluate what changed because of the action
- update memory and self-understanding

The paper treats this as structural learning, not just a scalar reward.

Useful trace items from the paper:

- situation tags
- chosen action
- need delta
- attribution
- modulator context
- confidence changes in relevant beliefs or models

This is also where post-action emotion is assigned.
The paper separates:

- pre-action feelings
- post-action emotions

### 10. `Governor / Integration`

Function:

- keep the whole system from changing too abruptly or incoherently

This is where the updated state is blended back into the continuing state.
The paper ties this to individuation and transcendence rather than to ad hoc smoothing alone.

## Why The Full Version Matters

The point of the full 10-stage version is not complexity for its own sake.
The point is clear separation of functions:

- perception
- modeling
- modulation
- appraisal
- action
- revision

That separation is useful scientifically because it makes the architecture more inspectable.

## What Would Need To Exist In Code

- a stable state schema
- a need estimation layer
- modulator calculations
- a readable pre-action feeling or state readout
- an appraisal tuple
- typed conversational actions
- an action-selection scheme
- post-turn revision and memory logging

The paper also explicitly recommends that `W`, `S`, and `U` be queried at multiple later stages, not only at turn start.

## What Can Be Deferred

For the first experiment, the following can be simplified heavily:

- rich schema retrieval
- complicated symbolic reasoning inside candidate generation
- mathematically elegant governor dynamics
- mood-like long-timescale dynamics

The study only needs enough structure to generate legible traces.

## Open Questions The Paper Leaves Open

The paper is explicit that several pieces remain open:

- the latent-versus-derived modulator distinction needs empirical tuning
- the tag taxonomy for appraisal is still early
- multi-party attribution is underspecified
- the full scoring rule is not yet fully formalized end to end

That is useful for this repo because it means Sage should be built as a disciplined prototype, not as fake completeness.
