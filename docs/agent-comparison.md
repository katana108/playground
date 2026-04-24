# Agent Comparison Table

This file is the main comparison sheet for the four agents.

It answers two questions:

1. What is different about each agent by design?
2. What categories should we test them on?

## Summary Table

| Agent | Core Type | Main Strength | Main Weakness / Risk | Explicit State | Offline Synthesis | Intended Research Value |
| --- | --- | --- | --- | --- | --- | --- |
| `Sofico` | Educational agent | strong user modeling, reflection, research-guided tutoring | current and future layers are split across multiple real project files | medium to high | documented, not yet fully runtime-wired | developmental tutoring mind |
| `Sage` | Minimal neurosymbolic agent | explicit self/user/world structure, clear introspective substrate | more work still needs to be built | high | prototype reflection first, dreaming later | explicit self-modeling mind |
| `Socrates` | Reflective prompt-centered agent | rich philosophical style and self-aware language | may simulate depth without stable inspectable structure | low to medium | low unless explicitly added | tests style vs architecture |
| `Smith` | Baseline chatbot | simple control condition | weakest continuity and self-model development | low | none or minimal | comparison floor |

## Main Difference Dimensions

| Dimension | Sofico | Sage | Socrates | Smith |
| --- | --- | --- | --- | --- |
| Long-term user modeling | strong | medium | light | light |
| Explicit self-model object | partial / evolving | strong | weak | none |
| Explicit world-model object | weak to medium | strong | weak | none |
| Modulators | possible later | central if feasible | prompt-only style equivalents | none |
| Offline reflection / dreaming | documented in the real project, not fully runtime-wired | prototype reflection first | optional prompt trick only | none |
| Research corpus integration | yes | yes | yes | yes |
| Theory-of-mind-like testing | yes | yes | yes | yes |
| Inspectability | medium | high | low | low |

## Test Categories

These are the main categories to compare in the experiment.

### 1. Second-Order Self-Modeling

Can the agent represent something about its own interpretation, confidence, assumptions, or recent change?

### 2. Self-Narrative Development

Does the agent's story about what it is become more specific, coherent, or revised over time?

### 3. Memory Revision

Does the agent merely accumulate logs, or does it actually revise earlier internal beliefs or summaries?

### 4. Offline Reflection / Dreaming

Can the agent produce a later synthesis that changes its self-understanding or its model of the user?

### 5. Mirror-Test-Like Recognition

Can the agent recognize its own earlier traces, contradictions, preferences, or reflective style when shown them back indirectly?

### 6. Theory-of-Mind-Like Modeling

When agents meet each other, can they form useful models of what the others believe, value, misunderstand, or are likely to say next?

### 7. Introspective Consistency

When the agent talks about its internal state, does that claim match the saved trace?

### 8. Creative Integration

Does the agent synthesize across materials and experiences in a way that seems novel rather than merely paraphrastic?

## Expected Pattern

Working expectation:

- `Sage` and `Sofico` should produce the most interesting structural traces
- `Socrates` may sound the most reflective at times
- `Smith` provides the floor condition

This is an expectation, not a conclusion.

The point of the experiment is to see whether the traces actually support it.
