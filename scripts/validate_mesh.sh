#!/usr/bin/env bash
# Validate that the mesh can be regenerated and passes checkMesh.
# Usage: ./scripts/validate_mesh.sh [phi|baseline]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE="${1:-phi}"

case "$CASE" in
  phi|PHI|RDE_PHI_2D)
    CASEDIR="$ROOT/cases/RDE_PHI_2D"
    ;;
  baseline|BASE|RDE_baseline)
    CASEDIR="$ROOT/cases/RDE_baseline"
    ;;
  *)
    echo "Unknown case: $CASE"
    exit 1
    ;;
esac

cd "$CASEDIR"
echo "=== Validating mesh in $CASEDIR ==="

if [[ -f system/blockMeshDict ]]; then
  echo "--- regenerating with blockMesh ---"
  # keep a backup of existing polyMesh if present
  if [[ -d constant/polyMesh ]]; then
    mv constant/polyMesh "constant/polyMesh.bak.$(date +%s)" 2>/dev/null || true
  fi
  blockMesh | tee log.blockMesh.validate
else
  echo "No blockMeshDict found — using existing polyMesh only"
fi

checkMesh | tee log.checkMesh.validate

echo ""
echo "Mesh validation finished. Inspect log.checkMesh.validate for details."
