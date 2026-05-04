"""
Upload Handler
Processes uploaded documents into study materials
"""

import logging
import os
import time
import yaml
from pathlib import Path
from datetime import date
from typing import Dict, Any, Optional

from orchestrator.artifact_store import ArtifactStore
from orchestrator.document_manifest import (
    build_document_manifest,
    build_topic_document_entry,
    extract_learning_notes,
)
from orchestrator.models import StudyArtifactType
from services.document_parser_service import DocumentParserService
from services.file_extraction_service import FileExtractionService

logger = logging.getLogger(__name__)


class UploadHandler:
    """Handles document uploads and processing"""

    def __init__(self, gitlab_service, slack_app=None, session_response_service=None, artifact_store=None):
        self.data_service = gitlab_service
        self.slack_app = slack_app
        self.response_service = session_response_service
        self.parser = DocumentParserService()
        self.extractor = FileExtractionService(slack_client=slack_app)
        self.artifact_store = artifact_store or ArtifactStore()
        # Pending uploads waiting for user topic confirmation
        # user_id → {"result": ..., "suggested_topic": ...}
        self.pending_uploads: Dict[str, Any] = {}

    _PENDING_UPLOAD_TTL_SECONDS = 1800  # 30 minutes

    def has_pending(self, user_id: str) -> bool:
        if user_id not in self.pending_uploads:
            persisted = self._load_pending_state(user_id)
            if persisted:
                self.pending_uploads[user_id] = persisted
        pending = self.pending_uploads.get(user_id)
        if not pending:
            return False
        created_at = pending.get("created_at")
        # Missing created_at means legacy state persisted before TTL was added —
        # treat as expired so we never get stuck on pre-fix data forever.
        if not created_at:
            logger.info("Pending upload for %s has no timestamp — clearing legacy state", user_id)
            self._clear_pending_state(user_id)
            return False
        if (time.time() - float(created_at)) > self._PENDING_UPLOAD_TTL_SECONDS:
            logger.info("Pending upload for %s expired (created_at=%s)", user_id, created_at)
            self._clear_pending_state(user_id)
            return False
        return True

    def handle_pending(self, user_id: str, message: str, say):
        """Handle user's reply to the title+folder confirmation question."""
        pending = self.pending_uploads.get(user_id)
        if not pending:
            return

        result = pending["result"]
        suggested = pending["suggested_topic"]
        source_label = pending.get("source_label") or str(result.get("source") or result.get("topic") or "").strip()
        text = message.strip().lower()

        if text in {"cancel", "never mind", "nevermind", "stop"}:
            self._clear_pending_state(user_id)
            say("Okay, I won't save that upload. We can come back to it later.")
            return

        import re

        # "yes" — use auto-detected title and suggested folder
        if text in {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "looks good", "correct", "that's right",
                    "merge", "add it", "add there", "use suggested", "save it", "save"}:
            self._clear_pending_state(user_id)
            self._finalize_save_with_label(user_id, result, suggested, source_label, say)
            return

        # "rename to X" / "call it X" / "title: X" — new title, keep folder
        title_match = re.match(
            r"^(?:rename\s+(?:it\s+)?to|call\s+it|title[:\s]+|name\s+it|save\s+as)\s+(.+)$",
            text, flags=re.IGNORECASE,
        )
        if title_match:
            new_label = title_match.group(1).strip()
            pending["source_label"] = new_label
            self._save_pending_state(user_id)
            say(
                f"Got it — I'll call it *{new_label}* and save it to *{suggested}*.\n"
                f"Say *yes* to confirm, or give me a different folder."
            )
            return

        # "move to X" / "save in X" / "save under X" / "put it in X" — new folder, keep title
        folder_match = re.match(
            r"^(?:no[,.]?\s+)?(?:move\s+(?:this\s+)?to|save\s+(?:it\s+)?(?:in|under|to)|put\s+(?:it\s+)?in|folder[:\s]+)\s+(.+)$",
            text, flags=re.IGNORECASE,
        )
        if folder_match:
            folder_topic = re.sub(r"[^a-z0-9\-_]+", "-", folder_match.group(1).strip().lower()).strip("-")
            if folder_topic:
                self._clear_pending_state(user_id)
                self._finalize_save_with_label(user_id, result, folder_topic, source_label, say)
                return

        # LLM parses free-form replies
        if self.response_service:
            parsed = self.response_service.parse_upload_topic_reply(
                user_message=message,
                suggested_topic=suggested,
                document_topic=result["topic"],
            )
            action = parsed["action"]
            if action == "unclear":
                say(
                    f"I still need to know where to save it.\n"
                    f"Say *yes* to save *{source_label}* under *{suggested}*, "
                    f"or tell me a different title or folder."
                )
                return
            folder_topic = suggested if action == "use_suggested" else (parsed.get("folder") or result["topic"])
        else:
            folder_topic = result["topic"]

        self._clear_pending_state(user_id)
        self._finalize_save_with_label(user_id, result, folder_topic, source_label, say)

    def _finalize_save_with_label(self, user: str, result: Dict[str, Any], folder_topic: str, source_label: str, say) -> Dict[str, Any]:
        """Inject the confirmed source_label into result metadata before saving."""
        import copy
        result = copy.deepcopy(result)
        if not isinstance(result.get("metadata"), dict):
            result["metadata"] = {}
        if source_label:
            result["metadata"]["source"] = source_label
            result["metadata"]["title"] = source_label
        result["source"] = source_label
        # doc_name is still the LLM-generated topic slug (used as the file path)
        return self._finalize_save(user, result, folder_topic, result["topic"], say)

    def handle(self, event, say):
        """Handle upload/process request — process inline text if present, otherwise show instructions"""
        import re
        user = event.get("user")
        raw_text = re.sub(r'<@[A-Z0-9]+>', '', event.get("text", "")).strip()

        # Strip common command prefixes to get the actual content
        content = raw_text
        for prefix in [
            "process this.", "process this,", "process this",
            "process the text above", "create a study doc",
            "create study doc", "process my notes",
        ]:
            if content.lower().startswith(prefix):
                content = content[len(prefix):].strip()
                break

        # If there's substantial content inline, process it directly
        # 200 char minimum to avoid treating short intent messages as document content
        if len(content.strip()) >= 200:
            self.process_text(content.strip(), user, say)
        else:
            say(
                "To create a study document:\n\n"
                "*Option 1: Paste your text*\n"
                "- Say `process this` and paste your notes in the same message\n\n"
                "*Option 2: Upload a file*\n"
                "- Upload a PDF, text, or DOCX file directly in chat\n\n"
                "_Tip: You can include a topic name — e.g. `process this [your notes] topic: Adobe Illustrator`_"
            )

    def handle_file_upload(self, event, say) -> Optional[Dict[str, Any]]:
        """Handle a file upload event"""
        try:
            user = event.get("user_id") or event.get("user")
            file_id = event.get("file_id")

            if not self.slack_app:
                say("File uploads require Slack app configuration. Please paste text instead.")
                return None

            say("Got your file! Extracting text... 📄")

            # Get file info from Slack
            file_info = self.slack_app.client.files_info(file=file_id)["file"]

            # Extract text
            text = self.extractor.extract_from_slack_file(file_info)

            if not text or len(text.strip()) < 50:
                say("I couldn't extract enough text from that file. Could you try:\n"
                    "- A different file format\n"
                    "- Pasting the text directly in chat")
                return None

            say(f"Extracted {len(text):,} characters. Generating notes and questions — this takes about a minute, sit tight... 🧠")

            # Process into study document
            result = self.parser.parse_document(
                content=text,
                user_id=user,
                topic_hint=None,  # TODO: Extract from message context
                user_instructions=None,
                data_service=self.data_service
            )

            # Save the study document
            return self._save_study_document(user, result, say)

        except Exception as e:
            logger.error(f"Error processing file upload: {e}", exc_info=True)
            say("Sorry, I had trouble processing that file. Try pasting the text directly, or contact support if this keeps happening.")
            return None

    def process_text(
        self,
        text: str,
        user: str,
        say,
        topic_hint: Optional[str] = None,
        user_instructions: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Process pasted text into a study document"""
        try:
            if len(text.strip()) < 50:
                say("That text seems too short to create a meaningful study document. "
                    "Please provide more content (at least a paragraph or two).")
                return None

            say(f"Processing your text ({len(text)} characters)... 🧠")

            # Parse into study document
            result = self.parser.parse_document(
                content=text,
                user_id=user,
                topic_hint=topic_hint,
                user_instructions=user_instructions,
                data_service=self.data_service
            )

            # Save the study document
            return self._save_study_document(user, result, say)

        except Exception as e:
            logger.error(f"Error processing text: {e}", exc_info=True)
            say("Sorry, I had trouble processing that text. Please try again, or contact support if this keeps happening.")
            return None

    def _save_study_document(self, user: str, result: Dict[str, Any], say) -> Dict[str, Any]:
        """Always confirm title + folder with the user before saving."""
        topic = result["topic"]
        tags = result["tags"]
        source_label = str(result.get("source") or (result.get("metadata") or {}).get("title") or topic or "the document").strip()

        existing_topics = self.data_service.get_available_topics(user)
        match = self.parser.find_matching_topic(topic, tags, existing_topics)

        if match["type"] == "match":
            suggested_topic = match["folder"]
            folder_note = f"I'd file it under *{suggested_topic}* where you already have related notes."
        elif match["type"] == "possible":
            suggested_topic = match["folder"]
            folder_note = f"I'd add it to *{suggested_topic}* — you already have notes there."
        else:
            suggested_topic = topic
            folder_note = f"I'd create a new topic called *{suggested_topic}*."

        q_count = len(result.get("questions", []) or [])
        self.pending_uploads[user] = {
            "result": result,
            "suggested_topic": suggested_topic,
            "source_label": source_label,
            "created_at": time.time(),
        }
        self._save_pending_state(user)
        say(
            f"Done! I've generated notes and *{q_count} questions*.\n\n"
            f"Here's what I found:\n"
            f"• Title: *{source_label}*\n"
            f"• Folder: {folder_note}\n\n"
            f"Does that look right? Say *yes* to save, give me a different name or folder, or say *cancel* to discard."
        )
        return {
            "status": "pending_confirmation",
            "topic": topic,
            "suggested_topic": suggested_topic,
            "question_count": q_count,
        }

    def _finalize_save(self, user: str, result: Dict[str, Any], folder_topic: str, doc_name: str, say) -> Dict[str, Any]:
        """Save study document and update index using data service."""
        try:
            study_doc = result["study_document"]
            questions = result["questions"]
            tags = result["tags"]
            is_new_folder = folder_topic == doc_name
            duplicate = self._is_duplicate_document(user, folder_topic, doc_name, questions)

            if duplicate:
                manifest = self._resolve_canonical_manifest(
                    user,
                    build_document_manifest(
                        parsed_result=result,
                        raw_source_content=str(result.get("raw_source_content") or ""),
                        folder_topic=folder_topic,
                        doc_name=doc_name,
                    ),
                )
                notes_content = extract_learning_notes(study_doc)
                if hasattr(self.data_service, "save_document_bundle"):
                    self.data_service.save_document_bundle(
                        user,
                        manifest,
                        str(result.get("raw_source_content") or ""),
                        notes_content,
                        questions,
                    )
                self._update_index_via_service(
                    user,
                    folder_topic,
                    [],
                    tags,
                    document_entry=build_topic_document_entry(manifest),
                )
                self._register_saved_artifacts(
                    user=user,
                    folder_topic=folder_topic,
                    doc_name=doc_name,
                    result=result,
                    is_new_folder=is_new_folder,
                    question_count=0,
                    manifest=manifest,
                )
                say(
                    f"I already have *{doc_name}* under *{folder_topic}*, "
                    "so I did not create duplicate notes or review questions."
                )
                logger.info("Skipped duplicate study doc for %s: folder=%s, doc=%s", user, folder_topic, doc_name)
                return {
                    "status": "duplicate",
                    "topic": folder_topic,
                    "doc_name": doc_name,
                    "question_count": 0,
                    "is_new_folder": is_new_folder,
                    "duplicate": True,
                    "doc_id": manifest.get("doc_id", ""),
                }

            # Save the .md file
            self.data_service.save_study_document(user, folder_topic, doc_name, study_doc)

            manifest = self._resolve_canonical_manifest(
                user,
                build_document_manifest(
                    parsed_result=result,
                    raw_source_content=str(result.get("raw_source_content") or ""),
                    folder_topic=folder_topic,
                    doc_name=doc_name,
                ),
            )
            notes_content = extract_learning_notes(study_doc)
            if hasattr(self.data_service, "save_document_bundle"):
                self.data_service.save_document_bundle(
                    user,
                    manifest,
                    str(result.get("raw_source_content") or ""),
                    notes_content,
                    questions,
                )

            # Update index
            added_count = self._update_index_via_service(
                user,
                folder_topic,
                questions,
                tags,
                document_entry=build_topic_document_entry(manifest),
            )
            self._register_saved_artifacts(
                user=user,
                folder_topic=folder_topic,
                doc_name=doc_name,
                result=result,
                is_new_folder=is_new_folder,
                question_count=added_count,
                manifest=manifest,
            )

            paper_label = (
                manifest.get("display_title")
                or manifest.get("title")
                or doc_name
                or "your paper"
            ).strip()
            topic_label = folder_topic or "your topic"

            if is_new_folder:
                say(
                    f"*Done!* Saved *{paper_label}* under topic *{topic_label}* "
                    f"and created {added_count} study questions across Recall, Explain, Apply, and Connect.\n\n"
                    f"Say *quiz me on {paper_label}* to start, or *explain {paper_label}* to walk through it."
                )
            elif added_count == 0:
                say(
                    f"*Done!* Saved *{paper_label}* under *{topic_label}*, "
                    f"but I did not add duplicate questions.\n\n"
                    f"Say *quiz me on {paper_label}* to review what is already there, "
                    f"or *explain {paper_label}* to walk through it."
                )
            else:
                say(
                    f"*Done!* Added {added_count} new questions for *{paper_label}* under *{topic_label}*.\n\n"
                    f"Say *quiz me on {paper_label}* to start, or *explain {paper_label}* to walk through it."
                )

            logger.info(f"Saved study doc for {user}: folder={folder_topic}, doc={doc_name}")
            return {
                "status": "saved",
                "topic": folder_topic,
                "doc_name": doc_name,
                "question_count": added_count,
                "is_new_folder": is_new_folder,
                "doc_id": manifest.get("doc_id", ""),
            }

        except Exception as e:
            logger.error(f"Error saving study document: {e}", exc_info=True)
            say("I had trouble saving the document. Please try again.")
            return {
                "status": "error",
                "topic": folder_topic,
                "doc_name": doc_name,
                "question_count": 0,
            }

    def _register_saved_artifacts(
        self,
        user: str,
        folder_topic: str,
        doc_name: str,
        result: Dict[str, Any],
        is_new_folder: bool,
        question_count: int,
        manifest: Optional[Dict[str, Any]] = None,
    ):
        """Register notes and question outputs in the artifact store."""
        source_label = result.get("source") or "uploaded material"
        source_path = f"{folder_topic}/{doc_name}.md"
        if self._artifact_exists(user, source_path):
            logger.info("Skipped duplicate artifact registration for %s", source_path)
            return

        _m = manifest or {}
        _bib = _m.get("bibliography") or {}
        _know = _m.get("knowledge") or {}
        _cls = _m.get("classification") or {}
        _ents = _know.get("named_entities") or {}

        self.artifact_store.add_artifact(
            user_id=user,
            artifact_type=StudyArtifactType.UPLOADED_SOURCE,
            title=source_label,
            topic=folder_topic,
            source_path=source_path,
            metadata={
                "source_label": source_label,
                "source_kind": "ingested_material",
                "doc_name": doc_name,
                "doc_id": _m.get("doc_id", ""),
                "doc_type": _m.get("doc_type", ""),
                "authors": _bib.get("authors") or [],
                "year": _bib.get("year"),
                "keywords": _know.get("keywords") or [],
                "key_concepts": _know.get("key_concepts") or [],
                "named_people": _ents.get("people") or [],
                "disciplines": _cls.get("disciplines") or [],
                "schools_of_thought": _cls.get("schools_of_thought") or [],
            },
        )

        notes_artifact = self.artifact_store.add_artifact(
            user_id=user,
            artifact_type=StudyArtifactType.NOTES,
            title=doc_name,
            topic=folder_topic,
            source_path=source_path,
            metadata={
                "tags": result.get("tags", []),
                "question_count": question_count,
                "doc_id": _m.get("doc_id", ""),
                "summary_short": (_m.get("learning") or {}).get("summary_short", ""),
                "authors": _bib.get("authors") or [],
                "year": _bib.get("year"),
                "doc_type": _m.get("doc_type", ""),
            },
        )

        self.artifact_store.add_artifact(
            user_id=user,
            artifact_type=StudyArtifactType.QUESTION_SET,
            title=f"{doc_name} questions",
            topic=folder_topic,
            source_path=source_path,
            source_artifact_id=notes_artifact.artifact_id,
            metadata={
                "question_count": question_count,
                "tags": result.get("tags", []),
                "doc_id": _m.get("doc_id", ""),
                "doc_type": _m.get("doc_type", ""),
            },
        )

    def _is_duplicate_document(self, user: str, folder_topic: str, doc_name: str, questions: list) -> bool:
        """Return True for exact re-uploads that would only duplicate existing review data."""
        if not hasattr(self.data_service, "study_document_exists"):
            return False
        try:
            if not self.data_service.study_document_exists(user, folder_topic, doc_name):
                return False
        except Exception:
            return False

        index_data = self.data_service.get_topic_index(user, folder_topic)
        existing_ids = {q.get("id") for q in index_data.get("questions", []) if q.get("id")}
        incoming_ids = {q.get("id") for q in questions if q.get("id")}
        return bool(incoming_ids) and incoming_ids.issubset(existing_ids)

    def _artifact_exists(self, user: str, source_path: str) -> bool:
        """Return True when this source path is already registered as an artifact."""
        try:
            return any(
                artifact.source_path == source_path
                for artifact in self.artifact_store.list_artifacts(user)
            )
        except Exception:
            return False

    def _resolve_canonical_manifest(self, user: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Reuse an existing content-backed document identity when the source hash matches."""
        source_hash = str((((manifest.get("source") or {}).get("source_hash")) or "")).strip()
        if not source_hash or not hasattr(self.data_service, "list_document_manifests"):
            return manifest

        try:
            existing = next(
                (
                    item
                    for item in self.data_service.list_document_manifests(user)
                    if str((((item.get("source") or {}).get("source_hash")) or "")).strip() == source_hash
                ),
                {},
            )
        except Exception:
            existing = {}

        if not existing or not existing.get("doc_id"):
            return manifest

        resolved = dict(manifest)
        resolved["doc_id"] = existing["doc_id"]

        classification = dict(resolved.get("classification") or {})
        existing_topics = list((((existing.get("classification") or {}).get("topics")) or []))
        new_topics = list((classification.get("topics")) or [])
        classification["topics"] = list(dict.fromkeys(existing_topics + new_topics))
        resolved["classification"] = classification

        storage = dict(resolved.get("storage") or {})
        existing_memberships = list((((existing.get("storage") or {}).get("topic_memberships")) or []))
        new_memberships = list((storage.get("topic_memberships")) or [])
        storage["topic_memberships"] = list(dict.fromkeys(existing_memberships + new_memberships))
        storage["document_root"] = f"documents/{existing['doc_id']}"
        resolved["storage"] = storage
        return resolved

    def _save_pending_state(self, user_id: str):
        """Persist pending upload confirmation state if the data service supports it."""
        pending = self.pending_uploads.get(user_id)
        if not pending:
            return
        if hasattr(self.data_service, "save_pending_upload_state"):
            try:
                self.data_service.save_pending_upload_state(user_id, pending)
            except Exception as e:
                logger.warning(f"Could not persist pending upload state for {user_id}: {e}")

    def _load_pending_state(self, user_id: str) -> Dict[str, Any]:
        """Recover pending upload confirmation state after a restart."""
        if hasattr(self.data_service, "load_pending_upload_state"):
            try:
                return self.data_service.load_pending_upload_state(user_id) or {}
            except Exception as e:
                logger.warning(f"Could not recover pending upload state for {user_id}: {e}")
        return {}

    def _clear_pending_state(self, user_id: str):
        """Remove pending upload state from memory and persistent storage."""
        self.pending_uploads.pop(user_id, None)
        if hasattr(self.data_service, "clear_pending_upload_state"):
            try:
                self.data_service.clear_pending_upload_state(user_id)
            except Exception as e:
                logger.warning(f"Could not clear pending upload state for {user_id}: {e}")

    def _update_index_via_service(
        self,
        user: str,
        topic: str,
        questions: list,
        tags: list,
        document_entry: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Load, update, and save the topic index via data service."""
        index_data = self.data_service.get_topic_index(user, topic)

        if not index_data:
            index_data = {
                "topic": topic,
                "last_updated": date.today().isoformat(),
                "questions": [],
                "documents": [],
            }
        index_data.setdefault("questions", [])
        index_data.setdefault("documents", [])

        for q in questions:
            q["tags"] = tags

        existing_ids = {q["id"] for q in index_data.get("questions", [])}
        added_count = 0
        for q in questions:
            if q["id"] not in existing_ids:
                index_data["questions"].append(q)
                existing_ids.add(q["id"])
                added_count += 1

        if document_entry and document_entry.get("doc_id"):
            existing_doc_ids = {
                str(doc.get("doc_id", ""))
                for doc in index_data.get("documents", [])
                if isinstance(doc, dict)
            }
            if document_entry["doc_id"] not in existing_doc_ids:
                index_data["documents"].append(document_entry)

        index_data["last_updated"] = date.today().isoformat()
        self.data_service.update_topic_index(user, topic, index_data)
        logger.info(f"Updated index for {user}/{topic}: {added_count} new questions")
        return added_count
