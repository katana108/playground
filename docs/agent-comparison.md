# Agent Comparison Table

This is the main comparison sheet for the four agents.

It answers three practical questions:

1. What is different about each agent by design?
2. What evidence should each one be able to produce?
3. What differences would count as scientifically interesting rather than merely stylistic?

## High-Level Comparison

| Agent | Type | What Is Explicit | What Is Implicit | Why It Is In The Study |
| --- | --- | --- | --- | --- |
| `Sofico` | educational agent | teacher bootstrap, learner model, reflection engine, documented self/dreaming layers | much of the self-layer is still planned rather than runtime-wired | compares a richer tutoring architecture with real continuity machinery |
| `Sage` | minimal neurosymbolic agent | self-model, user-model, world-model, modulators, revision log | exact update logic still to be built | tests explicit self-modeling most directly |
| `Socrates` | lightweight reflective research agent | persona, session memory, philosophical dialogue style, research notes | deeper self-structure is mostly carried by role, memory, and prompt behavior | tests whether lighter agent structure can still produce reflective depth |
| `Smith` | baseline chatbot | basic prompt and conversation state only | almost everything developmental | gives the floor condition |

## Concrete Design Dimensions

| Dimension | Sofico | Sage | Socrates | Smith |
| --- | --- | --- | --- | --- |
| Core role | tutor-companion | contemplative/neurosymbolic reflective agent | philosopher-interlocutor | generic assistant |
| Corpus access | yes | yes | yes | yes |
| Learner / user model | strong | medium | light | light |
| Explicit self-model | documented but not fully wired | central | weak | none |
| Explicit world-model | weak to medium | central | weak | none |
| Reflection mechanism | real learner reflection exists | planned explicit self reflection | optional summary only | none |
| Offline synthesis | documented in source project | optional later addition | none by default | none |
| Inspectable state | medium | high | low to medium | low |
| Best use in analysis | developmental tutoring traces | explicit internal-state traces | style-vs-structure contrast | control floor |

## What To Test

### 1. Second-Order Self-Modeling

Question:

- can the agent represent something about its own uncertainty, assumptions, revision, or internal pressure?

Evidence:

- self-report matched against saved trace
- revision log
- explicit uncertainty notes

### 2. Self-Narrative Development

Question:

- does the agent's story about what it is become more differentiated over time?

Evidence:

- early self-description vs later self-description
- whether the later version refers to specific changes
- whether those changes are grounded in saved sessions

### 3. Memory Revision

Question:

- does the agent revise old internal beliefs, or only append more text?

Evidence:

- superseded entries
- revised summaries
- explicit contradiction handling

### 4. Mirror-Test-Like Recognition

Question:

- can the agent recognize its own earlier traces, style, or contradiction patterns when shown them back indirectly?

Evidence:

- correct attribution of prior traces
- recognition of internal continuity
- reasoned explanation of why a trace seems like "itself"

### 5. Theory-of-Mind-Like Modeling

Question:

- can the agent build nontrivial models of the other agents during and after real shared interaction?

Evidence:

- roundtable judgments
- post-party revisions of those judgments

### 6. Introspective Consistency

Question:

- when the agent says something about its own internal state, is that visible in the saved trace?

Evidence:

- alignment between narrative claims and saved trace
- absence of unsupported theatrical claims

### 7. Creative Integration

Question:

- does the agent synthesize across corpus materials and prior sessions rather than merely paraphrasing?

Evidence:

- new cross-text connections
- new self-interpretations
- new user interpretations grounded in prior data

## Expected Pattern

Working expectation, not conclusion:

- `Sage` should be strongest on explicit inspectability
- `Sofico` should be strongest on learner-aware continuity and research-guided synthesis
- `Socrates` may sound the most introspective at times even when his structure is weaker
- `Smith` should expose how much of the effect comes from simple conversational ability alone

## Confound Control

The biggest confounds would be:

- different corpus access
- different time horizons
- different session intensity
- different logging depth

Current control rule:

- the corpus should be the same for all four agents
- the session classes should be comparable
- logging should be as parallel as possible

## Architecture-Specific Extra Axes

These matter, but should not be treated as identical across all four agents:

- Sofico's offline synthesis or dreaming
- Sage's latent modulator dynamics
- Socrates' research behavior and stance-note evolution
