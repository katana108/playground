"""Helpers for graph-ready document manifests."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str, fallback: str = "document") -> str:
    """Convert a human label into a stable filesystem-safe slug."""
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return text or fallback


def extract_learning_notes(study_document: str) -> str:
    """Return the learner-facing notes section without the quiz section."""
    notes = (
        study_document.split("## Anki Questions")[0].strip()
        if "## Anki Questions" in study_document
        else study_document.strip()
    )
    if notes.startswith("---"):
        parts = notes.split("---", 2)
        if len(parts) >= 3:
            notes = parts[2].strip()
    return notes


def build_document_manifest(
    parsed_result: Dict[str, Any],
    raw_source_content: str,
    folder_topic: str,
    doc_name: str,
) -> Dict[str, Any]:
    """Build a graph-ready document manifest from one parsed upload result."""
    metadata = parsed_result.get("metadata", {}) or {}
    title = str(metadata.get("title") or doc_name or "Untitled Document").strip()
    source_label = str(metadata.get("source") or parsed_result.get("source") or title or "uploaded material").strip()
    source_hash = "sha256:" + hashlib.sha256((raw_source_content or "").encode("utf-8")).hexdigest()
    slug = slugify(doc_name or title, fallback="document")
    doc_id = f"doc_{source_hash.split(':', 1)[1][:16]}"
    now = utc_now_iso()

    topics = _unique_list([folder_topic] + _as_list(metadata.get("topics", [])))
    tags = _as_list(metadata.get("tags", parsed_result.get("tags", [])))
    summary_short = str(metadata.get("summary_short") or "").strip()
    authors = _as_list(metadata.get("authors", []))
    year = _coerce_int(metadata.get("year"))
    doc_type = str(metadata.get("doc_type") or _infer_doc_type(source_label, title)).strip() or "other"
    key_concepts = _as_list(metadata.get("key_concepts", []))
    keywords = _unique_list(tags + _as_list(metadata.get("keywords", [])))

    manifest = {
        "schema_version": 1,
        "doc_id": doc_id,
        "title": title,
        "display_title": source_label or title,
        "slug": slug,
        "doc_type": doc_type,
        "status": "active",
        "language": str(metadata.get("language") or "en"),
        "created_at": now,
        "updated_at": now,
        "source": {
            "source_kind": str(metadata.get("source_kind") or "upload"),
            "source_label": source_label,
            "original_filename": str(metadata.get("original_filename") or ""),
            "source_url": str(metadata.get("source_url") or ""),
            "uploaded_at": now,
            "extraction_method": str(metadata.get("extraction_method") or "text"),
            "source_hash": source_hash,
        },
        "bibliography": {
            "authors": authors,
            "year": year,
            "venue": str(metadata.get("venue") or ""),
            "publisher": str(metadata.get("publisher") or ""),
            "doi": str(metadata.get("doi") or ""),
            "volume": str(metadata.get("volume") or ""),
            "issue": str(metadata.get("issue") or ""),
            "pages": str(metadata.get("pages") or ""),
            "edition": str(metadata.get("edition") or ""),
        },
        "classification": {
            "topics": topics,
            "subtopics": _as_list(metadata.get("subtopics", [])),
            "disciplines": _as_list(metadata.get("disciplines", [])),
            "schools_of_thought": _as_list(metadata.get("schools_of_thought", [])),
            "theories": _as_list(metadata.get("theories", [])),
            "document_genre": _as_list(metadata.get("document_genre", [])),
        },
        "learning": {
            "summary_short": summary_short,
            "summary_medium": "",
            "notes_status": "ready",
            "questions_status": "ready" if parsed_result.get("questions") else "missing",
            "question_count": len(parsed_result.get("questions", []) or []),
            "note_sections": [
                "learning_notes",
                "key_concepts",
                "connections",
                "watchpoints",
            ],
            "explanation_ready": bool(extract_learning_notes(parsed_result.get("study_document", "")).strip()),
            "quiz_ready": bool(parsed_result.get("questions")),
        },
        "knowledge": {
            "key_concepts": key_concepts,
            "named_entities": {
                "people": authors,
                "institutions": _as_list(metadata.get("institutions", [])),
                "works": _as_list(metadata.get("works", [])),
            },
            "keywords": keywords,
        },
        "relations": {
            "related_document_ids": [],
            "cited_author_names": _as_list(metadata.get("cited_author_names", [])),
            "contrasted_with_document_ids": [],
            "supported_by_document_ids": [],
        },
        "storage": {
            "primary_topic": folder_topic,
            "topic_memberships": topics,
            "legacy_topic_document_path": f"topics/{folder_topic}/{doc_name}.md",
            "document_root": f"documents/{doc_id}",
        },
        "field_provenance": _field_provenance(metadata),
    }
    return manifest


def build_topic_document_entry(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Create a lightweight topic-index entry for one document."""
    return {
        "doc_id": manifest.get("doc_id", ""),
        "slug": manifest.get("slug", ""),
        "title": manifest.get("title", ""),
        "display_title": manifest.get("display_title", ""),
        "doc_type": manifest.get("doc_type", "other"),
        "authors": list((((manifest.get("bibliography") or {}).get("authors")) or [])),
        "year": ((manifest.get("bibliography") or {}).get("year")),
        "source_label": ((manifest.get("source") or {}).get("source_label", "")),
        "summary_short": ((manifest.get("learning") or {}).get("summary_short", "")),
        "question_count": int(((manifest.get("learning") or {}).get("question_count", 0)) or 0),
        "tags": list((((manifest.get("knowledge") or {}).get("keywords")) or [])),
        "updated_at": manifest.get("updated_at", ""),
    }


def _field_provenance(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Record simple provenance for optional metadata filled by the parser/LLM."""
    provenance: Dict[str, Any] = {}
    field_map = {
        "authors": "bibliography.authors",
        "year": "bibliography.year",
        "venue": "bibliography.venue",
        "doc_type": "doc_type",
        "subtopics": "classification.subtopics",
        "disciplines": "classification.disciplines",
        "schools_of_thought": "classification.schools_of_thought",
        "theories": "classification.theories",
        "key_concepts": "knowledge.key_concepts",
        "keywords": "knowledge.keywords",
        "summary_short": "learning.summary_short",
    }
    for raw_key, target_path in field_map.items():
        value = metadata.get(raw_key)
        if value in (None, "", [], {}):
            continue
        provenance[target_path] = {
            "source": "document_parser",
            "method": "llm_extracted_or_inferred",
            "confidence": 0.72,
        }
    return provenance


def _as_list(value: Any) -> List[str]:
    """Normalize a scalar or list into a clean string list."""
    if not value:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]
    items = []
    for item in raw_items:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return _unique_list(items)


def _unique_list(items: List[str]) -> List[str]:
    """Preserve order while removing duplicates and blanks."""
    seen = set()
    ordered: List[str] = []
    for item in items:
        clean = str(item or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def _coerce_int(value: Any) -> int | None:
    """Convert a year-like field to int when possible."""
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _infer_doc_type(source_label: str, title: str) -> str:
    """Infer a coarse document type when the parser leaves it blank."""
    text = f"{source_label} {title}".lower()
    if any(token in text for token in ("journal", "paper", "preprint", "doi", "proceedings")):
        return "paper"
    if any(token in text for token in ("book", "chapter")):
        return "book"
    if any(token in text for token in ("blog", "substack", "post")):
        return "blog_post"
    if any(token in text for token in ("lesson", "curriculum")):
        return "lesson"
    if any(token in text for token in ("transcript", "interview", "podcast")):
        return "transcript"
    return "article"
