# Sofico Document Manifest And Graph-Ready Schema

Last updated: 2026-04-24

## Purpose

This document defines the future-proof metadata model for Sofico's document layer.

The goal is to support all three scopes cleanly:

1. document scope
2. topic scope
3. future knowledge-graph scope

Short rule:

- documents are the canonical learning objects
- topics are first-class metadata and retrieval scopes
- the knowledge graph will later connect documents, topics, concepts, people, theories, and claims

## Design Principles

### 1. Document-first, topic-aware

Each uploaded paper, article, post, lesson, or note set should become one canonical document object with its own identity.

Topics should remain important, but as metadata and indexes, not as the only identity.

Why:

- users naturally ask both document-level and topic-level questions
- moving a document between topics should be cheap
- one document may later belong to multiple topics
- graph edges should point to stable document ids, not temporary folder names

### 2. Fill what you can, leave the rest blank

The system should not pretend it knows metadata it cannot support.

Allowed behavior:

- extract what is explicit in the source
- infer what is strongly supported
- leave unknown fields empty

Not allowed:

- invent missing bibliographic details
- overcommit on theory, school, or author identity when evidence is weak

### 3. Metadata should be graph-friendly

Every field we store now should make future graph construction easier.

That means especially:

- stable ids
- normalized names
- structured lists for entities and concepts
- provenance and confidence for machine-filled fields

## Core Query Goals

The schema should support queries like:

- `explain Ward paper`
- `quiz me on Ward paper`
- `show my consciousness papers`
- `give me a quiz on my consciousness papers`
- `find connections between all papers in consciousness`
- `which authors recur in consciousness`
- `which theories or schools appear across these papers`
- `which papers in this topic disagree`

## Canonical Storage Shape

Recommendation:

```text
learner/
  documents/
    <doc_id>/
      manifest.yaml
      source.md
      notes.md
      questions.yaml
  topics/
    <topic_slug>/
      index.yaml
  artifacts.yaml
```

Interpretation:

- `manifest.yaml` = structured metadata for one document
- `source.md` = saved/extracted source content
- `notes.md` = the learner-facing summary / study notes for that document
- `questions.yaml` = the document's own quiz set
- `topics/<topic>/index.yaml` = topic membership and lightweight topic-level view

## Document Manifest

Recommendation: split fields into four layers.

### A. Operational Identity

These fields should be required because the runtime depends on them.

```yaml
doc_id: "doc_ward_2022_em_field_001"
title: "Qualia and Phenomenal Consciousness Arise From the Information Structure of an Electromagnetic Field in the Brain"
display_title: "Ward & Guevara (2022) EM Field Consciousness"
slug: "em-field-consciousness"
doc_type: "paper"   # paper | book | article | blog_post | note_set | lesson | transcript | other
status: "active"    # active | archived | duplicate | superseded
created_at: "2026-04-24T12:00:00Z"
updated_at: "2026-04-24T12:00:00Z"
language: "en"
```

Why these matter:

- `doc_id` is the stable identity
- `slug` is the filesystem-safe local name
- `doc_type` supports queries like `my consciousness papers`
- `status` supports dedupe and archival behavior

### B. Provenance

These fields tell us where the document came from.

```yaml
source:
  source_kind: "upload"        # upload | paste | generated | imported | curriculum
  source_label: "Ward & Guevara (2022)"
  original_filename: "ward-guevara-2022.pdf"
  source_url: ""
  uploaded_at: "2026-04-24T12:00:00Z"
  extraction_method: "pdf_text"
  source_hash: "sha256:..."
```

Why this matters:

- dedupe
- reprocessing
- auditability
- later graph import/export

### C. Bibliographic / Document Metadata

These are especially useful for papers, books, and formal articles.

All are optional except where explicitly known.

```yaml
bibliography:
  authors:
    - "C. Ward"
    - "M. Guevara"
  year: 2022
  venue: "Frontiers in Human Neuroscience"
  publisher: ""
  doi: ""
  volume: ""
  issue: ""
  pages: ""
  edition: ""
```

Useful future additions:

- editors
- translators
- ISBN
- arXiv id
- publication date granularity beyond year

### D. Intellectual Framing

These are the graph-useful conceptual hooks.

All are optional and may be partially filled.

```yaml
classification:
  topics:
    - "consciousness"
    - "electromagnetism"
  subtopics:
    - "qualia"
    - "field-theories-of-consciousness"
  disciplines:
    - "philosophy_of_mind"
    - "neuroscience"
  schools_of_thought:
    - "electromagnetic-theories-of-consciousness"
  theories:
    - "cemi"
  document_genre:
    - "theoretical_argument"
```

Why these matter:

- topic retrieval
- cross-document synthesis
- future graph clustering

## Learning Metadata

Yes: summary should be treated as metadata too, but not only metadata.

Recommendation:

- keep the full learner-facing notes in `notes.md`
- also keep a short structured summary in the manifest for retrieval and graph operations

Example:

```yaml
learning:
  summary_short: "Argues that phenomenal consciousness arises from the information structure of the brain's electromagnetic field."
  summary_medium: ""
  notes_status: "ready"          # missing | ready | stale | needs_regeneration
  questions_status: "ready"      # missing | ready | stale | needs_regeneration
  question_count: 15
  note_sections:
    - "core_idea"
    - "key_concepts"
    - "connections"
  explanation_ready: true
  quiz_ready: true
```

Why this matters:

- fast previews
- topic-level summaries
- routing to explain/quiz
- future graph search without loading full notes every time

## Concept / Entity Metadata

These should be lightweight now, but structured enough to grow later.

```yaml
knowledge:
  key_concepts:
    - "qualia"
    - "electromagnetic field"
    - "information structure"
  named_entities:
    people:
      - "C. Ward"
      - "M. Guevara"
    institutions: []
    works: []
  keywords:
    - "consciousness"
    - "em field"
    - "phenomenal consciousness"
```

This is useful even before a full graph because it supports:

- keyword retrieval
- topic summaries
- document comparison

## Relationship Metadata

We do not need a full graph implementation yet, but we should reserve relationship-friendly fields.

```yaml
relations:
  related_document_ids: []
  cited_author_names: []
  contrasted_with_document_ids: []
  supported_by_document_ids: []
```

Short-term meaning:

- mostly empty now
- later populated by synthesis and graph-building passes

## Confidence And Provenance For Filled Fields

This is the important future-proofing rule.

When the interpreter or parser fills optional metadata, it should be allowed to annotate:

- where the field came from
- how confident it is
- whether it was extracted or inferred

Example:

```yaml
field_provenance:
  bibliography.authors:
    source: "document_text"
    method: "extracted"
    confidence: 0.95
  classification.schools_of_thought:
    source: "interpreter"
    method: "inferred"
    confidence: 0.62
```

Recommendation:

- required operational fields should be code-owned and validated
- optional semantic fields may be interpreter-filled
- low-confidence optional fields should remain blank

## Topic Index

Topics should remain first-class because users think in topics.

Recommendation:

```yaml
topic: "consciousness"
display_name: "Consciousness"
document_ids:
  - "doc_ward_2022_em_field_001"
  - "doc_lerchner_2026_abstraction_001"
topic_summary_short: ""
concepts:
  - "qualia"
  - "consciousness"
  - "computation"
doc_types:
  paper: 2
updated_at: "2026-04-24T12:00:00Z"
```

This supports:

- `show my consciousness papers`
- `quiz me on my consciousness papers`
- `find connections between all papers in consciousness`

## Interpreter Fill Policy

Recommendation:

### The interpreter may fill:

- `display_title`
- `doc_type`
- `authors`
- `year`
- `venue`
- `topics`
- `subtopics`
- `disciplines`
- `schools_of_thought`
- `theories`
- `summary_short`
- `key_concepts`
- `keywords`

### The interpreter should not directly own:

- `doc_id`
- `slug`
- `source_hash`
- filesystem path decisions
- final persistence without executor validation

### Operational rule

- if explicit in source: extract
- if strongly implied: infer with provenance
- if uncertain: leave blank

## Suggested Commands To Support

Document scope:

- `show my documents`
- `show Ward paper`
- `quiz me on Ward paper`
- `regenerate notes for Ward paper`

Topic scope:

- `show documents in consciousness`
- `quiz me on my consciousness papers`
- `summarize my consciousness papers`
- `find connections between all papers in consciousness`

Future graph scope:

- `which theories recur across my consciousness documents`
- `which authors are central in this topic`
- `what connects Ward and Lerchner`

## Minimal Implementation Slice

Recommendation: do not try to implement the full graph now.

Implement next:

1. `manifest.yaml` per document
2. `source.md`, `notes.md`, `questions.yaml` per document
3. `topics/<topic>/index.yaml` storing document ids
4. interpreter fill policy for optional metadata
5. executor validation before writing

This is enough to support:

- robust document identity
- topic-level retrieval
- future graph migration without redesign

## Key Decision

The system should keep both:

- document identity
- topic grouping

That is the right compromise between:

- user-friendly retrieval
- clean engineering
- future knowledge-graph integration

## Canonical Identity Rule

- `doc_id` should be content-fingerprint-based, not folder-name-based
- reason: the same document may appear in multiple topics, be renamed, or be re-uploaded under a different display title
- practical rule:
  - topic and display title are metadata
  - content fingerprint is identity
