# Mesh Provenance — RDE_PHI_2D

## Geometry

| Quantity              | Value                          |
|-----------------------|--------------------------------|
| Domain (x × y × z)    | 0.30 m × 0.15 m × 0.001 m     |
| Cells (nx × ny × nz)  | 300 × 150 × 1 = **45 000**    |
| Cell type             | Structured hexahedra           |
| Grading               | Uniform (1 1 1)                |
| Cell size (approx.)   | Δx = 1 mm, Δy = 1 mm, Δz = 1 mm |

The mesh is generated entirely by OpenFOAM’s `blockMesh` from the dictionary:

```
cases/RDE_PHI_2D/system/blockMeshDict
```

No external CAD, snappyHexMesh, or third-party mesh generator is required.

## Boundary patches

| Patch            | Type     | Role                                      |
|------------------|----------|-------------------------------------------|
| `inlet`          | wall     | Bottom boundary (no continuous injection) |
| `outlet`         | patch    | Top (axial) boundary                      |
| `periodic_left`  | cyclic   | Azimuthal periodicity (left)              |
| `periodic_right` | cyclic   | Azimuthal periodicity (right)             |
| `front` / `back` | empty    | 2-D empty planes                          |

This configuration represents an **unwrapped (planarized) annular RDE**.  
The cyclic pair closes the azimuthal direction; the 1 mm extrusion and `empty` fronts enforce a strictly two-dimensional solution.

## Why these dimensions?

The values present in the original workspace are:

- Axial height 0.15 m  
- Unwrapped circumference 0.30 m  
- Unit depth 0.001 m  

They produce a 300 × 150 grid that matches the spatial resolution of the public RDE-72 dataset (150 × 300 cells when fields are stored row-major).  

Exact physical mapping to a particular experimental annulus (mean radius, channel height, etc.) is not documented inside the case files and is therefore left as open provenance for the community.

## Regenerating the mesh

```bash
cd cases/RDE_PHI_2D
blockMesh
checkMesh
```

The supplied `constant/polyMesh/` already contains a valid mesh so the case can be run immediately.  
Committing the mesh makes the repository self-contained; regenerating from `blockMeshDict` guarantees bit-for-bit reproducibility on any OpenFOAM installation that supports the same dictionary syntax.

## Precursor mesh (RDE_baseline)

An earlier, smaller mesh was used during development:

| Quantity              | Value                       |
|-----------------------|-----------------------------|
| Domain                | 0.10 m × 0.05 m × 0.001 m  |
| Cells                 | 100 × 50 × 1 = 5 000       |

Logs (`log.blockMesh`, `log.checkMesh`) are preserved inside `cases/RDE_baseline/` so the evolution of the mesh can be audited.
