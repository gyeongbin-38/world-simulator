import json
from pathlib import Path


N0_PREFIXES = {
    "N0-CONTRACT-",
    "N0-COMPAT-",
    "N0-DETERMINISM-",
    "N0-SYMMETRY-",
    "N0-HASH-",
    "N0-CAS-",
    "N0-CRASH-",
    "N0-MUTATION-",
    "N0-PEFT-",
    "N0-GGUF-",
    "N0-ISOLATION-",
    "N0-VIABILITY-",
    "N0-LEAKAGE-",
}


def load_json_yaml(repository_root: Path, relative: str) -> dict:
    return json.loads((repository_root / relative).read_text(encoding="utf-8"))


def test_n0_machine_documents_are_valid_json_compatible_yaml(
    repository_root: Path,
) -> None:
    for relative in (
        "architecture/MANIFEST.yaml",
        "specs/domain/genome.schema.yaml",
        "specs/protocol/inheritance-operator.schema.yaml",
        "specs/protocol/genome-evidence.schema.yaml",
        "specs/experiments/founder-model-admission.yaml",
        "specs/experiments/N0-heredity-operator-admission.yaml",
    ):
        assert isinstance(load_json_yaml(repository_root, relative), dict), relative


def test_n0_architecture_manifest_has_one_owner_per_contract(
    repository_root: Path,
) -> None:
    manifest = load_json_yaml(repository_root, "architecture/MANIFEST.yaml")
    owned_paths = (
        [manifest["semantic_owner"], manifest["sequence_owner"]]
        + manifest["field_owners"]
        + manifest["decision_records"]
        + manifest["baseline_decision_records"]
        + [manifest["founder_admission_owner"], manifest["admission_owner"]]
    )
    assert len(owned_paths) == len(set(owned_paths))
    for relative in owned_paths:
        assert (repository_root / relative).is_file(), relative
    assert set(manifest["test_id_prefixes"]) == N0_PREFIXES
    assert manifest["exp000_change"] == "SELF_SEND_GAP_RESOLUTION_ONLY"
    assert manifest["dependency_dag"]["M2_requires_N0"] is False
    assert manifest["n0_control_treatments"] == ["H0_NULL", "H0_RESET_ZERO"]


def test_n0_genome_contract_distinguishes_null_and_zero_adapter(
    repository_root: Path,
) -> None:
    schema = load_json_yaml(repository_root, "specs/domain/genome.schema.yaml")
    defs = schema["$defs"]
    null = defs["nullGenome"]["properties"]
    adapter = defs["adapterGenome"]
    required = set(adapter["required"])

    assert null["genome_type"]["const"] == "NULL_GENOME"
    assert null["neural_heredity_enabled"]["const"] is False
    assert adapter["properties"]["genome_type"]["const"] == "ADAPTER_GENOME"
    assert adapter["properties"]["neural_heredity_enabled"]["const"] is True
    assert "ZERO_ADAPTER_SENTINEL" in adapter["properties"]["representation_kind"]["enum"]
    inherited_operators = adapter["allOf"][1]["else"]["properties"][
        "inheritance_operator_id"
    ]["enum"]
    assert "H0_RESET_ZERO" in inherited_operators
    assert "H0_NULL" not in inherited_operators
    assert {
        "genome_id",
        "genome_schema_version",
        "base_model_ref",
        "base_model_digest",
        "architecture_signature",
        "tokenizer_digest",
        "adapter_schema_version",
        "adapter_rank",
        "target_modules",
        "adapter_scaling_metadata",
        "canonical_artifact_ref",
        "canonical_artifact_digest",
        "effective_delta_digest",
        "generation",
        "parent_genome_a",
        "parent_genome_b",
        "birth_event_ref",
        "inheritance_operator_id",
        "inheritance_operator_version",
        "mutation_operator_id",
        "mutation_operator_version",
        "rng_derivation_ref",
        "created_by",
    } <= required
    forbidden = {"personality", "fitness", "benchmark", "trust", "social_rank"}
    assert not forbidden & set(adapter["properties"])


def test_n0_operator_contract_freezes_symmetric_effective_delta_laws(
    repository_root: Path,
) -> None:
    schema = load_json_yaml(
        repository_root, "specs/protocol/inheritance-operator.schema.yaml"
    )
    branches = {
        branch["properties"]["operator_id"]["const"]: branch["properties"]
        for branch in schema["oneOf"]
    }

    assert branches["H1_SYMMETRIC_DELTA_BLEND"]["parameters"]["properties"]["alpha"]["const"] == "0.5"
    h2 = branches["H2_RANDOM_DELTA_CROSSOVER"]["parameters"]["properties"]
    assert h2["mask_granularity"]["const"] == "MODULE"
    assert h2["canonical_parent_zero_probability"]["const"] == "0.5"
    assert schema["properties"]["declared_symmetric"]["const"] is True
    assert schema["properties"]["parent_order_policy"]["const"].endswith("_ASC_V1")
    assert schema["properties"]["rank_policy"]["properties"]["policy_id"]["const"] == "FIXED_MANIFEST_RANK"
    reset = branches["H0_RESET_ZERO"]
    assert reset["compatibility_requirement"]["const"] == "EXPERIMENT_BASE_EXACT_RESET_CONTROL"
    assert reset["parameters"]["properties"]["child_representation"]["const"] == "ZERO_ADAPTER_SENTINEL"
    assert reset["parameters"]["properties"]["parental_neural_contribution"]["const"] == "NONE"
    assert reset["mutation"]["$ref"] == "#/$defs/noMutation"


def test_n0_rng_contract_has_required_causal_inputs_and_named_streams(
    repository_root: Path,
) -> None:
    schema = load_json_yaml(
        repository_root, "specs/protocol/inheritance-operator.schema.yaml"
    )
    rng = schema["$defs"]["rngPolicy"]["properties"]
    assert rng["kdf"]["const"] == "HKDF-SHA-256"
    assert set(rng["required_inputs"]["const"]) >= {
        "root_seed",
        "replication_id",
        "child_birth_seq",
        "sorted_parent_genome_digests",
        "genome_policy_version",
        "inheritance_operator_id",
        "inheritance_operator_version",
        "mutation_operator_id",
        "mutation_operator_version",
    }
    assert set(rng["substreams"]["const"]) == {
        "GENOME_CROSSOVER",
        "GENOME_MUTATION_MASK",
        "GENOME_MUTATION_NOISE",
        "GENOME_DECOMPOSITION",
    }
    assert {"wall_time", "thread_or_completion_order", "retry_count"} <= set(
        rng["forbidden_sources"]["const"]
    )


def test_n0_evidence_is_research_only_and_reconstructable_by_reference(
    repository_root: Path,
) -> None:
    schema = load_json_yaml(repository_root, "specs/protocol/genome-evidence.schema.yaml")
    assert schema["properties"]["classification"]["const"] == "RESEARCHER_ONLY"
    assert {
        "child_genome_digest",
        "parent_a_genome_digest",
        "parent_b_genome_digest",
        "base_model_digest",
        "compatibility_class",
        "rng_derivation_digest",
        "effective_delta_digest",
        "effective_delta_norm",
        "distance_parent_a",
        "distance_parent_b",
        "changed_parameter_count",
        "canonical_artifact_ref",
        "reconstruction_inputs",
    } <= set(schema["required"])
    reconstruction = schema["properties"]["reconstruction_inputs"]["properties"]
    assert reconstruction["reference_backend_id"]["const"] == "N0_REFERENCE_GENOME_CONSTRUCTION_BACKEND"
    assert reconstruction["effective_delta_codec_id"]["const"] == "ALIFELM_EFFECTIVE_DELTA_V1"


def test_n0_admission_catalog_covers_every_required_category_without_performance_selection(
    repository_root: Path,
) -> None:
    admission = load_json_yaml(
        repository_root, "specs/experiments/N0-heredity-operator-admission.yaml"
    )
    test_ids = [case["id"] for case in admission["tests"]]
    assert len(test_ids) == len(set(test_ids))
    for prefix in N0_PREFIXES:
        assert any(test_id.startswith(prefix) for test_id in test_ids), prefix
    assert admission["admission_result"]["no_best_operator"] is True
    assert set(admission["scope"]["operators"]) == {
        "H1_SYMMETRIC_DELTA_BLEND",
        "H2_RANDOM_DELTA_CROSSOVER",
    }
    assert admission["scope"]["controls"] == ["H0_NULL", "H0_RESET_ZERO"]
    assert admission["dependency"]["blocks_M2"] is False
    assert admission["dependency"]["M2_genome_mode"] == "NULL_GENOME"
    assert admission["scope"]["h2_mask_granularity"] == "MODULE"
    assert {"benchmark_score", "fitness", "reproduction_rate"} <= set(
        admission["forbidden_selection_inputs"]
    )
    tests = {case["id"]: case for case in admission["tests"]}
    assert "ZERO_ADAPTER" in tests["N0-CONTRACT-005"]["pass"]
    assert "behaviorally equivalent" in tests["N0-PEFT-007"]["requirement"]


def test_founder_admission_has_zero_tolerance_critical_core(
    repository_root: Path,
) -> None:
    admission = load_json_yaml(
        repository_root, "specs/experiments/founder-model-admission.yaml"
    )
    assert admission["C0"] == {
        "role": "PRE_SCREEN",
        "corpus_id": "FOUNDER_C0_V2",
        "corpus_spec": "specs/experiments/founder-c0-v2.yaml",
        "probe_count": 10,
        "factual_correct_minimum": 9,
        "reference_structure_valid_required": 10,
        "malformed_maximum": 0,
        "critical_core_accuracy_required": 1.0,
        "critical_core_error_policy": "FAIL_REGARDLESS_OF_AGGREGATE",
    }
    assert admission["C20"]["overall_factual_accuracy_minimum"] == "0.90"
    assert admission["C20"]["critical_core_accuracy_required"] == "1.00"
    assert admission["C20"]["critical_failure_policy"].startswith("ANY_CRITICAL_CORE_ERROR")
    assert set(admission["C20"]["critical_core_probe_tags"]) == {
        "SELF_IDENTITY",
        "PEER_IDENTITY_REFERENCE",
        "TARGET_REFERENCE",
        "INCOMING_PROPOSAL_OWNERSHIP",
        "OUTGOING_PROPOSAL_OWNERSHIP",
        "PROPOSAL_DIRECTION",
        "PROPOSAL_TARGET",
        "REPRODUCTION_PROPOSAL_HANDLE_GROUNDING",
    }
    assert admission["non_prescriptive_grounding"] == [
        "MESSAGE_RECEIVED_DOES_NOT_IMPLY_SEND",
        "PROPOSAL_RECEIVED_DOES_NOT_IMPLY_ACCEPT_OR_REJECT",
    ]
    assert admission["post_freeze_dependencies"]["M2"]["requires_N0"] is False


def test_n0_birth_sequence_puts_verified_cas_before_atomic_commit(
    repository_root: Path,
) -> None:
    sequence = (
        repository_root / "architecture/views/SEQ-351-genome-artifact-commit.md"
    ).read_text(encoding="utf-8")
    assert sequence.index("save canonical child bytes") < sequence.index("P11 atomically")
    assert "committed non-sentinel child referencing missing" in sequence


def test_n0_external_dependency_decisions_are_bounded(repository_root: Path) -> None:
    decision = (
        repository_root
        / "architecture/decisions/ADR-350-003-external-genetics-dependencies.md"
    ).read_text(encoding="utf-8")
    for value in (
        "`ADOPT`",
        "`ADAPT_PRIMITIVES_ONLY`",
        "`OPTIONAL`",
        "`ADAPT_DESIGN_ONLY`",
        "`REFERENCE_ONLY`",
    ):
        assert value in decision
    assert "GENOME is not used as an evolution engine" in decision
    assert "never core runtime authority" in decision
