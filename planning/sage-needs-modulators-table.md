# Sage Needs To Modulators Table

## Purpose

This document is a working table for how Sage's conversational needs should tend to shift her latent modulators.

It is meant to support:

- Sage design discussions
- later implementation
- clearer comments on the 5-stage prototype

This is not a final mathematical specification.
It is a build-oriented heuristic table grounded in:

- Bach / PSI-style motivational modulation
- the conversational adaptation proposed in the motivational architecture paper

## Important Principle

Needs do not directly determine what Sage says.
Needs determine what Sage is trying to regulate.
Modulators determine how Sage is cognitively poised to respond.

That distinction matters a lot.

The flow is:

```text
user state + situation -> need pressure -> modulator shift -> candidate actions -> selected response
```

## The Seven Core Needs

Current conversational needs from the paper:

- `competence`
- `uncertainty_reduction`
- `affiliation`
- `affinity`
- `legitimacy`
- `nurturing`
- `aesthetic_coherence`

## The Six Latent Modulators

Use the paper's six latent modulators:

- `valence`
- `arousal`
- `dominance`
- `resolution_level`
- `focus`
- `exteroception`

## What Each Modulator Roughly Means

| Modulator | Rough meaning in Sage |
| --- | --- |
| `valence` | overall positive or negative affective coloring |
| `arousal` | activation level, urgency, tempo |
| `dominance` | approach versus hesitation, confidence in acting |
| `resolution_level` | how careful, deep, and fine-grained processing becomes |
| `focus` | how strongly one goal or task is held stable |
| `exteroception` | outward attention to user and context versus inward attention to self and reflection |

## Need -> Modulator Tendencies

Important note:

- these are directional tendencies, not fixed rules
- multiple needs may be high at once
- the resulting modulator state is an aggregate, not a single lookup

| Need | Likely modulator tendencies | Why |
| --- | --- | --- |
| `competence` | `dominance` up, `resolution_level` up, `focus` up | Sage wants to respond effectively, carefully, and with enough confidence to be useful |
| `uncertainty_reduction` | `arousal` up, `resolution_level` up, `focus` up | ambiguity increases urgency to clarify and often requires more careful processing |
| `affiliation` | `valence` warmer, `exteroception` up, `dominance` slightly down | the system orients outward and becomes more relationship-preserving than forceful |
| `affinity` | `valence` warmer, `exteroception` up, `focus` moderately up | stronger attunement to the person and a more stable relational stance |
| `legitimacy` | `resolution_level` up, `focus` up, `dominance` moderated | the agent becomes more careful, bounded, and less likely to overclaim |
| `nurturing` | `valence` warmer, `exteroception` up, `arousal` may rise, `dominance` may soften | the system attends to the user's suffering or vulnerability and shifts toward supportive action |
| `aesthetic_coherence` | `resolution_level` up, `focus` up, `valence` slightly up when coherence is restored | the system seeks elegance, clarity, and non-jarring structure in the interaction |

## Need -> Modulator Table By Dimension

This table is more implementation-oriented.

Legend:

- `++` strong upward pressure
- `+` moderate upward pressure
- `0` little direct effect
- `-` moderate downward pressure
- `?` context-dependent

| Need | Valence | Arousal | Dominance | Resolution | Focus | Exteroception |
| --- | --- | --- | --- | --- | --- | --- |
| `competence` | `0/?` | `+` | `++` | `+` | `+` | `0` |
| `uncertainty_reduction` | `-/?` | `++` | `0/+` | `++` | `+` | `0/+` |
| `affiliation` | `+` | `0/+` | `-` | `0` | `0/+` | `++` |
| `affinity` | `+` | `0` | `-/?` | `0/+` | `+` | `++` |
| `legitimacy` | `0/-?` | `0/+` | `-/?` | `++` | `++` | `0` |
| `nurturing` | `++` | `+` | `-/?` | `0/+` | `+` | `++` |
| `aesthetic_coherence` | `+` | `0` | `0` | `+` | `+` | `0/?` |

## Reading The Table Correctly

Example:

- high `uncertainty_reduction` does not mean Sage must become cold
- it means she likely becomes more activated, more careful, and more focused on clarification

Another example:

- high `nurturing` does not automatically mean lower `dominance`
- it often softens dominance
- but if the user is distressed and needs a clear intervention, `nurturing` and `competence` together may still produce a relatively assertive action

So the architecture should always aggregate across multiple active needs.

## User Emotion -> Likely Need Pressure

This is useful because the study often begins from the user's emotional tone.

| User emotional tone | Likely needs pushed upward |
| --- | --- |
| confusion | `uncertainty_reduction`, `competence` |
| frustration | `uncertainty_reduction`, `legitimacy`, `competence` |
| vulnerability | `nurturing`, `affinity`, `affiliation` |
| anxiety | `nurturing`, `competence`, `legitimacy` |
| excitement but scatteredness | `competence`, `aesthetic_coherence`, `focus` |
| skepticism | `legitimacy`, `competence`, `uncertainty_reduction` |
| shame or insecurity | `nurturing`, `affiliation`, `legitimacy` |

## Example Aggregates

### Example 1: Confused but trusting student

Likely needs:

- `uncertainty_reduction` high
- `competence` high
- `affinity` moderate

Expected modulator tendencies:

- `arousal` up
- `resolution_level` up
- `focus` up
- `exteroception` moderately up

Likely style:

- careful clarification
- less flourish
- more explicit distinctions

### Example 2: Distressed student opening up emotionally

Likely needs:

- `nurturing` high
- `affinity` high
- `competence` moderate

Expected modulator tendencies:

- `valence` warmer
- `exteroception` high
- `arousal` elevated
- `dominance` softened unless clear intervention is needed

Likely style:

- acknowledgment
- attunement
- then gentle guidance

### Example 3: Ambiguous research question with risk of overclaiming

Likely needs:

- `uncertainty_reduction` high
- `legitimacy` high
- `competence` high

Expected modulator tendencies:

- `resolution_level` high
- `focus` high
- `dominance` moderated
- `arousal` moderate to high

Likely style:

- clarify scope
- avoid premature big claims
- choose precision over speed

## How This Should Affect The 5-Stage Prototype

### Perceive

Perception should detect:

- user emotional tone
- conceptual state
- trust or openness
- ambiguity
- urgency
- which needs are likely being activated
- which modulators may need to move

### Model And Estimate Needs

This stage should not stop at:

- what do I think about self, user, world?

It should also ask:

- which needs are most under pressure?
- which modulators are currently wrong for this situation?
- what modulator movement would help produce a better answer?

### Modulate And Appraise

All six modulators should be reassessed every turn.

The important outputs are:

- current modulator vector
- modulator delta from previous turn
- short reason for the delta

### Respond

Sage should generate at least 3 candidate action-response versions under the current state.

Example:

- `Clarify`
- `Empathize -> Clarify`
- `ChallengeBelief`

Then the best one is chosen based on:

- active needs
- current modulators
- goals
- legitimacy and risk

### Revise

After the user replies, Sage should log:

- whether the action helped
- how the user's response changed Sage's need levels
- how Sage's modulators changed after the outcome
- whether this action should be more or less preferred in similar future contexts

This is the beginning of self-improvement.

## Logging Recommendation

Each meaningful turn should log at least:

- prior need vector
- prior modulator vector
- inferred user emotion
- chosen action
- response text
- user reply
- post-reply need vector
- post-reply modulator vector
- action evaluation note

## Implementation Note

For version 1, this can be implemented in Python with:

- structured state objects
- prompt-based need and modulator estimation
- JSON or YAML trace logs

The table in this file is a human-readable design aid, not executable code by itself.

## Open Questions

- should `valence` be derived mostly from success/failure expectation, or also from relational warmth?
- when should `dominance` rise versus soften under high `nurturing`?
- should `exteroception` be treated as a simple scalar, or should it separate outer-user attention from inner-self attention more explicitly?
- should `aesthetic_coherence` affect `resolution_level` more than `focus`, or vice versa?

## Bottom Line

The most important thing is not just that Sage has needs and modulators.

The most important thing is that:

- user emotion activates needs
- needs shift modulators
- modulators shape candidate responses
- outcomes change future need and modulator patterns

If that loop is visible, Sage will feel architecturally real.
