# save as fix_conditions.py and run:  python fix_conditions.py
import numpy as np
import pandas as pd

d = np.load("rde_full_dataset_72cases.npz")
fields = d["fields"]
is_synth = d["is_synthetic"]

# synthetic conditions already good (from generation)
synth = np.load("output_real/synthetic_dataset.npz")
synth_cond = synth["conditions"]   # (60, 4)

# real conditions from CSV — same order the Dataset class used
df = pd.read_csv("RDE_hybrid_dataset_v9.csv")
# expect columns that match the training script:
# case, phi, p0_pa, T0_k, cantera_cj_speed_ms  (or similar)
print("CSV columns:", list(df.columns))

case_col = next(c for c in ["case", "case_id", "Case"] if c in df.columns)
param_map = {}
for std, cands in {
    "phi": ["phi"],
    "p0":  ["p0_pa", "p0"],
    "T0":  ["T0_k", "T0"],
    "cj":  ["cantera_cj_speed_ms", "cj_speed_ms", "D_CJ", "cj"],
}.items():
    for c in cands:
        if c in df.columns:
            param_map[std] = c
            break
print("param_map:", param_map)

real_cond = []
for case_name in sorted(df[case_col].unique())[:12]:
    row = df[df[case_col] == case_name].iloc[0]
    real_cond.append([
        float(row[param_map["phi"]]),
        float(row[param_map["p0"]]),
        float(row[param_map["T0"]]),
        float(row[param_map["cj"]]),
    ])
real_cond = np.array(real_cond, dtype=np.float32)
print("real conditions shape", real_cond.shape)
print(real_cond)

conditions = np.concatenate([real_cond, synth_cond], axis=0).astype(np.float32)
assert conditions.shape == (72, 4)

np.savez_compressed(
    "rde_full_dataset_72cases.npz",
    fields=fields.astype(np.float32),
    conditions=conditions,
    real_count=12,
    synthetic_count=60,
    is_synthetic=is_synth,
)
print("Updated rde_full_dataset_72cases.npz with real conditions.")
print("conditions sample (real[0], synth[0]):", conditions[0], conditions[12])