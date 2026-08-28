"""Validated scalar values used by the canonical foundation contracts."""

from __future__ import annotations


class _NonNegativeInt(int):
    """An int that rejects booleans, non-integers, and negative values."""

    def __new__(cls, value: int) -> _NonNegativeInt:
        if type(value) is not int:
            raise TypeError(f"{cls.__name__} requires an integer")
        if value < 0:
            raise ValueError(f"{cls.__name__} cannot be negative")
        return int.__new__(cls, value)


class Tick(_NonNegativeInt):
    """A simulation boundary index."""


class Duration(_NonNegativeInt):
    """A non-negative count of ticks."""


class StateVersion(_NonNegativeInt):
    """Monotonic version of a canonical snapshot."""
