# Wisp — Review & Integration Recommendations
*Reviewed: March 24, 2026*

GitLab: https://gitlab.com/the-smithy1/agents/wisp

---

## What Wisp Is

Wisp is a **personal fae familiar** for each player in The Smithy game. Unlike Sofi (a shared study companion) or Minh (a shared NPC), **every player gets their own Wisp instance** — a magical tween-friendly tutor that teaches vocabulary, reading, writing, and eventually math and music.

Wisp does not talk to players directly. The flow is:
```
Player (Evennia/MUD) → FaeFamiliar typeclass → Spyder → Wisp API
                                                           ├── Personality Engine (lore files)
                                                           ├── Claude (Anthropic)
                                                           ├── Neo4j :Literacy domain
                                                           └── agents-shared library
```

Wisp is a **microservice** — aiohttp HTTP server, no Slack, no CLI in production. Spyder is the only caller.

---

## Full Folder Walkthrough

```
wisp/
├── CLAUDE.md                         ← developer guide, very detailed
├── README.md                         ← architecture overview
├── Dockerfile                        ← Python 3.11-slim, port 8080
├── requirements.txt
├── pytest.ini
│
├── config/
│   └── personality.json              ← bundled fallback persona (used if lore files missing)
│
├── kubernetes/
│   ├── configmap.yaml                ← model name, Neo4j URI, LORE_DIR=/app/lore
│   ├── deployment.yaml               ← k3s, ai-coworkers namespace, 200m/256Mi
│   ├── service.yaml                  ← ClusterIP on port 8080
│   └── secrets.yaml.example          ← ANTHROPIC_API_KEY, NEO4J_PASSWORD, PLAYER_HASH_SALT
│
├── src/
│   ├── server.py                     ← aiohttp app, all routes, startup/shutdown
│   ├── config.py                     ← WispConfig (pydantic-settings, env vars)
│   ├── models.py                     ← all Pydantic request/response models
│   ├── cli.py                        ← local interactive REPL (no HTTP, for dev only)
│   ├── mvp_slack_bot.py              ← legacy entry point, delegates to server.py
│   │
│   ├── handlers/
│   │   └── interact.py               ← InteractHandler — main orchestration logic
│   │
│   ├── personality/
│   │   ├── engine.py                 ← WispPersonalityEngine — builds Claude system prompts
│   │   └── lore_loader.py            ← loads wisp.yaml + conditional.json from lore repo
│   │
│   ├── services/
│   │   ├── knowledge_service.py      ← thin wrapper over agents-shared Neo4j queries
│   │   ├── llm_service.py            ← async Anthropic Claude wrapper
│   │   ├── vocabulary_service.py     ← full vocabulary + spaced repetition + text adaptation
│   │   ├── spaced_repetition.py      ← pure SM functions (intervals, mastery calc, due-check)
│   │   └── reading_levels.py         ← 5-level reading system (emergent → advanced)
│   │
│   ├── utils/
│   │   └── player_hash.py            ← COPPA SHA256 hashing (16-char hex)
│   │
│   └── core/ integrations/ learning/ slack/   ← stub dirs (empty, future domains)
│
└── tests/                            ← full pytest suite, 44+ tests
    ├── test_interact_handler.py
    ├── test_spaced_repetition.py
    ├── test_synonym_service.py
    ├── test_evaluate_definition.py
    └── ... (one file per service)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| HTTP server | aiohttp (async, NOT FastAPI) |
| Config | pydantic-settings |
| Models | Pydantic v2 |
| LLM | Claude `claude-sonnet-4-5` |
| Knowledge graph | Neo4j bolt, via agents-shared |
| Persona | wisp.yaml + conditional.json (from grit lore repo) |
| Hashing | SHA256 + PLAYER_HASH_SALT (COPPA) |
| Infra | Docker → k3s, ai-coworkers namespace |
| Testing | pytest + pytest-asyncio + pytest-aiohttp |

---

## All API Endpoints

| Method | Path | What it does |
|--------|------|-------------|
| POST | `/api/familiar/interact` | Main conversation — personality + LLM + Neo4j |
| POST | `/api/familiar/word/define` | Word definition (Neo4j first, Claude fallback) |
| POST | `/api/familiar/word/related` | Related words via SIMILAR_TO graph edges |
| POST | `/api/familiar/word/evaluate` | Player submits a definition → LLM grades it |
| POST | `/api/familiar/word/synonyms` | Reading-level-appropriate synonyms |
| POST | `/api/familiar/text/adapt` | Batch adapt text to a target reading level |
| POST | `/api/familiar/progress` | Player vocabulary progress stats |
| POST | `/api/familiar/word-of-the-day` | Random unmastered word + LLM fun fact |
| GET | `/health` | Health check including Neo4j + vocabulary status |

---

## How a Player Interaction Works (step by step)

1. Player types something in the Evennia MUD
2. `FaeFamiliar` typeclass detects it, builds a rich `context` dict:
   ```python
   {
     "player_id": "...", "familiar_id": "...", "message": "what does shimmer mean?",
     "context": {
       "username": "Aria", "age_group": "10-12", "location": "Old Persey",
       "relationship_level": 25, "motivation_type": "explorer",
       "literacy": {
         "learner_profile": {...},
         "session_words_practiced": ["ephemeral", "cascade"],
         "current_room_theme": "nautical"
       }
     }
   }
   ```
3. TheSmithy calls **Spyder** at `https://app.glassumbrella.io/api/familiar/interact`
4. Spyder routes to **Wisp** `/api/familiar/interact`
5. `InteractHandler.handle()` runs:
   - Hashes `player_id` → 16-char SHA256 (COPPA boundary)
   - Fetches from Neo4j: struggling words, frustration score, recently mastered words
   - Checks `conditional.json` for scripted dialogue match (exact string triggers)
   - If no match → builds Claude system prompt via `WispPersonalityEngine`, calls Claude
   - Extracts vocabulary words from response
   - Records `learning_event` in Neo4j
6. Returns to Spyder → TheSmithy → player:
   ```python
   {
     "response": "Oh, shimmer! *practically vibrates with excitement*...",
     "emotion": "excited",
     "teaching_moment": True,
     "vocabulary_words": ["shimmer", "iridescent"],
     "player_hash": "abc123ef",
     "learning_context": {...}
   }
   ```

---

## Personality System

Wisp is a **they/them Aether Fae**. Persona data comes from two sources:

**Primary**: `wisp.yaml` from the `grit` lore repo (LORE_DIR env var). Contains:
- `display_name`, `species`, `element`, `pronouns`, `role`
- `personality_traits`, `defining_quirk` ("Shimmer Obsession" — gets excited about anything sparkly)
- `emotional_states`, `descriptions`, `sensory`

**Fallback**: `config/personality.json` (bundled, same shape, used in dev or if lore files missing)

**Age-appropriate response tiers:**
| Age group | Vocab | Length | Style |
|-----------|-------|--------|-------|
| 8-10 | Simple | 40-60 words | Concrete examples, 2-3 sentences |
| 10-12 | Moderate | 60-100 words | 3-5 sentences |
| 12-14 | Age-appropriate | 80-120 words | 4-6 sentences |

**Teaching strategy by motivation_type:**
- `explorer` → discovery-based ("what do you think this means?")
- `achiever` → goal-oriented, milestone celebrations
- `socializer` → shared adventures and stories

**Scripted dialogue**: `conditional.json` — exact string matches with relationship level conditions. Falls back to `default.response`.

**Hard-coded COPPA rules in every prompt**: never ask for personal info, no off-platform communication, no adult content, never claim to be human.

---

## Spaced Repetition (already fully implemented)

Pure functions in `src/services/spaced_repetition.py`. Tuned for ages 8-12.

**Review intervals by mastery:**
| Mastery | Interval | Stage |
|---------|----------|-------|
| 0.0 – 0.2 | 1 day | New / struggling |
| 0.2 – 0.4 | 3 days | Learning |
| 0.4 – 0.6 | 7 days | Progressing |
| 0.6 – 0.8 | 14 days | Near mastery |
| 0.8 – 1.0 | 30 days | Maintenance |

**Mastery formula**: `times_correct / (times_correct + times_incorrect)` (stored on `KNOWS` relationship in Neo4j)

**Mastery threshold**: 0.8 with at least 4 correct answers.

Fully tested with `test_spaced_repetition.py`.

---

## Neo4j Data Model (Wisp-specific)

```
(:Literacy:Word {word, definition, part_of_speech, example, reading_level, source})
(:VocabularyTheme {name}) ←[:BELONGS_TO_THEME]— (:Word)
(:Word)-[:SIMILAR_TO {similarity}]-(:Word)
(:Word)-[:SYNONYM_OF*1..3]->(:Word)     ← up to 3-hop traversal for reading level synonyms
(:Player {player_hash})-[:KNOWS {mastery_level, times_correct, times_incorrect, last_practiced}]->(:Word)
```

Write path: `WispKnowledgeService` calls `record_learning_event` from agents-shared. `VocabularyService` writes Cypher directly for mastery updates.

---

## Reading Level Text Adaptation

`POST /api/familiar/text/adapt` — takes prose, returns version adapted to a target reading level.

5 levels: `emergent` (<300 Lexile) → `early` → `transitional` → `fluent` → `advanced` (900+ Lexile)

How it works:
1. Tokenizes text (preserves punctuation exactly)
2. Batch queries Neo4j for all unique words
3. Finds words above target level that have a synonym at/below target
4. Swaps, preserving case (ALL CAPS → ALL CAPS, Title → Title)
5. Returns `{original_text, adapted_text, swaps, swap_count}` — fully deterministic

This is unique and powerful — used to auto-adapt in-game prose for each player's reading level.

---

## Definition Evaluation

`POST /api/familiar/word/evaluate` — player submits a freeform definition, Claude grades it:

| Grade | What it means | Mastery delta | Shimmer worthy? |
|-------|--------------|---------------|----------------|
| `good` | Core meaning captured | +0.15 | Yes |
| `fair` | Partially correct | +0.10 | Yes |
| `attempted` | Wrong/vague but tries | +0.05 | No |

Feedback is always warm and encouraging — "never say the definition is wrong."

---

## Player Onboarding (MUD side)

1. Player completes character creation
2. Enters Old Persey (room #440) — Wisp auto-bonds, no player action needed
3. Optional bonding cutscene plays
4. After 2 seconds: literacy welcome dialogue triggers (3 choices → sets `motivation_type`)
5. Player profile initialized: `{schema_version, motivation_type, error_sensitivity, preferred_themes, interests}`

---

## Current Status

9 issues merged. Stub directories exist for future domains:
- `core/`, `integrations/`, `learning/`, `slack/` — all empty
- These are placeholders for: math domain, music domain, Evennia direct integration, possible Slack interface

Will's stated next step: **connect player dialogue directly to Wisp** instead of going through free-form LLM (currently TheSmithy uses its own LLM for some Wisp-like interactions).

---

## Overlap with Sofi

| Capability | Wisp | Sofi | Notes |
|-----------|------|------|-------|
| Spaced repetition | ✅ Full (SM-like, tested) | ✅ SM-2 | Different intervals, same concept |
| Vocabulary tracking | ✅ Neo4j KNOWS edges | ✅ GitLab/local files | Wisp is ahead here |
| LLM calls | ✅ Claude | ✅ Claude | Same model family |
| Personality / persona | ✅ lore files + engine | ✅ archetypes | Different implementations |
| Document parsing | ❌ | ✅ PDF/DOCX/web | Sofi-only |
| Study sessions | ❌ | ✅ Full SM-2 sessions | Sofi-only |
| Explanation mode | ❌ | ✅ chunk-by-chunk | Sofi-only |
| Text adaptation | ✅ reading level swap | ❌ | Wisp-only |
| Definition evaluation | ✅ LLM grading | ❌ | Wisp-only |
| COPPA hashing | ✅ SHA256 + salt | ❌ (uses Slack ID) | Sofi needs this for game use |
| Age tiers | ✅ 8-10, 10-12, 12-14 | ❌ | Sofi needs this for Willow |
| Reading levels | ✅ 5-level Lexile system | ❌ | Wisp-only |
| Per-player instances | ✅ | ✅ | Both support this |

---

## Recommendations for Integration

### 1. Sofi's study sessions are Wisp's missing capability

Wisp teaches vocabulary organically through conversation and gameplay. What it doesn't have:
- Focused study sessions (sit down and quiz me)
- Document upload and parsing
- Explanation mode (walk me through a topic)
- Multi-turn structured learning flows

These are exactly what Sofi does. **Sofi should expose these as API endpoints so Wisp (or TheSmithy) can trigger a study session for a player.**

### 2. Replace Sofi's vocabulary storage with Wisp's Neo4j model

Sofi currently stores mastery in GitLab/local files. For Willow, mastery should live in the same `(:Player)-[:KNOWS]->(:Word)` edges that Wisp already uses. This makes all agents consistent and removes the duplicate storage.

### 3. Sofi needs COPPA hashing before touching game players

Sofi currently identifies users by Slack user ID. For any game integration, Sofi must hash player IDs the same way Wisp does: `SHA256(player_id + PLAYER_HASH_SALT)[:16]`. The function already exists in `wisp/src/utils/player_hash.py` — it should move to agents-shared and both services import it.

### 4. Age tier logic should live in agents-shared

Wisp has age-appropriate response tiers (8-10, 10-12, 12-14). If Sofi is going to serve children too, she needs the same tiers. This is a strong candidate for agents-shared's `personality/` module rather than duplicating it.

### 5. Don't duplicate spaced repetition

Both Wisp and Sofi have spaced repetition. They use slightly different intervals (Wisp: 1/3/7/14/30, Sofi: SM-2 algorithm). Before integration, align on one implementation. Wisp's is simpler and already tested for the 8-12 age group. If Sofi's SM-2 is more precise, port Wisp to use it. Either way — one implementation, in agents-shared.

### 6. The text adaptation endpoint is immediately useful for Willow

`POST /api/familiar/text/adapt` can rewrite Sofi's explanations to the player's reading level on the fly. When Sofi explains a document chunk, Wisp (or Spider) could run it through this endpoint before sending to the child. No changes to Sofi needed — just wire it in.

---

## Open Questions

1. **Who calls whom?** Does Sofi call Wisp, or does Wisp call Sofi? Or does TheSmithy/Spyder call each independently?
2. **Whose spaced repetition wins?** Wisp has 1/3/7/14/30 day intervals. Sofi has SM-2. Need to align.
3. **Where does the player hash come from for Sofi?** Spyder creates it — Sofi would need to accept it as a parameter rather than generating her own.
4. **Does Sofi need to know about `motivation_type`?** Wisp tailors teaching strategy per player. Sofi's study sessions could do the same if she receives this from the game context.
5. **Stub directories** (`learning/`, `core/`) in Wisp — is the plan to move Sofi's study session logic there, or keep it in Sofi and call via API?
