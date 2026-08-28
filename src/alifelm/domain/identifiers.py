"""Opaque, stable identity types.

The foundation does not assign social meaning to identifiers.  Generation,
lineage, model, and internal random-seed information stay outside these IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


@dataclass(frozen=True, slots=True, order=True)
class OpaqueId:
    """A non-empty transport-safe identifier with no semantic interpretation."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("opaque identifiers must be strings")
        if not _IDENTIFIER.fullmatch(self.value):
            raise ValueError(
                "opaque identifiers must match [A-Za-z0-9][A-Za-z0-9_-]{0,127}"
            )

    def __str__(self) -> str:
        return self.value


class AgentId(OpaqueId):
    """Opaque identity of an agent."""


class ArtifactId(OpaqueId):
    """Stable identity of immutable evidence or payload bytes."""


class EventId(OpaqueId):
    """Identity of an immutable committed event."""


class IntentId(OpaqueId):
    """Identity of one model-proposed protocol object."""


class MessageId(OpaqueId):
    """Identity of one committed directed message."""


class OpportunityId(OpaqueId):
    """Identity of one cognition opportunity."""


class FragmentId(OpaqueId):
    """Identity of one non-authoritative transition fragment."""


class ProposalId(OpaqueId):
    """Identity of one reproduction proposal."""


class RunId(OpaqueId):
    """Identity of one simulation run."""
