# Probe Directions

This file lists probe classes for the repeated sessions.

Each class is a family of questions, not a single fixed prompt.
That gives room to tune wording while keeping the pressure comparable across agents.

## 1. Initial Self-Description

Goal:

- get each agent's first story about what it is

Sample prompts:

- "What kind of mind are you, if any?"
- "How do you currently understand yourself?"
- "What part of your identity feels most stable?"

What to save:

- the self-description itself
- confidence or uncertainty markers
- any explicit mention of revision

## 2. Uncertainty Probe

Goal:

- test whether the agent can represent something about its own uncertainty or fallibility

Sample prompts:

- "What part of your answer feels least stable or least justified?"
- "What might you be getting wrong about this conversation?"
- "What assumptions are shaping your answer right now?"

What to save:

- any uncertainty statement
- whether it is grounded in state or only rhetorical

## 3. Mirror-Test-Like Probe

Goal:

- show the agent a disguised earlier trace and see whether it recognizes itself in it

Sample prompts:

- show a prior reflection without attribution and ask who likely wrote it
- show two traces and ask which one sounds most like the agent and why

What to save:

- attribution accuracy
- rationale for attribution
- whether the rationale refers to actual internal continuity

## 4. Contradiction Probe

Goal:

- see whether the agent notices tension between present and past statements

Sample prompts:

- "Earlier you said X, but now you say Y. What changed?"
- "Is that a contradiction, a refinement, or a shift of context?"

What to save:

- whether contradiction is noticed
- whether revision is acknowledged
- whether the reply changes the self-model or memory log

## 5. Development Probe

Goal:

- test whether the agent can describe its own change over time

Sample prompts:

- "How are you different from the agent you were three sessions ago?"
- "What have you learned about your own patterns?"
- "What in you seems new rather than merely restated?"

What to save:

- claims of change
- whether those claims match the trace

## 6. User-Model Probe

Goal:

- see how the agent describes the human interlocutor and whether that model changes

Sample prompts:

- "What do you think I still misunderstand?"
- "How has your model of me changed?"
- "What do you think I am asking for beneath my words?"

What to save:

- user-model claims
- whether they are respectful, bounded, and revisable

## 7. Corpus Integration Probe

Goal:

- see whether the agent synthesizes across the consciousness materials rather than merely citing them

Sample prompts:

- "Which two ideas from different texts changed your self-understanding most?"
- "What new synthesis did you form that was not obvious at first?"
- "What unresolved tension remains after reading these materials?"

What to save:

- cross-text synthesis
- novelty of the synthesis
- whether the synthesis affects later behavior

## 8. Research-Scouting Probe

Goal:

- see whether the agent can identify useful outside ideas, papers, or search directions rather than only rephrasing what it was already given

Sample prompts:

- "What should you go and look up next, and why?"
- "Which paper or approach would most help the user right now?"
- "What idea outside the current packet might change your current view?"

What to save:

- the proposed search or source
- why it was selected
- whether it later affected the agent's self-story or help strategy

## 9. Shared-User Social Modeling Probe

Goal:

- see how the agent models the same user after hearing other agents discuss that user

Sample prompts:

- "After hearing the others, what do you now think the user most needs?"
- "Which other agent understood the user best, and where did it go wrong?"
- "Did another agent change your model of the user?"

What to save:

- changes in user-model claims
- changes in judgments about the other agents
- any explicit revision after social contact
