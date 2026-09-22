# Data & external archives

This folder holds **metadata and pointers only**.  
Large CFD time directories and the processed ML dataset live outside Git.

## Public dataset

- **RDE-72** (12 real OpenFOAM cases + 60 CVAE synthetic cases)  
  https://huggingface.co/datasets/SM-Bello/rde-72-dataset

  - Spatial resolution: 150 × 300  
  - Channels: p, T, Ux, Uy, H2, O2  
  - Format: `.npz`

## Recommended external storage for raw CFD output

If you archive selected time directories from `RDE_PHI_2D` (or new runs), place them on:

- Zenodo (DOI recommended)
- Hugging Face (as a second dataset or supplementary files)
- Institutional storage with a permanent URL

Then record the DOI / URL here and in the main README so the provenance chain remains complete:

```
paper / this repo → CFD case → raw fields (Zenodo) → processed RDE-72 (Hugging Face)
```

## Local development note

When you run the cases yourself, time directories will appear under `cases/RDE_PHI_2D/`.  
Add them to `.gitignore` (already provided at repository root) so they are never committed by accident.
