# Provenance Chain

This document records exactly what was recovered from the original research workspace.  
No rationale that is absent from the files has been invented.

## High-level chain

```
MESH GENERATION (blockMesh)
      ↓
GEOMETRY / DOMAIN (0.30 × 0.15 × 0.001 m)
      ↓
BOUNDARY PATCHES (wall bottom, cyclic sides, empty fronts)
      ↓
CHEMISTRY (1-step H₂–O₂ Arrhenius)
      ↓
INITIAL MIXTURE (premixed H₂/air mass fractions)
      ↓
IGNITION METHOD (setFields hot/high-pressure box)
      ↓
NUMERICAL SCHEMES (reactingFoam, adaptive Δt, maxCo = 0.4)
      ↓
RAW CFD FIELDS (time directories)
      ↓
POST-PROCESSING (azimuthal probes, fieldMinMax, Qdot)
      ↓
RDE-72 / ML DATASET
```

## 1. Mesh

See [MESH.md](MESH.md).

- Generator: OpenFOAM `blockMesh`
- Source dictionary: `cases/RDE_PHI_2D/system/blockMeshDict`
- Resulting mesh is stored in `cases/RDE_PHI_2D/constant/polyMesh/`

## 2. Chemistry

**Mechanism** (1-step global):

```
H2 + 0.5 O2 → H2O
```

- Type: irreversible Arrhenius  
- A = 9.87 × 10⁸  
- β = 0  
- Ta = 8052 K  

Files:

- `constant/reactions`
- `constant/chemistryProperties` (ODE solver = seulex)
- `constant/thermo.compressibleGas` (species: H2, O2, H2O, N2)
- `constant/thermophysicalProperties` (hePsiThermo, reactingMixture)

The same single-step form appears (with slightly different coefficients) in the earlier `RDE_baseline` case.

## 3. Initial mixture (streams)

Premixed composition written by `setFieldsDict`:

| Species | Mass fraction |
|---------|---------------|
| H2      | 0.02834       |
| O2      | 0.22650       |
| H2O     | 0.00000       |
| N2      | 0.74516       |

These values correspond to approximately stoichiometric H₂/air.  
No continuous mass-flow inlet is present on the bottom boundary of the production case; the mixture is established as the initial field.

## 4. Ignition

`system/setFieldsDict` creates a rectangular high-energy region:

```
box (0.040 0.000 0.000) (0.080 0.025 0.001)
T = 2000 K
p = 506625 Pa (≈ 5 atm)
partially reacted composition (H2 and O2 halved, H2O added)
```

This is the only ignition method present in the production case files.

## 5. Boundary conditions (production case)

| Patch            | Type     | Notes                                      |
|------------------|----------|--------------------------------------------|
| inlet (bottom)   | wall     | No continuous fresh-mixture injection      |
| outlet (top)     | patch    | Axial outflow                              |
| periodic_left/right | cyclic | Closes the azimuthal direction           |
| front / back     | empty    | Strictly 2-D                               |

Contrast with the earlier baseline, which used a velocity inlet (150 m/s) on the bottom.

## 6. Numerics

From `system/controlDict` (PHI_2D):

- Application: `reactingFoam`
- `deltaT` = 1 × 10⁻⁸ s
- `adjustTimeStep` = yes
- `maxCo` = 0.4
- `maxDeltaT` = 5 × 10⁻⁷ s
- `endTime` = 0.001 s
- Write interval = 5 × 10⁻⁵ s

Function objects:

- `fieldMinMax` on p and T
- `azimuthalProbes` (9 locations at mid-height)
- `Qdot`

## 7. Solver / version notes

- PHI_2D dictionaries carry OpenFOAM v2406-style headers and use `reactingFoam`.
- Baseline dictionaries carry OpenFOAM 11 headers and use `multicomponentFluid` / related thermo packages.
- Both cases are retained so the community can see the evolution of the numerical setup.

## 8. Downstream products

The public RDE-72 dataset (12 real OpenFOAM cases + 60 CVAE synthetic cases) was generated from fields of the same 150 × 300 resolution.  
Links and metadata live under `data/`.

## What is deliberately not claimed

- Exact experimental annulus radius or channel height that motivated 0.30 m × 0.15 m  
- Source of the particular Arrhenius coefficients beyond the files themselves  
- Mesh-convergence or CJ-velocity validation studies (not present in the supplied archives)

Any of the above that the community recovers or improves should be documented by pull request.
