#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-validate}"
REPO="/workspace/world-simulator-formal"
PY="/workspace/world-p1-canonical-venv/bin/python"
BASE="/workspace/alifelm/models/OLMo-2-0425-1B-Instruct"
ADAPTER="/workspace/alifelm/artifacts/F0_FA_V1_FORMAL"
P1C_ROOT="/workspace/alifelm/evidence/WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1_PRIMARY"
P1C_STDOUT="/workspace/WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1_PRIMARY.stdout.log"
P1C_ARCHIVE="/workspace/WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1_4FCBF48_CANONICAL.tar.gz"
CONFIG="$REPO/docs/research/world/WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_CONFIG_V1.json"
OUT_REL="alifelm/evidence/WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1_PRIMARY"
OUT="/workspace/$OUT_REL"
STDOUT="/workspace/WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1_PRIMARY.stdout.log"

cd "$REPO"
HEAD="$(git rev-parse HEAD)"
test -z "$(git status --porcelain --untracked-files=all)"

COMMON=(
  --base-model-dir "$BASE"
  --adapter-path "$ADAPTER"
  --p1c-v2-root "$P1C_ROOT"
  --p1c-v2-stdout "$P1C_STDOUT"
  --p1c-v2-archive "$P1C_ARCHIVE"
  --output-root "$OUT"
  --config "$CONFIG"
  --expected-git-commit "$HEAD"
)

if [[ "$MODE" == "validate" ]]; then
  exec "$PY" tools/world_p2_hardened_entry.py --validate-only "${COMMON[@]}"
fi

if [[ "$MODE" != "execute" ]]; then
  echo "usage: $0 [validate|execute]" >&2
  exit 2
fi

SHORT="$(printf '%s' "$HEAD" | cut -c1-7 | tr '[:lower:]' '[:upper:]')"
ARCHIVE="/workspace/WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1_${SHORT}_CANONICAL.tar.gz"
test ! -e "$OUT"
test ! -e "$STDOUT"
test ! -e "$ARCHIVE"

"$PY" tools/world_p2_hardened_entry.py --execute "${COMMON[@]}" 2>&1 | tee "$STDOUT"

test -f "$OUT/summary.json"
test -f "$OUT/details.json"
sha256sum "$OUT/summary.json" "$OUT/details.json" "$STDOUT" > "$OUT/preservation_manifest.sha256"
tar -czf "$ARCHIVE" -C /workspace "$OUT_REL" "$(basename "$STDOUT")"
gzip -t "$ARCHIVE"
tar -tzf "$ARCHIVE" >/dev/null
sha256sum "$ARCHIVE"
echo P2_CANONICAL_ARCHIVE_VERIFIED
