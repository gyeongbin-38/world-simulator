"""CPU-only contracts for the preregistered EXP-000 A40 score-selector smoke.

This module contains no model loader and performs no inference.  It freezes the
single source-selected R3 fixture and verifies that an already-compiled fixture
and frozen P2-D1 row still resolve to the exact preregistered selector identity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from alifelm.context import CompiledContext

from .score_selector import SCORE_SELECTOR_ACTION_ORDER, ScoreSelectorDecision, select_score_action


SMOKE_CONTEXT_CLASS = "QUIET"
SMOKE_CASE_INDEX = 4000
SMOKE_RUN_ID = "i05r3-quiet-4000"
SMOKE_TICK = 2
SMOKE_AGENT_ID = "A"
SMOKE_OPPORTUNITY_ID = "cbf8914977ebb729ac940ee5cdcdecf23fc0680c99797cb2b1694b7c1b052daf"
SMOKE_SELECTED_ACTION = "SEND"
SMOKE_SEED_DIGEST = "91b37369db308547a211fd40ee5c6d01f5bf632bc125a30fd46bed3915f0e227"
SMOKE_UNIFORM_NUMERATOR = 131804850447753180354580172813106518111693388313251446682588685379011516417103
SMOKE_UNIFORM_DENOMINATOR = 231584178474632390847141970017375815706539969331281128078915168015826259279872
D1_DETAILS_SHA256 = "0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17"


class ScoreSelectorSmokeError(RuntimeError):
    """A frozen smoke identity or source-evidence check failed closed."""


def sha256_file(path: Path | str) -> str:
    target = Path(path)
    if not target.is_file():
        raise ScoreSelectorSmokeError(f"required smoke source file is missing: {target}")
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_frozen_d1_row(details: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve exactly one C10/QUIET/4000 row from a parsed D1 details object."""

    try:
        rows = details["primary"]["C10"]
    except (KeyError, TypeError) as error:
        raise ScoreSelectorSmokeError("D1 details do not contain primary C10 records") from error
    if not isinstance(rows, list):
        raise ScoreSelectorSmokeError("D1 primary C10 records must be a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("context_class") == SMOKE_CONTEXT_CLASS
        and row.get("case_index") == SMOKE_CASE_INDEX
    ]
    if len(matches) != 1:
        raise ScoreSelectorSmokeError("frozen smoke row is not unique in D1 details")
    row = matches[0]
    scores = row.get("mean_scores")
    if not isinstance(scores, dict) or set(scores) != set(SCORE_SELECTOR_ACTION_ORDER):
        raise ScoreSelectorSmokeError("frozen smoke row lacks the five D1 mean scores")
    return row


def load_frozen_d1_row(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    observed = sha256_file(target)
    if observed != D1_DETAILS_SHA256:
        raise ScoreSelectorSmokeError("P2-D1 details SHA-256 differs from frozen smoke source")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScoreSelectorSmokeError("P2-D1 details are not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise ScoreSelectorSmokeError("P2-D1 details root must be an object")
    return select_frozen_d1_row(payload)


def verify_compiled_smoke_fixture(
    compiled: CompiledContext,
    source_row: Mapping[str, Any],
) -> ScoreSelectorDecision:
    """Verify compiled/source identity and reproduce the frozen source-only decision."""

    if not isinstance(compiled, CompiledContext):
        raise TypeError("compiled must be a CompiledContext")
    opportunity = compiled.opportunity
    observed_identity = (
        opportunity.run_id.value,
        int(opportunity.tick),
        opportunity.agent_id.value,
        opportunity.opportunity_id.value,
    )
    expected_identity = (
        SMOKE_RUN_ID,
        SMOKE_TICK,
        SMOKE_AGENT_ID,
        SMOKE_OPPORTUNITY_ID,
    )
    if observed_identity != expected_identity:
        raise ScoreSelectorSmokeError("compiled smoke opportunity identity drifted")

    expected_rendered_sha = source_row.get("rendered_context_sha256")
    actual_rendered_sha = hashlib.sha256(compiled.rendered_input).hexdigest()
    if not isinstance(expected_rendered_sha, str) or actual_rendered_sha != expected_rendered_sha:
        raise ScoreSelectorSmokeError("compiled smoke context bytes differ from frozen D1 row")

    scores = source_row.get("mean_scores")
    if not isinstance(scores, Mapping):
        raise ScoreSelectorSmokeError("frozen D1 row mean_scores are missing")
    decision = select_score_action(
        scores,
        run_id=opportunity.run_id,
        tick=opportunity.tick,
        opportunity_id=opportunity.opportunity_id,
        agent_id=opportunity.agent_id,
    )
    if decision.selected_action != SMOKE_SELECTED_ACTION:
        raise ScoreSelectorSmokeError("source-only smoke selector no longer chooses frozen SEND")
    if decision.seed_digest != SMOKE_SEED_DIGEST:
        raise ScoreSelectorSmokeError("source-only smoke selector seed digest drifted")
    if (
        decision.uniform_numerator != SMOKE_UNIFORM_NUMERATOR
        or decision.uniform_denominator != SMOKE_UNIFORM_DENOMINATOR
    ):
        raise ScoreSelectorSmokeError("source-only smoke selector exact uniform variate drifted")
    return decision


__all__ = [
    "D1_DETAILS_SHA256",
    "SMOKE_AGENT_ID",
    "SMOKE_CASE_INDEX",
    "SMOKE_CONTEXT_CLASS",
    "SMOKE_OPPORTUNITY_ID",
    "SMOKE_RUN_ID",
    "SMOKE_SEED_DIGEST",
    "SMOKE_SELECTED_ACTION",
    "SMOKE_TICK",
    "SMOKE_UNIFORM_DENOMINATOR",
    "SMOKE_UNIFORM_NUMERATOR",
    "ScoreSelectorSmokeError",
    "load_frozen_d1_row",
    "select_frozen_d1_row",
    "sha256_file",
    "verify_compiled_smoke_fixture",
]
