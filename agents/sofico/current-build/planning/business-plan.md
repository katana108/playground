# Sofi — Business Plan

*Sofi is a personal learning assistant that uses spaced repetition, Anki cards and individualized AI tutoring to help people study anything — languages, philosophy, code, history — through conversation on Slack or Telegram.*

---

## What Sofi Does

Sofi is a Slack (and eventually Telegram) bot that acts as a personal tutor. Users upload study materials — PDFs, notes, articles — and Sofi processes them into structured study documents, then runs adaptive quiz sessions using the SM-2 spaced repetition algorithm. She remembers what each learner knows, adapts to their learning style, and teaches in explanation mode when they want to go deeper.

Core capabilities:
- Document processing: raw notes → structured study materials with categorized questions
- Spaced repetition scheduling (SM-2 algorithm)
- Personalized quiz sessions with AI grading
- Explanation mode: teaches content chunk by chunk with check-ins
- Progress tracking and mastery analytics
- Learner profile: adapts tone, pacing, metaphors to each person

---

## Go-To-Market: Two Paths

### Path 1 — Open Source (Launch First)

**What we provide:** The full source code on GitHub and GitLab, free to use under an open source license.

**What the user does themselves:** Deploy it, connect their own Slack workspace or telegram, provide their own Anthropic API key, set up their own GitLab (or other storage) for learner data.

**Target persona:** Developers, AI enthusiasts, team leads, and builders who want a self-hosted learning assistant. People who are already comfortable with AI, who want to own their data, and who are interested in the emerging space of AI co-workers and educational agents.

**Why open source first:**
- Builds credibility and community before charging
- Low cost to us (zero hosting)
- Creates a pipeline of people who want more


**Email capture strategy:**
- GitHub README includes a short "Want managed hosting or interested in AI co-workers for your team?" callout with a link to a simple form (Typeform, Google Form, or a minimal landing page)
- The form asks: (1) what they're using Sofi for, (2) whether they're interested in education agents, team co-workers, or both, (3) their email
- This segments leads by interest: individual learners vs. teams vs. education

**Open questions:**
- Which open source license? (MIT for maximum adoption vs. AGPL to prevent commercial free-riding)

---

### Path 2 — Managed Subscription (Phase 2)

The hosted version: users don't need to deploy anything. They connect Sofi to their Slack or Telegram, and we handle everything.

#### Option A — Sofi Standalone Subscription

| Tier | Price | What's included |
|------|-------|-----------------|
| Free trial | 14 days | Full features, 1 user |
| Individual | ~$10/month | 1 learner, unlimited topics |
| Family | ~$20/month | Up to 4 learners (shared billing, separate profiles) |

#### Option B — Sofi as Part of Broader Subscription

If the Smithy platform develops a premium family subscription, Sofi could be included as a premium add-on or tier upgrade rather than a standalone product. This bundles value and reduces per-product friction.

So users can choose - whether they want path A or B

---

## Rough Unit Economics (Estimates — Needs Proper Analysis)

These are directional only. Real numbers need measurement from actual usage data.

### Anthropic API costs per active user per month

Assumptions: 1 study session/day (avg 15 questions), 3 document uploads/month, occasional explanation sessions and chat.

| Activity | Avg tokens | Sessions/mo | Est. cost |
|----------|------------|-------------|-----------|
| Quiz session (grading + responses) | ~4,000 | 20 | ~$0.50 |
| Document processing | ~8,000 | 3 | ~$0.35 |
| Explanation sessions | ~6,000 | 4 | ~$0.35 |
| Aside questions + chat | ~2,000 | 10 | ~$0.30 |
| **Total API cost/user/month** | | | **~$1.50** |

*Using claude-sonnet-4-6 pricing (~$3/M input, ~$15/M output tokens, blended ~$5/M estimate)*

### Storage costs per user per month

- GitLab: free tier covers most learners; at scale, ~$0.10–0.20/user/month
- If self-managed storage: negligible

### Gross margin estimate at $10/month

| Cost item | Est./user/month |
|-----------|----------------|
| Anthropic API | $1.50 |
| Storage | $0.15 |
| Infrastructure (shared, prorated) | $0.35 |
| **Total COGS** | **~$2.00** |
| **Gross margin at $10** | **~80%** |

This is a healthy margin if usage stays within assumptions. Heavy users (daily sessions + lots of uploads) could push COGS to $4–5/month. Rate limiting or a usage cap may be needed on lower tiers.

**Action needed:** Instrument actual token usage per user before setting final pricing.

---

## Platform Availability

| Platform | Status |
|----------|--------|
| Slack | Live |
| Telegram | Planned (Phase 2) |

Telegram support would open access to learners outside corporate Slack environments — students, independent learners, international users. The bot logic is platform-agnostic; adding Telegram is primarily an integration task.

---

## Future Direction: Willow (Kids Version)

A future adaptation of Sofi for children, designed as the AI backend for the game character **Willow**.

**Concept:**
- Willow is already an existing game character with a designed persona
- She has a knowledge graph (Neo4j) tracking what the child knows — starting with literacy/vocabulary
- The learning engine (spaced repetition, question categories, mastery tracking) is the same as Sofi's
- The interface is in-game, not Slack — Willow talks to the child through the game
- Learner data (what the child knows, progress) is stored in GitLab under the parents' account
- Parents have visibility; the child interacts through the game

**What makes this different from Sofi:**
- Age-appropriate language and pacing (not adult learner assumptions)
- Gamified feedback (not quiz scores — story progression, unlocks, etc.)
- Parent account management and consent layer
- Knowledge graph integration (Neo4j → what words/concepts the child has mastered)

**This is Phase 3.** Requires: in-game message layer (we already have that), Neo4j integration, parental account structure, child-safe content filtering.

---

## Phased Roadmap

| Phase | What | When |
|-------|------|------|
| **1 — Open Source Launch** | Publish to GitHub, email capture, documentation | Soon |
| **2 — Managed Subscription** | Hosted version, Telegram, payment integration | Soon |
| **3 — Willow / Kids** | Game integration, Neo4j, parental accounts | After Phase 2 |

---

## Open Questions

- [ ] Pricing validation: survey open source users before setting subscription price
- [ ] License choice: MIT vs. AGPL
- [ ] Email capture: build minimal landing page, or GitHub form link only?
- [ ] Subscription platform: Stripe? Which invoicing/billing tool?
- [ ] Phase 2 bundling: standalone Sofi subscription vs. part of broader Smithy premium tier
- [ ] Willow timeline: depends on game development schedule and Neo4j integration readiness
- [ ] Data privacy / GDPR: especially important for Willow (children's data)
