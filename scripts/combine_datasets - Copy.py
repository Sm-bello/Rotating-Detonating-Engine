"""
combine_datasets.py
Build the 72-case dataset from the 12 real cases + 60 CVAE synthetics.
Matches the paths produced by the current training/generation run.
"""

import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (edit only if your filenames differ)
# ---------------------------------------------------------------------------
REAL_NPZ   = Path("spatial_fields_fixed.npz")          # 12 real cases
SYNTH_NPZ  = Path("output_real/synthetic_dataset.npz") # 60 synthetic cases
OUT_NPZ    = Path("rde_full_dataset_72cases.npz")

# ---------------------------------------------------------------------------
# Load & validate
# ---------------------------------------------------------------------------
assert REAL_NPZ.exists(),  f"Missing real data: {REAL_NPZ}"
assert SYNTH_NPZ.exists(), f"Missing synthetic data: {SYNTH_NPZ}"

real  = np.load(REAL_NPZ)
synth = np.load(SYNTH_NPZ)

real_fields  = real["fields"]          # expected (12, 20, 6, 150, 300)
synth_fields = synth["fields"]         # expected (60, 20, 6, 150, 300)

print("Real fields:     ", real_fields.shape,  "std =", float(real_fields.std()))
print("Synthetic fields:", synth_fields.shape, "std =", float(synth_fields.std()))

# Basic sanity checks
assert real_fields.ndim == 5 and real_fields.shape[0] == 12,  "Real data shape unexpected"
assert synth_fields.ndim == 5 and synth_fields.shape[0] == 60, "Synthetic data shape unexpected"
assert real_fields.shape[1:] == synth_fields.shape[1:], \
    f"Shape mismatch after case axis: real {real_fields.shape[1:]} vs synth {synth_fields.shape[1:]}"
assert real_fields.std()  > 1e-6, "Real fields appear to be all zeros — check extractor"
assert synth_fields.std() > 1e-6, "Synthetic fields appear to be all zeros — check generation"

# ---------------------------------------------------------------------------
# Optional: also keep conditions / times if present
# ---------------------------------------------------------------------------
save_dict = {
    "fields":        np.concatenate([real_fields, synth_fields], axis=0).astype(np.float32),
    "real_count":    12,
    "synthetic_count": 60,
    "is_synthetic":  np.array([False] * 12 + [True] * 60),
}

# times (real only, or tile if useful)
if "times" in real:
    # keep real times; synthetics can reuse the same time vector
    save_dict["times"] = real["times"]          # (12, 20) or (20,)
    if real["times"].ndim == 1:
        save_dict["times"] = np.tile(real["times"][None, :], (72, 1))
    elif real["times"].shape[0] == 12:
        # pad synthetic times with the first real time vector
        t0 = real["times"][0:1]
        save_dict["times"] = np.concatenate([real["times"], np.tile(t0, (60, 1))], axis=0)

# conditions (prefer synthetic file; rebuild real side if needed)
if "conditions" in synth:
    synth_cond = synth["conditions"]            # (60, 4)
    if "conditions" in real:
        real_cond = real["conditions"]
    else:
        # placeholder zeros — replace later from CSV if you need them
        real_cond = np.zeros((12, 4), dtype=np.float32)
        print("WARNING: real conditions not in NPZ — stored as zeros. "
              "Re-inject from RDE_hybrid_dataset_v9.csv if required.")
    save_dict["conditions"] = np.concatenate([real_cond, synth_cond], axis=0).astype(np.float32)

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
np.savez_compressed(OUT_NPZ, **save_dict)

mb = save_dict["fields"].nbytes / (1024 ** 2)
print(f"\n✓ Combined dataset written → {OUT_NPZ}")
print(f"  Real:      12")
print(f"  Synthetic: 60")
print(f"  Total:     72")
print(f"  Shape:     {save_dict['fields'].shape}")
print(f"  Size:      {mb:.1f} MB (uncompressed); file on disk will be smaller")
print(f"  Field std: {float(save_dict['fields'].std()):.4g}")