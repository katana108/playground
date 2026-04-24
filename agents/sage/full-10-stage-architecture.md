# Sage Full 10-Stage Architecture

This file restates the larger motivational architecture that inspired Sage.

It is the long-form target, not the minimum first build.

## Stage Overview

### 1. `Perception`

Input:

- current user turn
- recent conversation
- relevant memory

Function:

- extract what just happened
- identify salient signals

### 2. `Need Estimation`

Function:

- estimate dialogue-native pressures such as clarity, nurturing, legitimacy, affiliation, or uncertainty reduction

Output:

- a temporary need state

### 3. `Cognitive Modulation`

Function:

- transform needs into a modulator profile that shapes how the agent is poised to respond

Possible modulators:

- clarity
- caution
- curiosity
- nurturing
- legitimacy

### 4. `Pre-Action Feeling / State Readout`

Function:

- create a readable summary of the current internal stance before action

This is useful because it gives the architecture an interpretable pre-response state rather than only a hidden vector.

### 5. `Appraisal`

Function:

- interpret the situation through the modulated stance

In practice:

- the same user input may be interpreted differently depending on current internal state

### 6. `Candidate Generation`

Function:

- produce possible next actions, not only one response

Examples:

- clarify
- soothe
- challenge
- reframe
- synthesize
- remain cautious

### 7. `Scoring And Selection`

Function:

- weigh the candidates
- decide whether urgency, caution, or broader deliberation should dominate

### 8. `Action Execution`

Function:

- generate the actual response or selected act

### 9. `Post-Action Evaluation And Learning`

Function:

- evaluate what changed because of the action
- update memory and self-understanding

### 10. `Governor / Integration`

Function:

- keep the whole system from changing too abruptly or incoherently

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
- a readable state readout
- an action-selection scheme
- post-turn revision and memory logging

## What Can Be Deferred

For the first experiment, the following can be simplified heavily:

- rich candidate generation
- complicated selection calculus
- mathematically elegant governor dynamics

The study only needs enough structure to generate legible traces.
