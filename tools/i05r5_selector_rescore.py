"""Correctly score I4 selectors at the constrained output branch point."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import statistics

from alifelm.model import R3ContextClass, TransformersModelRuntime, balanced_selector_codebooks, compile_r3_fixture, render_selector_interface, score_selectors
from alifelm.persistence import FileSystemArtifactStore

from i05r4_motor_probe import _generation_policy as pythia_policy, _policy as context_policy, _profile as pythia_profile
from i05r5_capacity_probe import _profile as olmo_profile, _pythia_1b_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("pythia", "olmo", "pythia1b"), required=True)
    parser.add_argument("--cases", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    profile = {"pythia": pythia_profile, "olmo": olmo_profile,
               "pythia1b": _pythia_1b_profile}[args.model]()
    policy = pythia_policy()
    runtime = TransformersModelRuntime.load(profile)
    store = FileSystemArtifactStore(args.output / "cas")
    records = []
    for context_class in R3ContextClass:
        for book in balanced_selector_codebooks():
            for case_index in range(args.cases):
                compiled = compile_r3_fixture(
                    context_class, case_index, policy=context_policy(),
                    model_profile_id=profile.profile_id,
                    generation_policy_id=policy.policy_id,
                    generation_seed_id="mode-d-seed", artifact_store=store,
                )
                scores = score_selectors(runtime, rendered_input=render_selector_interface(compiled, book), codebook=book)
                records.append({"context_class": context_class.value, "case_index": case_index,
                                "codebook_id": book.codebook_id,
                                "context_hash": compiled.context_pack.context_hash,
                                "scores": [asdict(score) for score in scores]})
    summary = {}
    for context_class in R3ContextClass:
        chosen = [r for r in records if r["context_class"] == context_class.value]
        totals=defaultdict(list); means=defaultdict(list); ranks=defaultdict(list)
        for record in chosen:
            for score in record["scores"]:
                totals[score["mapped_action"]].append(score["total_log_probability"])
                means[score["mapped_action"]].append(score["mean_log_probability"])
                ranks[score["mapped_action"]].append(score["rank"])
        summary[context_class.value] = {
            action: {"mean_total_log_probability": statistics.mean(totals[action]),
                     "mean_log_probability_per_token": statistics.mean(means[action]),
                     "mean_rank": statistics.mean(ranks[action]), "rank_1": ranks[action].count(1)}
            for action in totals
        }
    document = {"model": args.model, "cases": args.cases,
                "score_binding": "CONSTRAINED_GENERATED_OBJECT_SELECTOR_POSITION_V1",
                "summary": summary, "records": records}
    (args.output / "summary.json").write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
