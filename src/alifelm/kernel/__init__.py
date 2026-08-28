"""I-02 deterministic in-memory kernel vertical slice.

The kernel is intentionally headless and ephemeral.  It contains no model
provider, persistence, replay, physical environment, or Observatory code.
"""

from .commit import (
    CommitError,
    CommitRequest,
    CommitResult,
    InMemoryCommitCoordinator,
)
from .opportunities import CognitionFixture, CognitionOpportunity, EqualOpportunityScheduler
from .run import RunStatus, SimulationRun
from .runtime import FakeDeterministicModelRuntime
from .state import Snapshot
from .transitions import (
    BirthConflictTransition,
    BirthTransition,
    MessageTransition,
    NaturalDeathTransition,
    ProposalCreatedTransition,
    ProposalRejectedTransition,
    TransitionFragment,
    TransitionKind,
)
from .validation import LawValidator
from .engine import DeterministicKernel, TickResult

__all__ = [
    "CognitionFixture",
    "CognitionOpportunity",
    "BirthConflictTransition",
    "BirthTransition",
    "CommitError",
    "CommitRequest",
    "CommitResult",
    "DeterministicKernel",
    "EqualOpportunityScheduler",
    "FakeDeterministicModelRuntime",
    "InMemoryCommitCoordinator",
    "LawValidator",
    "MessageTransition",
    "NaturalDeathTransition",
    "ProposalCreatedTransition",
    "ProposalRejectedTransition",
    "RunStatus",
    "SimulationRun",
    "Snapshot",
    "TickResult",
    "TransitionFragment",
    "TransitionKind",
]
