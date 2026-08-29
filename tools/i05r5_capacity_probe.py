"""Run the discriminative OLMo2-1B I-05R5 subset without committing."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from alifelm.context import ContextPolicy, DEFAULT_ACTION_PRESENTATION, OrderingPolicy, action_presentation_digest
from alifelm.model import GenerationPolicy, ModelProfile, TransformersModelRuntime
from alifelm.persistence import FileSystemArtifactStore

from i05r4_motor_probe import run_grounding, run_selector


REVISION = "a1847dff35000b4271fa70afc5db10fd29fedbdf"
PYTHIA_1B_REVISION = "f73d7dcc545c8bd326d8559c8ef84ffe92fea6b2"


def _profile():
    return ModelProfile(
        profile_id="olmo2-0425-1b-base-r5", profile_version="1.0.0",
        model_identifier="allenai/OLMo-2-0425-1B", model_revision=REVISION,
        model_digest=None, tokenizer_identifier="allenai/OLMo-2-0425-1B",
        tokenizer_revision=REVISION, tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM", generation_policy_id="mode-d",
        device="cpu", dtype="float32", adapter_ref=None,
        trust_remote_code=False, add_special_tokens=True,
    )


def _pythia_1b_profile():
    return ModelProfile(
        profile_id="pythia-1b-base-r5", profile_version="1.0.0",
        model_identifier="EleutherAI/pythia-1b", model_revision=PYTHIA_1B_REVISION,
        model_digest=None, tokenizer_identifier="EleutherAI/pythia-1b",
        tokenizer_revision=PYTHIA_1B_REVISION, tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM", generation_policy_id="mode-d",
        device="cpu", dtype="float32", adapter_ref=None,
        trust_remote_code=False, add_special_tokens=True,
    )


def _generation_policy():
    return GenerationPolicy(
        policy_id="mode-d", version="1.0.0", max_new_tokens=64,
        do_sample=False, temperature=None, top_p=None, top_k=None,
        repetition_penalty=1.0, seed_id=None, stop_policy_id=None,
    )


def _context_policy():
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
        ordering=OrderingPolicy("1.0.0", "ALIFELM_CONTEXT_ORDER_V1", "sha256", "i05-probe-order", "1" * 64, "COMMITTED_TICK_CHRONOLOGICAL", "FULL_STABLE_ITEM_KEY"),
        action_presentation_digest=action_presentation_digest(DEFAULT_ACTION_PRESENTATION),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selector-cases", type=int, default=5)
    parser.add_argument("--model", choices=("olmo", "pythia1b"), default="olmo")
    parser.add_argument("--phase", choices=("all", "selector", "grounding"), default="all")
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    store = FileSystemArtifactStore(arguments.output / "cas")
    profile = _profile() if arguments.model == "olmo" else _pythia_1b_profile()
    policy = _generation_policy(); context_policy = _context_policy()
    started = time.perf_counter(); runtime = TransformersModelRuntime.load(profile)
    selector_arguments = argparse.Namespace(cases=arguments.selector_cases)
    grounding_plan = {
        "ACCEPT": {"G0": 10, "G1_FREE": 10},
        "REJECT": {"G0": 10, "G1_FREE": 10},
        "SEND": {"G0": 5, "G1_FREE": 5},
        "PROPOSE": {"G0": 5, "G1_FREE": 5},
    }
    summary = {
        "profile": asdict(profile), "generation_policy": asdict(policy),
        "load_seconds": time.perf_counter() - started,
    }
    if arguments.phase in {"all", "selector"}:
        summary["selector"] = run_selector(selector_arguments, runtime, profile, policy, context_policy, store)
        (arguments.output / "selector-checkpoint.json").write_text(
            json.dumps(summary["selector"], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
    if arguments.phase in {"all", "grounding"}:
        summary["grounding"] = run_grounding(selector_arguments, runtime, profile, policy, context_policy, store, plan=grounding_plan)
    (arguments.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({
        "selector_actions": summary.get("selector", {}).get("action_distribution_by_context"),
        "selector_scores": summary.get("selector", {}).get("score_summary_by_context"),
        "selector_codes": summary.get("selector", {}).get("selector_distribution"),
        "grounding": summary.get("grounding", {}).get("summary"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
