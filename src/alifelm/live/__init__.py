"""LIVE EXP-000 integration boundary.

This package composes existing deterministic kernel, context, model-runtime,
and durable persistence components. It owns no simulation law.
"""

from .controller import (
    LiveExperimentConfig,
    LiveExperimentController,
    LiveRunObservation,
    observe_run,
)

__all__ = [
    "LiveExperimentConfig",
    "LiveExperimentController",
    "LiveRunObservation",
    "observe_run",
]
