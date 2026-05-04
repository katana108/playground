# agents-shared — Review & Integration Recommendations
*Reviewed: March 24, 2026*

GitLab: https://gitlab.com/the-smithy1/agents/agents-shared
Version: library `0.2.0`, gateway `0.1.0`

---

## What is agents-shared?

Two things in one repo:

1. **A Python library** (`src/agents_shared/`) — installed into every agent's Docker image. Gives each agent a shared vocabulary: the same Neo4j schemas, the same query functions, the same way to call other agents.

2. **A gateway service** (`gateway/`) — a standalone FastAPI reverse-proxy running in Kubernetes. The outside world (and agents talking to each other) go through it.

---

## Full folder walkthrough

### `src/agents_shared/` — the library

```
src/agents_shared/
├── schemas/
│   ├── nodes.py          ← Pydantic models for every Neo4j node type
│   ├── relationships.py  ← relationship definitions between nodes
│   ├── domains.py        ← KnowledgeDomain enum (Literacy, Team, Game, Pedagogy, Community)
│   └── cypher.py         ← all raw Cypher query strings (single source of truth)
├── knowledge/
│   ├── client.py         ← async Neo4j driver wrapper
│   ├── queries.py        ← high-level Python query functions (the main thing you call)
│   └── cache.py          ← in-memory cache for expensive queries
├── personality/
│   └── __init__.py       ← early-stage personality engine (placeholder for now)
├── interfaces/
│   ├── community_api.py  ← contract types for Minh (player registration)
│   ├── creative_api.py   ← contract types for Roland (character descriptions)
│   └── quest_api.py      ← shared types for Arturo's quest board
└── services/
    ├── client.py         ← base AgentServiceClient (aiohttp + auth)
    ├── registry.py       ← AgentRegistry (k8s service discovery)
    ├── community.py      ← typed client → Minh's API
    └── creative.py       ← typed client → Roland's API
```

**Node types defined (every Neo4j entity has a schema here):**
`AgentNode`, `PersonaNode`, `PlayerNode`, `FamiliarNode`, `WordNode`, `PersonalRepoNode`, `LearningEventNode`, `ProjectNode`, `DocumentNode`, `TeamMemberNode`, `FeatureNode`, `LoreNode`, `LocationNode`, `QuestNode`, `TeachingMethodNode`, `LearningStyleNode`, `LearningPathNode`, `ContributorNode`, `SkillNode`

**Key query functions in `knowledge/queries.py`:**

| Function | What it returns |
|----------|----------------|
| `query_player_insights(player_hash, days_back)` | Wisp's full picture of a player's learning journey |
| `record_learning_event(player_hash, event_type, context, word)` | Write a learning observation (Wisp only today) |
| `get_struggling_words(player_hash, min_struggles)` | Words the player keeps getting wrong |
| `get_near_mastery_words(player_hash, threshold)` | Words close to mastered — good for targeted practice |
| `get_recent_mastered_words(player_hash, ...)` | Words just mastered — for celebration |
| `check_frustration_level(player_hash, hours_back)` | Real-time: `needs_encouragement` bool + frustration score |
| `get_emotional_patterns(player_hash, days_back)` | Emotional state over time |
| `get_player_trends(player_hash, weeks)` | Week-over-week learning activity |
| `get_learning_summary(player_hash, days_back)` | Aggregate mastery stats |
| `get_agent_personas(agent_name)` | Agent's personas and core traits from Neo4j |

Caching: most queries are in-memory cached. `check_frustration_level` bypasses cache (needs real-time data).

---

### `gateway/` — the reverse-proxy service

```
gateway/
├── agent-registry.yaml     ← SOURCE OF TRUTH: all registered agents
├── src/gateway/
│   ├── app.py              ← FastAPI app factory
│   ├── config.py           ← reads env + YAML
│   ├── middleware/auth.py  ← Bearer token auth
│   └── routes/
│       ├── health.py       ← /healthz, /health, /health/{agent}
│       ├── registry.py     ← GET /agents
│       └── proxy.py        ← /agents/{agent}/{path} → forwards to k8s service
└── k8s/                    ← deployment, service, configmap YAMLs
```

**All registered agents:**

| Agent | K8s service | Port | Description |
|-------|------------|------|-------------|
| minh | minh | 8000 | Community steward — docs, knowledge graph |
| pearl | pearl | 8000 | Customer lifecycle |
| arturo | arturo-service | 8000 | Product lead — quests, roadmap |
| roland | roland | 8000 | Lore, creative content |
| chisel | chisel | 8000 | Security, compliance |
| **wisp** | wisp | 8080 | Fae familiar — literacy tutoring |
| **sofi** | sofi | 8000 | Learning coach — session-based tutoring |
| spark | spark | 8000 | Trading familiar |

**Sofi is already registered.** She has a slot in the gateway. She just doesn't have API endpoints yet.

---

### `tests/` and `docs/`

```
tests/
├── test_community_domain.py
├── test_domains.py
├── test_learning_events.py     ← tests for the write path (LearningEvent)
├── test_query_integration.py   ← integration tests against real Neo4j
└── test_quest_api.py

docs/implementation-plans/
├── feat-issue-3-learning-events.md   ← design doc for LearningEvent schema
├── feat-issue-4-domain-labels.md     ← domain access rules
└── feat-issue-5-agent-query-interface.md  ← planned query API for agents
```

---

## Privacy model

Players are **never stored by name** in Neo4j. Only SHA256 hashes.

- **Wisp** is the sole *writer* of `LearningEvent` nodes — only Wisp observes and records player behaviour
- All other agents are **read-only** consumers of those observations
- Spider anonymizes player data before it enters Neo4j (no PII ever hits the graph)
- Character data (how the avatar plays) is separate from player data (the actual child)

---

## How to use agents-shared from Sofi

**Install the library:**
```toml
# In sofi/pyproject.toml (or requirements.txt equivalent)
"agents-shared @ git+https://gitlab.com/the-smithy1/agents/agents-shared.git"
```

**Read player vocabulary state (e.g. for Willow):**
```python
from agents_shared.knowledge.queries import (
    get_struggling_words,
    get_near_mastery_words,
    check_frustration_level
)

# Which words should we focus on this session?
struggling = await get_struggling_words(player_hash, min_struggles=2)
near_mastery = await get_near_mastery_words(player_hash, threshold=0.7)
```

**Call another agent (e.g. check Wisp's player insights):**
```python
from agents_shared.services.client import AgentServiceClient

client = AgentServiceClient("wisp")
result = await client.get("/player/profile")
```

**Local dev (bypass k8s):**
```bash
export WISP_API_URL=http://localhost:8080
export WISP_INTERNAL_API_TOKEN=dev-token
```

---

## Recommendations for Sofi/Willow integration

### 1. Add API endpoints to Sofi (highest priority)

Sofi is registered in the gateway but has no endpoints. The minimum needed for Willow:

```
POST /session/start          ← Wisp tells Sofi: this player is starting a game session
GET  /session/{player}/words ← Wisp asks: which words should I surface this session?
POST /session/{player}/event ← Wisp reports: player just encountered/mastered a word
GET  /player/{hash}/progress ← any agent can check mastery summary
```

This is option A from the architecture discussion: **keep it in Sofi, expose via API.**

### 2. Use agents-shared Neo4j queries instead of custom ones

Sofi currently does her own SM-2 calculations and stores results in GitLab/local files. For Willow, the storage backend should be Neo4j — but the _query functions are already written_ in agents-shared. Sofi should:
- Import `get_struggling_words`, `get_near_mastery_words` instead of duplicating this logic
- Use `LearningEventNode` schema for tracking mastery events
- Write results via `record_learning_event` (or a new function if Sofi needs her own event types)

### 3. Do NOT copy spaced repetition into agents-shared yet

Will suggested this as an option. I'd recommend against it for now because:
- SM-2 logic is tightly coupled to Sofi's session management
- agents-shared is currently stateless query functions — adding session state there is a bigger change
- Better to expose it via Sofi's API first, prove it works, then extract if other agents really need it

### 4. The personality module is a natural home for Willow's persona

`src/agents_shared/personality/` exists but is early stage. This is where Willow's child-appropriate persona traits could live so Wisp and other NPCs can share the same personality definitions. Not urgent — but worth noting for the Willow design.

### 5. What Sofi needs to add to use this library

- Switch to `pyproject.toml` (agents-shared uses hatchling, not requirements.txt)
- Add async support if not already present (all agents-shared queries are `async`)
- Handle player hash: Sofi currently identifies learners by Slack user ID — needs a mapping to the anonymized Neo4j player hash

---

## Open questions before starting work

1. **Who owns the `record_learning_event` write path for vocabulary?** Today only Wisp writes. If Sofi wants to update word mastery from a study session, does she write directly, or does she tell Wisp and Wisp writes?
2. **Does Sofi need her own `LearningEvent` type**, or does she reuse Wisp's existing types?
3. **What's the Slack user ID → player hash mapping?** Sofi knows users by Slack ID; Neo4j knows them by hash. Spider likely owns this translation.
4. **Is Sofi meant to serve both Slack users (Anna's team) and game players (children)?** Or does Willow become a separate service that replaces Sofi for game use?
