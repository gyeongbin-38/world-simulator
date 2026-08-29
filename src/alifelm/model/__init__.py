"""Bounded real-model adapter foundation.

The package is infrastructure-only.  Canonical state remains owned by the
simulation kernel and all model output remains a candidate until it passes the
existing Cognition Gateway.
"""

from .adapter import (
    ContextModelRuntimeAdapter,
    ModelRuntime,
    generation_request_for,
    parse_raw_generation,
)
from .audit import (
    ChatTemplateAudit,
    GenerationSemanticsAudit,
    RuntimeEnvironment,
    collect_runtime_environment,
    inspect_chat_template,
    inspect_generation_semantics,
)
from .action_diagnostics import (
    ACTION_SCORE_PREFIX,
    ACTION_SCORE_TREATMENT_ID,
    ACTION_SCORE_TREATMENT_VERSION,
    ActionLabelScore,
    ActionLabelScoreResult,
    action_label_score_bytes,
    rank_action_label_scores,
    score_action_labels,
)
from .evidence import (
    CognitionDryRunResult,
    CognitionEvidence,
    ModelOutputStatus,
    RealCognitionDryRunner,
    RejectedModelOutput,
    cognition_evidence_bytes,
    raw_generation_bytes,
)
from .generation import (
    GenerationPolicy,
    GenerationRequest,
    RawGenerationResult,
    StopHook,
    generation_identity,
)
from .profile import ModelProfile
from .r3_fixtures import R3ContextClass, compile_r3_fixture
from .transformers_backend import GenerationError, ModelLoadError, TransformersModelRuntime
from .treatments import (
    I0_STRICT_FREE_GENERATION,
    I1_NEUTRAL_CODEC_SCAFFOLD,
    I2_SYNTAX_CONSTRAINED_CODEC,
    I3_CONDITIONAL_TYPED_CODEC,
    I3_BRANCH_ORDERS,
    InterfaceMode,
    InterfaceTreatment,
    ResearchDiagnosticLabel,
    ResearchGenerationDiagnostic,
    action_codec_json_schema,
    build_transformers_constraint,
    diagnose_generation,
    forced_action_codec_json_schema,
    i3_branch_order_treatment,
    i3_forced_branch_treatment,
    typed_action_codec_json_schema,
)
from .typed_codec import (
    CodecValidityStatus,
    CommitValidityStatus,
    DomainValidityStatus,
    TypedCodecEvaluation,
    evaluate_typed_codec,
    typed_codec_evaluation_bytes,
)

__all__ = [
    "ContextModelRuntimeAdapter",
    "ChatTemplateAudit",
    "ACTION_SCORE_PREFIX",
    "ACTION_SCORE_TREATMENT_ID",
    "ACTION_SCORE_TREATMENT_VERSION",
    "ActionLabelScore",
    "ActionLabelScoreResult",
    "action_label_score_bytes",
    "rank_action_label_scores",
    "score_action_labels",
    "CognitionDryRunResult",
    "CognitionEvidence",
    "GenerationError",
    "GenerationPolicy",
    "GenerationSemanticsAudit",
    "GenerationRequest",
    "ModelLoadError",
    "ModelProfile",
    "R3ContextClass",
    "compile_r3_fixture",
    "ModelOutputStatus",
    "ModelRuntime",
    "RawGenerationResult",
    "RealCognitionDryRunner",
    "RejectedModelOutput",
    "RuntimeEnvironment",
    "StopHook",
    "TransformersModelRuntime",
    "I0_STRICT_FREE_GENERATION",
    "I1_NEUTRAL_CODEC_SCAFFOLD",
    "I2_SYNTAX_CONSTRAINED_CODEC",
    "I3_CONDITIONAL_TYPED_CODEC",
    "I3_BRANCH_ORDERS",
    "InterfaceMode",
    "InterfaceTreatment",
    "ResearchDiagnosticLabel",
    "ResearchGenerationDiagnostic",
    "action_codec_json_schema",
    "build_transformers_constraint",
    "diagnose_generation",
    "forced_action_codec_json_schema",
    "i3_branch_order_treatment",
    "i3_forced_branch_treatment",
    "typed_action_codec_json_schema",
    "CodecValidityStatus",
    "CommitValidityStatus",
    "DomainValidityStatus",
    "TypedCodecEvaluation",
    "evaluate_typed_codec",
    "typed_codec_evaluation_bytes",
    "generation_request_for",
    "generation_identity",
    "collect_runtime_environment",
    "inspect_chat_template",
    "inspect_generation_semantics",
    "cognition_evidence_bytes",
    "raw_generation_bytes",
    "parse_raw_generation",
]
