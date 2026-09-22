#!/usr/bin/env bash
# Convenience runner for the RDE cases in this repository.
# Usage:
#   ./scripts/run_case.sh              # runs RDE_PHI_2D (serial)
#   ./scripts/run_case.sh baseline     # runs RDE_baseline
#   ./scripts/run_case.sh phi parallel # runs RDE_PHI_2D in parallel

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE="${1:-phi}"
MODE="${2:-serial}"

case "$CASE" in
  phi|PHI|RDE_PHI_2D)
    CASEDIR="$ROOT/cases/RDE_PHI_2D"
    ;;
  baseline|BASE|RDE_baseline)
    CASEDIR="$ROOT/cases/RDE_baseline"
    ;;
  *)
    echo "Unknown case: $CASE (use 'phi' or 'baseline')"
    exit 1
    ;;
esac

cd "$CASEDIR"
echo "=== Working directory: $CASEDIR ==="

if [[ ! -f constant/polyMesh/points ]]; then
  echo "=== blockMesh (mesh missing) ==="
  blockMesh | tee log.blockMesh
fi

if [[ -f system/setFieldsDict ]]; then
  echo "=== setFields ==="
  setFields | tee log.setFields
fi

echo "=== checkMesh ==="
checkMesh | tee log.checkMesh

if [[ "$MODE" == "parallel" ]]; then
  if [[ -x ./Allrun_parallel ]]; then
    ./Allrun_parallel
  else
    echo "decomposePar + mpirun reactingFoam ..."
    decomposePar -force
    nProcs=$(foamDictionary -entry numberOfSubdomains -value system/decomposeParDict 2>/dev/null || echo 4)
    mpirun -np "$nProcs" reactingFoam -parallel | tee log.reactingFoam
  fi
else
  if [[ -x ./Allrun ]]; then
    ./Allrun
  else
    # baseline may use a different application name
    APP=$(foamDictionary -entry application -value system/controlDict 2>/dev/null || echo reactingFoam)
    $APP | tee "log.$APP"
  fi
fi

echo "=== Done ==="
