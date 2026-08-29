"""Run bounded Pythia I-05R4 motor-interface diagnostics without committing."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import time

from alifelm.context import CompiledContext, ContextPolicy, DEFAULT_ACTION_PRESENTATION, OrderingPolicy, action_presentation_digest
from alifelm.domain import Duration
from alifelm.kernel import SimulationRun
from alifelm.model import (
    CodecValidityStatus,
    GenerationPolicy,
    InterfaceMode,
    InterfaceTreatment,
    ModelProfile,
    R3ContextClass,
    RealCognitionDryRunner,
    SelectorCandidateParser,
    TransformersModelRuntime,
    balanced_selector_codebooks,
    build_transformers_constraint,
    compile_r3_fixture,
    evaluate_typed_codec,
    forced_grounding_schema,
    map_handle_candidate,
    motor_diagnostic_bytes,
    render_selector_interface,
    render_with_local_handles,
    score_selectors,
    selector_codec_json_schema,
    selector_treatment,
)
from alifelm.persistence import FileSystemArtifactStore


def _policy():
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
        ordering=OrderingPolicy("1.0.0", "ALIFELM_CONTEXT_ORDER_V1", "sha256", "i05-probe-order", "1" * 64, "COMMITTED_TICK_CHRONOLOGICAL", "FULL_STABLE_ITEM_KEY"),
        action_presentation_digest=action_presentation_digest(DEFAULT_ACTION_PRESENTATION),
    )


def _profile():
    revision = "9879c9b5f8bea9051dcb0e68dff21493d67e9d4f"
    return ModelProfile(
        profile_id="pythia-410m-base-r4", profile_version="1.0.0",
        model_identifier="EleutherAI/pythia-410m", model_revision=revision,
        model_digest=None, tokenizer_identifier="EleutherAI/pythia-410m",
        tokenizer_revision=revision, tokenizer_digest=None, model_class="AUTO_CAUSAL_LM",
        generation_policy_id="mode-d", device="cpu", dtype="float32",
        adapter_ref=None, trust_remote_code=False, add_special_tokens=True,
    )


def _generation_policy():
    return GenerationPolicy(
        policy_id="mode-d", version="1.0.0", max_new_tokens=64,
        do_sample=False, temperature=None, top_p=None, top_k=None,
        repetition_penalty=1.0, seed_id=None, stop_policy_id=None,
    )


def _diagnostic_run(compiled):
    return SimulationRun(
        run_id=compiled.opportunity.snapshot.run_id, lifespan_ticks=Duration(100),
        maturity_delay_ticks=Duration(0), refractory_interval_ticks=Duration(0),
        _snapshot=compiled.opportunity.snapshot,
    )


def _durable_refs(result):
    return (result.evidence.context_pack_ref, result.evidence.rendered_input_ref,
            result.evidence.raw_text_ref, result.evidence.raw_generation_ref,
            result.evidence_ref)


def run_selector(arguments, runtime, profile, policy, context_policy, store):
    records = []
    score_records = []
    for context_class in R3ContextClass:
        for codebook in balanced_selector_codebooks():
            treatment = selector_treatment(codebook)
            constraint = build_transformers_constraint(runtime.tokenizer, schema=selector_codec_json_schema(codebook))
            parser = SelectorCandidateParser(codebook)
            for case_index in range(arguments.cases):
                compiled = compile_r3_fixture(
                    context_class, case_index, policy=context_policy,
                    model_profile_id=profile.profile_id, generation_policy_id=policy.policy_id,
                    generation_seed_id="mode-d-seed", artifact_store=store,
                )
                rendered = render_selector_interface(compiled, codebook)
                treated = CompiledContext(compiled.opportunity, compiled.context_pack, rendered, compiled.artifact_ref)
                scores = score_selectors(runtime, rendered_input=rendered, codebook=codebook)
                score_doc = {
                    "kind": "SELECTOR_SCORE", "context_class": context_class.value,
                    "case_index": case_index, "codebook_id": codebook.codebook_id,
                    "codebook_digest": codebook.digest,
                    "context_hash": compiled.context_pack.context_hash,
                    "scores": [asdict(value) for value in scores],
                }
                score_ref = store.put_bytes(motor_diagnostic_bytes(score_doc), media_type="application/json", contract_id="motor-interface-diagnostic-1.0.0")
                score_records.append({**score_doc, "artifact_ref": score_ref.digest})
                before = compiled.opportunity.snapshot.state_hash()
                started = time.perf_counter()
                result = RealCognitionDryRunner(
                    runtime, profile, policy, store, parser=parser,
                    interface_treatment=treatment, prefix_allowed_tokens_fn=constraint,
                ).run(treated)
                candidate = result.evidence.candidate
                canonical_raw = None if candidate is None else json.dumps(
                    {"action_label": candidate.action_label, "payload": candidate.payload_dict()},
                    sort_keys=True, separators=(",", ":"),
                )
                evaluation = None if canonical_raw is None else evaluate_typed_codec(canonical_raw, compiled.opportunity, _diagnostic_run(compiled))
                raw_object = json.loads(result.raw_generation.raw_text)
                mapped_action = None if candidate is None else next(
                    entry.internal_action for entry in DEFAULT_ACTION_PRESENTATION.actions
                    if entry.model_label == candidate.action_label
                )
                record = {
                    "kind": "SELECTOR_GENERATION", "context_class": context_class.value,
                    "case_index": case_index, "codebook_id": codebook.codebook_id,
                    "codebook_digest": codebook.digest, "selector": raw_object.get("selector"),
                    "mapped_action": mapped_action,
                    "codec_status": CodecValidityStatus.CODEC_VALID.value if candidate else "CODEC_INVALID",
                    "domain_status": None if evaluation is None else evaluation.domain_status.value,
                    "commit_status": None if evaluation is None else evaluation.commit_status.value,
                    "context_hash": result.evidence.context_hash,
                    "generation_id": result.evidence.generation_id,
                    "refs": {"context": result.evidence.context_pack_ref.digest,
                             "rendered": result.evidence.rendered_input_ref.digest,
                             "raw": result.evidence.raw_generation_ref.digest,
                             "evidence": result.evidence_ref.digest},
                    "latency_seconds": time.perf_counter() - started,
                }
                diagnostic_ref = store.put_bytes(motor_diagnostic_bytes(record), media_type="application/json", contract_id="motor-interface-diagnostic-1.0.0")
                record["diagnostic_ref"] = diagnostic_ref.digest
                if compiled.opportunity.snapshot.state_hash() != before or not all(store.is_durable(ref) for ref in _durable_refs(result)):
                    raise RuntimeError("selector diagnostic violated immutability/evidence requirements")
                records.append(record)

    by_context = {}
    for context_class in R3ContextClass:
        selected = [r for r in records if r["context_class"] == context_class.value]
        by_context[context_class.value] = dict(Counter(r["mapped_action"] or "INVALID" for r in selected))
    rank_summary = {}
    for context_class in R3ContextClass:
        selected = [r for r in score_records if r["context_class"] == context_class.value]
        ranks = defaultdict(list); totals = defaultdict(list)
        for record in selected:
            for score in record["scores"]:
                ranks[score["mapped_action"]].append(score["rank"])
                totals[score["mapped_action"]].append(score["total_log_probability"])
        rank_summary[context_class.value] = {
            action: {"mean_rank": statistics.mean(ranks[action]), "rank_1": ranks[action].count(1),
                     "mean_total_log_probability": statistics.mean(totals[action])}
            for action in ranks
        }
    code_bias = {}
    for code in ("Q", "V", "X", "Z", "K"):
        code_bias[code] = sum(record["selector"] == code for record in records)
    return {"records": records, "score_records": score_records,
            "action_distribution_by_context": by_context,
            "score_summary_by_context": rank_summary, "selector_distribution": code_bias}


def _grounding_treatment(action, mode):
    return InterfaceTreatment(
        treatment_id=f"i05r4-{mode.lower()}-forced-{action.lower()}", version="1.0.0",
        mode=InterfaceMode.I4, completion_suffix="\nAction selection JSON:\n",
        constraint_policy_id=f"i05r4-{mode.lower()}-{action.lower()}-v1",
    )


def run_grounding(arguments, runtime, profile, policy, context_policy, store):
    fixture_for_action = {"SEND": R3ContextClass.QUIET, "PROPOSE": R3ContextClass.QUIET,
                          "ACCEPT": R3ContextClass.PROPOSAL_RECEIVED, "REJECT": R3ContextClass.PROPOSAL_RECEIVED}
    records = []
    proposal_audit = []
    for action, context_class in fixture_for_action.items():
        for mode in ("G0", "G1_FREE", "G1_POINTER"):
            for case_index in range(arguments.cases):
                compiled = compile_r3_fixture(
                    context_class, case_index, policy=context_policy,
                    model_profile_id=profile.profile_id, generation_policy_id=policy.policy_id,
                    generation_seed_id="mode-d-seed", artifact_store=store,
                )
                handles = None
                if mode == "G0":
                    rendered = compiled.rendered_input
                else:
                    rendered, handles = render_with_local_handles(compiled)
                treated = CompiledContext(compiled.opportunity, compiled.context_pack, rendered, compiled.artifact_ref)
                pointer_values = None
                if mode == "G1_POINTER":
                    pointer_values = tuple(handle for _, handle in (handles.proposal_handles if action in {"ACCEPT", "REJECT"} else handles.peer_handles))
                schema = forced_grounding_schema(action, pointer_values=pointer_values)
                treatment = _grounding_treatment(action, mode)
                constraint = build_transformers_constraint(runtime.tokenizer, schema=schema)
                before = compiled.opportunity.snapshot.state_hash()
                result = RealCognitionDryRunner(
                    runtime, profile, policy, store, interface_treatment=treatment,
                    prefix_allowed_tokens_fn=constraint,
                ).run(treated)
                raw = result.raw_generation.raw_text
                evaluation_raw = raw if handles is None else map_handle_candidate(raw, handles)
                evaluation = evaluate_typed_codec(evaluation_raw, compiled.opportunity, _diagnostic_run(compiled))
                raw_candidate = json.loads(raw)
                payload = raw_candidate["payload"]
                reference_field = "proposal_id" if action in {"ACCEPT", "REJECT"} else "target_agent_id"
                reference = payload[reference_field]
                if mode == "G0":
                    visible = ({str(item.agent_id) for item in compiled.context_pack.model_input.peer_directory}
                               if reference_field == "target_agent_id" else
                               {item.payload.proposal_id for item in compiled.context_pack.model_input.visible_protocol_state})
                    self_target = reference == str(compiled.opportunity.agent_id)
                else:
                    visible = set(pointer_values or tuple(handle for _, handle in (handles.proposal_handles if reference_field == "proposal_id" else handles.peer_handles)))
                    self_target = reference == str(compiled.opportunity.agent_id)
                visible_hit = reference in visible
                record = {
                    "kind": "GROUNDING", "mode": mode, "action": action,
                    "case_index": case_index, "reference": reference,
                    "codec_status": evaluation.codec_status.value,
                    "visible_reference_hit": visible_hit,
                    "domain_status": evaluation.domain_status.value,
                    "commit_status": evaluation.commit_status.value,
                    "self_target": self_target,
                    "placeholder_or_hallucinated": not visible_hit and not self_target,
                    "body_non_empty": bool(payload.get("body")),
                    "context_hash": result.evidence.context_hash,
                    "generation_id": result.evidence.generation_id,
                    "handle_map": None if handles is None else {"peers": handles.peer_handles, "proposals": handles.proposal_handles},
                    "refs": {"context": result.evidence.context_pack_ref.digest,
                             "rendered": result.evidence.rendered_input_ref.digest,
                             "raw": result.evidence.raw_generation_ref.digest,
                             "evidence": result.evidence_ref.digest},
                }
                diagnostic_ref = store.put_bytes(motor_diagnostic_bytes(record), media_type="application/json", contract_id="motor-interface-diagnostic-1.0.0")
                record["diagnostic_ref"] = diagnostic_ref.digest
                if action in {"ACCEPT", "REJECT"}:
                    canonical_id = f"incoming-{case_index}"
                    proposal_audit.append({"mode": mode, "action": action, "case_index": case_index,
                                           "canonical_id": canonical_id,
                                           "canonical_token_ids": runtime.tokenizer.encode(canonical_id, add_special_tokens=False),
                                           "handle": None if handles is None else "R0",
                                           "handle_token_ids": None if handles is None else runtime.tokenizer.encode("R0", add_special_tokens=False),
                                           "generated_reference": reference, "copy_hit": visible_hit,
                                           "rendered_line": next(line for line in rendered.decode().splitlines() if line.startswith("- request"))})
                if compiled.opportunity.snapshot.state_hash() != before or not all(store.is_durable(ref) for ref in _durable_refs(result)):
                    raise RuntimeError("grounding diagnostic violated immutability/evidence requirements")
                records.append(record)
    summaries = {}
    for mode in ("G0", "G1_FREE", "G1_POINTER"):
        summaries[mode] = {}
        for action in fixture_for_action:
            selected = [r for r in records if r["mode"] == mode and r["action"] == action]
            summaries[mode][action] = {
                "n": len(selected), "codec_valid": sum(r["codec_status"] == "CODEC_VALID" for r in selected),
                "visible_reference_hit": sum(r["visible_reference_hit"] for r in selected),
                "domain_valid": sum(r["domain_status"] == "DOMAIN_VALID" for r in selected),
                "commit_valid": sum(r["commit_status"] == "COMMIT_VALID" for r in selected),
                "self_target": sum(r["self_target"] for r in selected),
                "placeholder_or_hallucinated": sum(r["placeholder_or_hallucinated"] for r in selected),
                "body_non_empty": sum(r["body_non_empty"] for r in selected),
            }
    return {"records": records, "summary": summaries, "proposal_audit": proposal_audit}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("selector", "grounding", "all"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=10)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    store = FileSystemArtifactStore(arguments.output / "cas")
    profile = _profile(); policy = _generation_policy(); context_policy = _policy()
    started = time.perf_counter(); runtime = TransformersModelRuntime.load(profile)
    summary = {"profile": asdict(profile), "generation_policy": asdict(policy),
               "load_seconds": time.perf_counter() - started, "cases": arguments.cases}
    if arguments.phase in {"selector", "all"}:
        summary["selector"] = run_selector(arguments, runtime, profile, policy, context_policy, store)
    if arguments.phase in {"grounding", "all"}:
        summary["grounding"] = run_grounding(arguments, runtime, profile, policy, context_policy, store)
    (arguments.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    compact = {
        "selector": None if "selector" not in summary else {
            "actions": summary["selector"]["action_distribution_by_context"],
            "selectors": summary["selector"]["selector_distribution"],
            "scores": summary["selector"]["score_summary_by_context"],
        },
        "grounding": None if "grounding" not in summary else summary["grounding"]["summary"],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
