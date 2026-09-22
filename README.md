# Rotating Detonation Engine — Reproducible OpenFOAM Cases

Open, executable 2-D Rotating Detonation Engine (RDE) cases used to generate the [RDE-72 spatiotemporal dataset](https://huggingface.co/datasets/SM-Bello/rde-72-dataset).

This repository supplies the **upstream computational recipe** (mesh, chemistry, ignition, numerics, and run scripts) so that the community can reproduce, audit, or extend the original CFD work.

```
geometry → mesh → chemistry → mixture → ignition → reactingFoam → probes → dataset
```

## Repository layout

```
Rotating-Detonating-Engine/
├── README.md
├── LICENSE
├── docs/
│   ├── PROVENANCE.md      # full chain recovered from the research workspace
│   └── MESH.md            # geometry, blockMeshDict, boundary rationale
├── cases/
│   ├── RDE_PHI_2D/        # ★ primary 300×150 production case
│   └── RDE_baseline/      # smaller 100×50 precursor used during development
├── scripts/
│   ├── run_case.sh
│   ├── extract_fields.py
│   └── validate_mesh.sh
└── data/                  # metadata + links to large result archives
```

## Quick start (RDE_PHI_2D)

**Requirements**

- OpenFOAM (v2406 or compatible; `reactingFoam` must be available)
- A working `blockMesh`, `setFields`, `checkMesh`

```bash
cd cases/RDE_PHI_2D

# Optional: regenerate mesh from dictionary (recommended for audit)
blockMesh
checkMesh

# Apply ignition + premixed composition
setFields

# Run (serial)
./Allrun
# or simply:
reactingFoam | tee log.reactingFoam
```

Parallel:

```bash
./Allrun_parallel          # uses system/decomposeParDict
```

Open in ParaView:

```bash
paraFoam -case .
```

## What the production case contains

| Item                | Value / description                                      |
|---------------------|----------------------------------------------------------|
| Domain              | 0.30 m × 0.15 m × 0.001 m                               |
| Mesh                | 300 × 150 × 1 = 45 000 structured cells                 |
| Solver              | `reactingFoam`                                           |
| Chemistry           | 1-step irreversible Arrhenius H₂ + ½O₂ → H₂O            |
| Mixture             | Premixed H₂/air (Y_H2 ≈ 0.02834)                        |
| Ignition            | High-T / high-p box via `setFieldsDict`                 |
| Bottom BC           | wall (no continuous injection)                           |
| Azimuthal BCs       | cyclic                                                   |
| Time control        | Δt₀ = 1e-8 s, maxCo = 0.4, maxΔt = 5e-7 s              |

Full details: [docs/PROVENANCE.md](docs/PROVENANCE.md) and [docs/MESH.md](docs/MESH.md).

## RDE_baseline

A smaller development case (5 000 cells) that was used to validate chemistry, boundary-condition syntax, and numerical settings before scaling to the 45 k-cell production mesh.  
It is retained so the evolution of the setup remains visible.

## Large result data

Time-resolved field directories and the processed RDE-72 `.npz` archive are **not** stored in Git (they exceed practical repository size).  

See `data/README.md` for links to:

- Hugging Face dataset (RDE-72)
- Optional Zenodo / local archives of selected time directories

## Scripts

| Script              | Purpose                                      |
|---------------------|----------------------------------------------|
| `scripts/run_case.sh`     | Convenience wrapper for either case    |
| `scripts/validate_mesh.sh`| blockMesh + checkMesh sanity check     |
| `scripts/extract_fields.py` | Example extractor for p, T, species  |

## Citation

If you use these cases or the derived dataset, please cite:

```bibtex
@dataset{rde72_2026,
  author    = {Bello, S. M.},
  year      = {2026},
  title     = {RDE-72: Spatiotemporal Dataset for Rotating Detonation Engine CFD},
  publisher = {HuggingFace},
  url       = {https://huggingface.co/datasets/SM-Bello/rde-72-dataset}
}
```

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Pull requests that improve documentation, add validation studies (mesh sensitivity, CJ velocity, conservation checks), or extend the chemistry/mechanism are welcome.  
Please keep generated time directories and large binary results out of Git; link them from `data/` instead.
