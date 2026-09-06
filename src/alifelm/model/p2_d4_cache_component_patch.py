"""Component-selective KV-cache transplant utilities for WORLD P2-D4.

P2-D2 established full-layer K/V cache transplantation. P2-D4 narrows that
intervention by replacing only K or only V at selected frozen cache layers,
while cloning every rebuilt tensor and preserving the nonselected component.
"""

from __future__ import annotations

from typing import Any, Iterable

from .p2_d2_cache_patch import (
    D2_EXPECTED_CACHE_LAYERS,
    _clone_tensor,
    _legacy_cache,
    _rebuild_cache,
    validate_cache_pair,
)


D4_COMPONENTS = ("K", "V")


def transplant_cache_components(
    target_cache: Any,
    donor_cache: Any,
    layer_indices: Iterable[int],
    component: str,
    expected_layers: int = D2_EXPECTED_CACHE_LAYERS,
) -> Any:
    """Return an independent target cache with selected K or V from donor.

    The unselected component at a selected layer remains from the target cache.
    Every rebuilt K/V tensor is cloned, including tensors from untouched layers,
    so neither donor nor source target cache is mutated or aliased.
    """

    if component not in D4_COMPONENTS:
        raise ValueError(f"P2-D4 component must be one of {D4_COMPONENTS}")

    target_layers, target_kind, target_type = _legacy_cache(target_cache)
    donor_layers, donor_kind, donor_type = _legacy_cache(donor_cache)
    if target_kind != donor_kind or target_type is not donor_type:
        raise ValueError("P2-D4 target/donor cache representations differ")
    if len(target_layers) != expected_layers or len(donor_layers) != expected_layers:
        raise ValueError("P2-D4 target/donor cache layer count differs from preregistration")

    selected = tuple(sorted(set(layer_indices)))
    if not selected or any(type(index) is not int for index in selected):
        raise ValueError("P2-D4 patch requires at least one integer layer index")
    if selected[0] < 0 or selected[-1] >= expected_layers:
        raise ValueError("P2-D4 patch layer index is outside the frozen range")

    validate_cache_pair(target_cache, donor_cache, expected_layers)
    selected_set = set(selected)
    rebuilt: list[tuple[Any, Any]] = []

    for index, ((target_key, target_value), (donor_key, donor_value)) in enumerate(
        zip(target_layers, donor_layers)
    ):
        if index in selected_set and component == "K":
            key, value = donor_key, target_value
        elif index in selected_set and component == "V":
            key, value = target_key, donor_value
        else:
            key, value = target_key, target_value
        rebuilt.append((_clone_tensor(key), _clone_tensor(value)))

    return _rebuild_cache(
        tuple(rebuilt),
        target_kind,
        target_type,
        template=target_cache,
    )


__all__ = ["D4_COMPONENTS", "transplant_cache_components"]
