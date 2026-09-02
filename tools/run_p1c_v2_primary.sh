#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: bash tools/run_p1c_v2_primary.sh <expected-git-commit>" >&2
  exit 2
fi

EXPECTED_COMMIT="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE=/workspace
EVIDENCE_ROOT="$WORKSPACE/alifelm/evidence"
VENV_PYTHON="$WORKSPACE/world-p1-canonical-venv/bin/python"
OUTPUT_ROOT="$EVIDENCE_ROOT/WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1_PRIMARY"
STDOUT_LOG="$WORKSPACE/WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1_PRIMARY.stdout.log"

cd "$REPO_ROOT"
ACTUAL_COMMIT="$(git rev-parse HEAD)"
if [[ "$ACTUAL_COMMIT" != "$EXPECTED_COMMIT" ]]; then
  echo "launcher commit mismatch: expected $EXPECTED_COMMIT got $ACTUAL_COMMIT" >&2
  exit 3
fi

if [[ -e "$OUTPUT_ROOT" ]]; then
  echo "primary output root already exists: $OUTPUT_ROOT" >&2
  exit 4
fi

set -o pipefail
PYTHONPATH=src "$VENV_PYTHON" tools/world_p1c_v2_common_topology_phase_ablation.py \
  --execute \
  --base-model-dir "$WORKSPACE/alifelm/models/OLMo-2-0425-1B-Instruct" \
  --adapter-path "$WORKSPACE/alifelm/artifacts/F0_FA_V1_FORMAL" \
  --p1c-v1-root "$EVIDENCE_ROOT/WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1_F2E9E4D" \
  --p1c-v1-stdout "$WORKSPACE/WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1_F2E9E4D.stdout.log" \
  --p1c-v1-archive "$WORKSPACE/WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1_F2E9E4D_CANONICAL.tar.gz" \
  --d1-root "$EVIDENCE_ROOT/WORLD_P1C_D1_EQUIVALENCE_LOCALIZATION_V1_6D09FBF_R2" \
  --d1-stdout "$WORKSPACE/WORLD_P1C_D1_EQUIVALENCE_LOCALIZATION_V1_6D09FBF_R2.stdout.log" \
  --d1-archive "$WORKSPACE/WORLD_P1C_D1_EQUIVALENCE_LOCALIZATION_V1_6D09FBF_R2_CANONICAL.tar.gz" \
  --output-root "$OUTPUT_ROOT" \
  --config docs/research/world/WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_CONFIG_V1.json \
  --expected-git-commit "$EXPECTED_COMMIT" \
  2>&1 | tee "$STDOUT_LOG"
