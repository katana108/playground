# Sage Full 10-Stage Architecture

This file summarizes the larger motivational architecture intended for Sage.

The full version is the future target, not the minimum first build.

## 10 Stages

1. `Perception`
   Read the current user input, conversation context, and relevant memory.

2. `Need Estimation`
   Estimate dialogue-native needs and tensions, such as clarity, nurturing, legitimacy, uncertainty reduction, or affiliation.

3. `Cognitive Modulation`
   Aggregate needs into modulators that shape how the agent is poised to think and respond.

4. `Pre-Action Feeling / State Readout`
   Produce an interpretable readout of the current stance before choosing an action.

5. `Appraisal`
   Interpret the situation through the current stance.

6. `Candidate Generation`
   Produce possible actions or response strategies.

7. `Scoring And Selection`
   Choose among candidates using both urgency-sensitive and more deliberative logic.

8. `Action Execution`
   Produce the response or other selected act.

9. `Post-Action Evaluation And Learning`
   Evaluate the outcome and update memory, action affinities, and self-understanding.

10. `Governor / Integration`
    Maintain overall stability, smooth change, and bounded motivational dynamics.

## Why The Full Version Matters

It makes clear that Sage is not meant to be merely a prompt persona.
It is meant to be an explicit motivational system.

## What Would Need To Be Fully Built

- explicit state schema
- need estimation logic
- modulator aggregation
- appraisal representation
- candidate action representation
- selection logic
- learning and revision logic
- memory integration
- reflective logging

## Demo Reality Check

The first experiment does not need the whole cathedral.
It needs a credible structural skeleton.
