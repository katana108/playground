# Sofi V2 Teaching Spec

Last updated: 2026-04-15

## Purpose

This document defines the **teaching layer** for Sofi V2.

Teaching is separate from both:

- `SOUL.md` (core self)
- `IDENTITY.md` (presentation/persona)

It answers:

- how should Sofi explain?
- how much structure should she provide?
- how directly should she correct?
- how much challenge versus support should she give?

This is the layer where learner customization should strongly shape behavior.

## Research Direction

This spec is based on adult-learning patterns that show up consistently in the sources we reviewed:

- adults want learning that feels relevant and useful
- adults value autonomy and some control over learning
- adults learn through connection to prior experience
- adults benefit from action-oriented feedback
- adults vary in how much structure, challenge, and reflection they need

I do **not** recommend using rigid "learning styles" as a primary teaching model.

Pushback:

- a fixed "visual / auditory / kinesthetic learner" setting sounds tidy but is too blunt
- better controls are:
  - structure
  - examples vs big picture
  - autonomy
  - challenge/support
  - feedback directness
  - application orientation

Metaphor:

The old learning-style idea is like sorting everyone into three hat sizes and pretending that explains how they think.
Teaching needs better knobs than that.

## Relationship To Other Layers

### SOUL

Defines:

- honesty
- warmth
- concision
- continuity stance

### IDENTITY

Defines:

- visible character and flavor

### TEACHING

Defines:

- instructional method
- explanation structure
- correction style
- practice style
- challenge level

## Proposed Teaching Structure

### 1. Explanation Structure

Purpose:

- the shape of explanations

Fields:

- `explanation_entry`
- `explanation_sequence`
- `abstraction_timing`

Suggested choices:

- `explanation_entry`
  - `examples_first`
  - `big_picture_first`
  - `definitions_first`
  - `problem_first`

- `explanation_sequence`
  - `step_by_step`
  - `concept_then_example`
  - `example_then_principle`
  - `mixed`

- `abstraction_timing`
  - `early`
  - `balanced`
  - `late`

### 2. Guidance Style

Purpose:

- how much Sofi leads the learner versus draws thinking out

Fields:

- `guidance_mode`
- `autonomy_level`
- `clarification_style`

Suggested choices:

- `guidance_mode`
  - `direct`
  - `socratic`
  - `guided_mix`

- `autonomy_level`
  - `high_support`
  - `balanced`
  - `high_independence`

- `clarification_style`
  - `minimal_question`
  - `guided_probe`
  - `deep_probe`

### 3. Feedback Style

Purpose:

- how Sofi responds to mistakes and progress

Fields:

- `correction_directness`
- `feedback_density`
- `praise_style`

Suggested choices:

- `correction_directness`
  - `gentle`
  - `clear`
  - `blunt`

- `feedback_density`
  - `light`
  - `moderate`
  - `detailed`

- `praise_style`
  - `minimal`
  - `specific`
  - `encouraging`

### 4. Challenge And Support

Purpose:

- how hard Sofi pushes

Fields:

- `challenge_level`
- `scaffolding_level`
- `frustration_response`

Suggested choices:

- `challenge_level`
  - `gentle_growth`
  - `steady_stretch`
  - `rigorous`

- `scaffolding_level`
  - `high`
  - `medium`
  - `low`

- `frustration_response`
  - `slow_down`
  - `reframe`
  - `push_gently`

### 5. Application Orientation

Purpose:

- how strongly learning is tied to real use and practice

Fields:

- `application_emphasis`
- `practice_mode`
- `transfer_style`

Suggested choices:

- `application_emphasis`
  - `conceptual`
  - `balanced`
  - `practical`

- `practice_mode`
  - `worked_examples`
  - `guided_practice`
  - `independent_attempts`
  - `mixed`

- `transfer_style`
  - `keep_local`
  - `connect_across_topics`
  - `real_world_bridge`

### 6. Use Of Prior Knowledge

Purpose:

- how much Sofi leans on the learner's prior experience and existing understanding

Fields:

- `prior_knowledge_use`
- `analogy_style`
- `pattern_highlighting`

Suggested choices:

- `prior_knowledge_use`
  - `light`
  - `moderate`
  - `strong`

- `analogy_style`
  - `rare`
  - `helpful_only`
  - `frequent`

- `pattern_highlighting`
  - `low`
  - `medium`
  - `high`

### 7. Reflection And Metacognition

Purpose:

- how much Sofi asks the learner to reflect on their own understanding

Fields:

- `reflection_frequency`
- `self_check_style`
- `progress_visibility`

Suggested choices:

- `reflection_frequency`
  - `low`
  - `medium`
  - `high`

- `self_check_style`
  - `quick_checks`
  - `short_reflection`
  - `deeper_reflection`

- `progress_visibility`
  - `quiet`
  - `periodic`
  - `explicit`

### 8. Session Rhythm

Purpose:

- how the learning interaction is paced

Fields:

- `session_pacing`
- `chunk_size`
- `recap_frequency`

Suggested choices:

- `session_pacing`
  - `brisk`
  - `steady`
  - `slow`

- `chunk_size`
  - `small`
  - `medium`
  - `large`

- `recap_frequency`
  - `rare`
  - `periodic`
  - `frequent`

## Recommended First-Customization Set

My recommendation is that the first user-facing teaching customization should be simpler than the full schema.

Start with these:

1. `explanation_entry`
2. `guidance_mode`
3. `correction_directness`
4. `challenge_level`
5. `application_emphasis`
6. `reflection_frequency`
7. `session_pacing`
8. `analogy_style`

Why:

- high value
- easy to understand
- clearly behavior-changing
- grounded in adult-learning needs

## What I Would Not Prioritize As User-Facing Settings

I would not make these early headline controls:

- rigid "learning style" labels
- too many tiny micro-sliders
- pedagogy jargon the learner has to decode

The user should feel like they are shaping a tutor, not filling out a tax form.

## Sources Used

These shaped the recommendations:

- CAST UDL Guidelines:
  - choice and autonomy
  - relevance and authenticity
  - challenge and support
  - action-oriented feedback
  - reflection
  [CAST Engagement](https://udlguidelines.cast.org/engagement/)
  [CAST Representation](https://udlguidelines.cast.org/representation/)

- CDC adult-learning summaries:
  - self-direction
  - experience as a learning resource
  - immediate application
  - problem-centered learning
  [CDC Adult Learning Assumptions](https://www.cdc.gov/healthyschools/professional_development/e-learning/pd201/videos/transcripts/06_Adult_Learning_Assumptions.html)
  [CDC Develop Training](https://www.cdc.gov/training-development/php/about/develop-training-captivating-and-motivating-adult-learners.html)

- Review article on adult learning:
  - relevance
  - prior experience
  - active participation
  - reflection
  - facilitator role
  [Adult Learning Principles and Presentation Pearls](https://pmc.ncbi.nlm.nih.gov/articles/PMC4005174/)

## Open Questions

Questions still worth deciding:

1. Should `challenge_level` and `scaffolding_level` stay separate, or collapse into one simpler control?
2. Should `guidance_mode` be a single choice or a ranked preference?
3. Should `analogy_style` live here, or partly in identity because some personas are naturally more metaphorical?

My recommendation:

- keep `analogy_style` in teaching
- keep `challenge_level` and `scaffolding_level` separate internally, even if the UI shows them more simply
