"""Sofi orchestration layer.

This package introduces a clean control surface above the existing handlers
and services. It is intentionally lightweight at first: define the shared
models and the orchestrator contract before wiring live Slack traffic through it.
"""

from .bootstrap_loader import BootstrapLoader, OrchestratorBootstrapContext
from .artifact_store import ArtifactStore
from .capability_registry import CapabilityRegistry, CapabilitySpec
from .context_engine import (
    ActiveWorkflowContext,
    DocumentContext,
    SoficoContextEngine,
    SoficoContextPacket,
    TopicContext,
)
from .context_view import ContextView, ContextViewBuilder
from .models import (
    ConversationState,
    CurrentFocus,
    FocusKind,
    OrchestratorResult,
    StudyArtifact,
    StudyArtifactType,
    TurnContext,
)
from .onboarding_flow import OnboardingSession, SoficoOnboardingFlow
from .orchestrator import SofiOrchestrator
from .reflection_engine import ReflectionEngine, SessionReflectionInput
from .student_model import (
    StudentMemoryDecision,
    StudentMemoryEntry,
    StudentMemoryUpdate,
    StudentModel,
    StudentModelStore,
)
from .turn_interpreter import TurnDecision, TurnInterpreter

__all__ = [
    "ArtifactStore",
    "BootstrapLoader",
    "CapabilityRegistry",
    "CapabilitySpec",
    "ActiveWorkflowContext",
    "ContextView",
    "ContextViewBuilder",
    "ConversationState",
    "CurrentFocus",
    "DocumentContext",
    "FocusKind",
    "OnboardingSession",
    "OrchestratorBootstrapContext",
    "OrchestratorResult",
    "ReflectionEngine",
    "SessionReflectionInput",
    "StudyArtifact",
    "StudyArtifactType",
    "SoficoOnboardingFlow",
    "SoficoContextEngine",
    "SoficoContextPacket",
    "StudentMemoryDecision",
    "StudentMemoryEntry",
    "StudentMemoryUpdate",
    "StudentModel",
    "StudentModelStore",
    "TurnContext",
    "TurnDecision",
    "TurnInterpreter",
    "TopicContext",
    "SofiOrchestrator",
]
