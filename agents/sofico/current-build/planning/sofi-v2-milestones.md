# Sofico V2 Milestones

Last updated: 2026-04-23

This file is the checkpoint map for rebuilding Sofico around an OpenClaw-style agent architecture.

Architecture direction:

- Slack/Telegram/web are transports, not the core architecture
- the core is an agent runtime + context engine + LLM turn interpreter + deterministic executors
- deterministic routing rules are fallback and safety rails, not the main conversational brain
- the LLM interprets human meaning; code executes concrete actions against real files/state

Rule for this project:

- build one milestone
- stop
- test it
- record the result
- only then move to the next milestone

Canonical architecture reference:

- see `planning/sofico-agent-loop-v1-spec.md`
- see `planning/document-manifest-graph-ready-schema.md`

Current implementation order for the next slice:

1. test ingest -> pending upload confirmation -> explanation handoff on real material
2. test active explanation -> quiz switch and active quiz -> explanation switch
3. separate `create_study_artifacts` from `ingest_material`
4. add `research` executor
5. decide whether `Milestone 6` starts next or whether one more hardening slice is needed

Runtime storage rule:

- all student material must live on the deployed pod's persistent learner storage
- production code must resolve learner data through `SOFI_LEARNERS_PATH` first
- local `learners/` data is only for development/testing unless explicitly migrated
- every memory/onboarding/artifact milestone must include a pod-like storage smoke test

Naming rule:

- user-facing product name is `Sofico`
- legacy internal names like `Sofi*` may remain temporarily where renaming would create churn
- a future cleanup slice must align docs, strings, class names, module names, and deployment labels where practical

## Milestone 1 — Runtime Foundation

Goal:

- create the Sofico runtime shell: the environment that loads identity, learner state, capabilities, active session state, and transport metadata before each turn
- keep it transport-independent so Slack is not the architecture

Target pieces:

- `CurrentFocus`
- `StudyArtifact`
- `ConversationState`
- `TurnContext`
- `OrchestratorResult`
- `SofiOrchestrator` interface/class shell
- existing bootstrap loader and student model

Test gate:

- code compiles
- imports work
- model shapes are readable and stable

Status:

- foundation scaffold created and tested; needs upgrade into OpenClaw-style runtime contract

## Milestone 2 — Context Engine V1

Goal:

- build the OpenClaw-style context engine for Sofico
- decide what the model should see before each turn

Lifecycle methods:

- `ingest`: record the incoming message and transport metadata
- `assemble`: build the context packet for one model call
- `compact`: later summarize/reduce old context
- `after_turn`: persist focus, memory, and decision traces

Context packet should include:

- recent conversation
- active workflow state
- current focus
- student model summary
- teacher bootstrap summary
- available topics
- document/artifact titles and source paths
- capability registry summary

Test gate:

- context packet can be printed for a learner
- packet includes all documents in a topic, not just the current note
- no API call required for this milestone

Status:

- V1 implemented: `SoficoContextEngine` assembles learner, teacher, focus, active workflows, recent messages, capabilities, topics, documents, and artifacts into an inspectable context packet

## Milestone 3 — LLM Turn Interpreter

Goal:

- add the LLM-first interpreter that reads the context packet and returns a structured turn decision
- replace phrase-exception routing as the main brain

Target pieces:

- `TurnDecision`
- `TurnInterpreter`
- strict JSON schema for decisions
- fallback to deterministic router when LLM fails or confidence is too low

Decision fields:

- capability
- intent
- target topic/artifact/document hint
- continue or exit active mode
- clarification question if needed
- confidence
- short reasoning/debug note for logs only

Test gate:

- transcript tests for natural phrases:
  - `how about Ward`
  - `there is another paper in that folder`
  - `give me recall questions`
  - `first explain`
  - `what do you think, same topic?`
- LLM decision is logged separately from executor result

Status:

- shadow-mode scaffold implemented: `TurnInterpreter` returns strict `TurnDecision` JSON when LLM is configured and safe fallback when unavailable; live comparison on pod still pending

## Milestone 4 — Agent Loop V1

Goal:

- implement the full OpenClaw-style turn loop in Sofico

Loop:

- intake
- context assembly
- LLM turn interpretation
- executor dispatch
- response composition
- persistence
- after-turn reflection hook

Design rules:

- `SessionController` is the runtime stage manager, not the business router
- `SofiOrchestrator` owns dispatch
- `TurnInterpreter` routes onboarding and pending-upload confirmation like normal capabilities
- executors receive preloaded bootstrap/context rather than reading bootstrap files directly
- the LLM may author content and structured proposals, but validated code commits writes

Test gate:

- every incoming text turn passes through the same loop
- active modes no longer own messages before interpretation
- old deterministic router is fallback only
- local CLI can run the loop without Slack
- at least one executor returns structured reflection input

Status:

- first live version implemented on 2026-04-23; needs real-material hardening tests

## Milestone 5 — Capability Executors

Goal:

- convert existing handlers into clean executors that the agent loop can call

First required executors:

- onboarding executor
- upload confirmation executor

Executors:

- onboarding executor
- artifact/material executor
- ingest/material parser executor
- explain executor
- review/quiz executor
- progress executor
- study plan executor
- research executor
- study artifact regeneration executor

Test gate:

- each executor has a simple input/output contract
- executors return state deltas and user-facing messages
- executors do not directly decide global routing
- onboarding and pending upload are no longer permanent `SessionController` exceptions

Status:

- core executor set implemented on 2026-04-23
- updated on 2026-04-27:
  - `research` now has a real executor and service
  - `create_study_artifacts` now has a dedicated executor and regeneration service
- updated on 2026-05-01:
  - added a shared learner-brief runtime service
  - turn interpreter now sees richer learner state than just identity/goals/preferences
  - explanation and review now receive a compact learner brief instead of relying only on legacy profile state
  - remaining work is cleanup/hardening:
    - thinner `SessionController`
    - real-material Slack tests
    - stronger learner-model synthesis from session memory into student model

## Milestone 6 — Artifact Memory And Document Graph

Goal:

- make uploaded sources, learning notes, question sets, lessons, and plans first-class graph-like objects

Target pieces:

- artifact registry cleanup
- duplicate/source identity handling
- document-level lookup
- per-document manifest with graph-ready metadata
- topic index storing document ids, not only topic-local file assumptions
- links:
  - uploaded source -> notes
  - notes -> question set
  - course plan -> lesson material
  - lesson material -> question set

Test gate:

- Sofico can answer `what papers are in this folder?`
- Sofico can answer `give me a quiz on my consciousness papers`
- Sofico can answer `find connections between all papers in consciousness`
- Sofico can distinguish two papers under one topic
- duplicate source uploads are flagged, not repeated
- old test artifacts can be cleaned safely

Status:

- started on 2026-04-28:
  - first-class document operations are now live:
    - `list_documents`
    - `show_document`
    - `move_document`
    - `rename_document`
  - these operate on the canonical `documents/<doc_id>/` bundles, not only topic folders
  - move now intentionally overwrites topic memberships instead of always unioning them
- expanded on 2026-04-29:
  - topic-scoped corpus plumbing is now live:
    - topic corpus builder from canonical documents
    - topic-scoped review across multiple saved papers
    - topic-scoped synthesis capability
    - repair/reindex/dedupe maintenance capability
  - remaining work:
    - real-material Slack testing of topic corpus review and synthesis
    - artifact-registry normalization under more edge cases
    - save-back path when a synthesis should become a durable artifact
    - stronger duplicate/source identity policies for multi-topic documents

## Milestone 7 — Learning Notes And Review Cards

Goal:

- implement the intended learning-note schema and card structure as runtime source of truth

Target pieces:

- `## Learning Notes`
- key concepts
- argument/structure
- examples/metaphors
- connections
- watchpoints/open questions
- `## Anki Questions` / card section
- category-aware review: Recall, Explain, Apply, Connect

Test gate:

- new uploads follow the learning-note schema
- existing docs can be reprocessed or migrated intentionally
- recall-only / apply-only quiz requests work
- SM-2 scheduling persists after review

Status:

- pending

## Milestone 8 — Transport Adapters

Goal:

- connect transports after the agent loop works locally

Transports:

- CLI/local demo
- Slack
- later: Telegram
- later: web/API

Test gate:

- same core loop handles all transports
- Slack adapter does not contain learning logic
- local CLI and Slack behave consistently

Status:

- pending

## Milestone 9 — Inner Continuity

Goal:

- add the first explicit inner-continuity layer for `Sofico`
- separate stable identity from conscious self-observation and offline synthesis
- keep the first version minimal and inspectable

Target pieces:

- `src/orchestrator/self_model/SELF_MODEL.md`
- `src/orchestrator/self_model/DREAMING.md`

Planned runtime behavior later:

- read self-model as part of warm-start orientation
- update self-model after meaningful sessions or check-ins
- run dreaming-lite less frequently as offline synthesis

Important constraint:

- these docs exist now as planning/spec artifacts
- they are not yet plugged into runtime behavior

Test gate:

- distinction is clear between `SOUL`, `SELF_MODEL`, and `DREAMING`
- trigger rules are explicit
- the feature is tracked in planning even before integration

Status:

- docs created; integration pending

## Completed / Existing Foundation To Preserve

Already built and still useful:

- teacher bootstrap files: `SOUL.md`, `IDENTITY.md`, `TEACHING.md`, `teacher_model.yaml`
- student model persistence
- capability registry
- artifact store
- current focus
- conversation memory
- upload parser
- explanation handler
- SM-2 review handler
- progress handler

These should be refactored into the OpenClaw-style runtime, not thrown away.

## Cross-Cutting Slice — Sofico Name Cleanup

Goal:

- remove confusing `Sofi` vs `Sofico` naming drift across user-facing strings, docs, runtime labels, and eventually internal code identifiers

Scope:

- first pass: user-facing bot copy, planning docs, deployment labels, and README-style docs
- second pass: internal class/module names where the rename is low-risk
- keep compatibility aliases temporarily if external integrations still import old names

Test gate:

- grep/code search shows no unintended user-facing `Sofi` strings
- Slack/demo output says `Sofico`
- imports and deployment start still work after any internal rename

Status:

- future cleanup slice; not blocking current memory/orchestrator fixes

## Cross-Cutting Slice — Pod Learner Storage Contract

Goal:

- guarantee every student's memory, onboarding state, uploaded material, study artifacts, and learner profile persist on the pod-backed learner volume

Required contract:

- `SOFI_LEARNERS_PATH` is the production source of truth for learner storage
- `user_map.yaml` is the canonical mapping from platform user IDs to stable learner folders
- repo-relative learner paths are allowed only as a local fallback for development
- generated student material should not be committed unless it is deliberate fixture/test data

Test gate:

- run a pod-like smoke test with a temporary `SOFI_LEARNERS_PATH`
- include a mapped Slack-style user ID in `user_map.yaml`
- intentionally pass a wrong project root and confirm reads/writes still land in the env learner root
- restart/recreate the session and confirm the same learner is not re-onboarded

Status:

- contract added after 2026-04-21 persistence bug; continue enforcing in future memory/artifact work

## Implementation Update — Document-First Storage

Status:

- core storage slice implemented in compatibility mode

Built:

- canonical per-document bundles under `learners/<user>/documents/<doc_id>/`
- graph-ready `manifest.yaml` generation during upload ingest
- topic indexes now store lightweight document entries
- context engine now surfaces document metadata for interpreter/runtime use
- duplicate upload path now backfills/merges canonical document bundles instead of only skipping work

Validated:

- exact duplicate re-upload keeps one canonical document bundle and does not duplicate review data
- same source content can live in multiple topics while remaining one canonical document

Next move:

- promote document-first operations to first-class capabilities:
  - `list_documents`
  - `show_document`
  - `move_document`
  - `rename_document`
  - `regenerate_notes`
  - `regenerate_questions`
  - document/topic scoped quiz and explanation

## Checkpoint Log

Use this section to record each milestone outcome briefly:

- date
- what was built
- what was tested
- result
- next move

- 2026-04-13
  Built: initial `src/orchestrator/` package with `TurnContext`, `CurrentFocus`, `StudyArtifact`, `ConversationState`, `OrchestratorResult`, and `SofiOrchestrator`
  Tested: `python3 -m compileall /Users/amikeda/Smithy/sofi/src` and a direct import smoke test via `PYTHONPATH=/Users/amikeda/Smithy/sofi/src python3`
  Result: passed
  Next move: define thin wrappers around the existing explanation / curriculum / parsing / review capabilities without wiring live Slack traffic yet
- 2026-04-14
  Built: runtime teacher bootstrap path (`SOUL.md`), student model schema/persistence, and orchestrator bootstrap loading
  Tested: `python3 -m compileall /Users/amikeda/Smithy/sofi/src` and `PYTHONPATH=/Users/amikeda/Smithy/sofi/src /Users/amikeda/Smithy/sofi/venv/bin/python` smoke test for teacher-soul load plus student-model `ADD` and `UPDATE`
  Result: passed; old learner beliefs can now be marked `superseded` while the new belief becomes active
  Next move: define the first capability registry and connect the orchestrator to teacher model + student model + artifact awareness, still without live Slack routing
- 2026-04-15
  Built: full bootstrap stack loading for `SOUL.md`, `IDENTITY.md`, `TEACHING.md`, and the student model
  Tested: `python3 -m compileall /Users/amikeda/Smithy/sofi/src` and `PYTHONPATH=/Users/amikeda/Smithy/sofi/src /Users/amikeda/Smithy/sofi/venv/bin/python` smoke test validating structured default extraction from identity and teaching bootstrap files
  Result: passed; orchestrator can now load the teacher stack as runtime context rather than only the soul file
  Next move: replace the capability summary sketch with a real capability registry contract
- 2026-04-15
  Built: first real capability registry with product-level capabilities mapped to existing handlers/services
  Tested: `python3 -m compileall /Users/amikeda/Smithy/sofi/src` and `PYTHONPATH=/Users/amikeda/Smithy/sofi/src /Users/amikeda/Smithy/sofi/venv/bin/python` smoke test validating capability names and orchestrator exposure
  Result: passed; orchestrator now exposes 8 named capabilities instead of a placeholder summary
  Next move: make StudyArtifact real as a stored/indexed domain object and begin wiring capabilities to artifact awareness
- 2026-04-15
  Built: structured `teacher_model.yaml` plus the first artifact store/registry
  Tested: `python3 -m compileall /Users/amikeda/Smithy/sofi/src` and `PYTHONPATH=/Users/amikeda/Smithy/sofi/src /Users/amikeda/Smithy/sofi/venv/bin/python` smoke test validating teacher-model load and artifact creation/retrieval
  Result: passed; teacher model now has a true system view and artifacts can now be stored and queried by type/topic
  Next move: connect existing upload/curriculum outputs into the artifact store and start using artifacts in current-focus resolution
- 2026-04-15
  Built: artifact wiring for upload/curriculum outputs, reflection engine V1, first orchestrator decision loop, and stored-history vs context-view split
  Tested: `python3 -m compileall /Users/amikeda/Smithy/sofi/src` plus smoke tests for artifact registration, capability selection, reflection update generation, and context-view reduction (12 stored messages -> 8-context view)
  Result: passed; Milestone 1 is now functionally complete as the first working V2 brain foundation
  Next move: Milestone 2 should deepen memory and begin integrating the new orchestrator path into real tutoring flows
- 2026-04-20
  Built: first explicit inner-continuity docs at `src/orchestrator/self_model/SELF_MODEL.md` and `src/orchestrator/self_model/DREAMING.md`
  Tested: document review and structure review
  Result: in place as planning/spec artifacts; not yet wired into runtime behavior
  Next move: integrate self-model and dreaming-lite only after the current tutoring slice is stable enough to benefit from reflective updates
