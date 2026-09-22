import sys
import os
import pandas as pd
import numpy as np

def parse_openfoam_probe(path):
    data = []
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip(): continue
            parts = line.strip().replace('(','').replace(')','').split()
            data.append([float(x) for x in parts])
    return np.array(data)

def compute_label(time, p_data, t_data, base_label):
    # Dynamic runtime labeling engine based on localized structural gradients
    if time < 0.0005: 
        return "IGNITION_TRANSIENT"
    
    # Assess pressure variances across baseline channel array (probes 0-23)
    p_std = np.std(p_data[:, 1:25], axis=1[-1]) if len(p_data) > 0 else 0
    p_mean = np.mean(p_data[:, 1:25]) if len(p_data) > 0 else 101325.0
    
    # Evaluate global thermodynamic quench boundaries
    if p_mean < 120000.0:
        return "LEAN_QUENCH" if "LEAN" in base_label else "RICH_QUENCH"
    
    # Mode transition tracking through standard deviation thresholds
    if p_std > 800000.0: 
        return "MODE_TRANSITION"
    
    return base_label

if __name__ == "__main__":
    gid, label, params, phi, vel, seed, out_csv = sys.argv[1:8]
    
    p_path = "postProcessing/rdeTelemetryProbes/0/p"
    t_path = "postProcessing/rdeTelemetryProbes/0/T"
    
    if not (os.path.exists(p_path) and os.path.exists(t_path)):
        sys.exit(0)
        
    p_arr = parse_openfoam_probe(p_path)
    t_arr = parse_openfoam_probe(t_path)
    
    # Align structural rows across files
    min_rows = min(len(p_arr), len(t_arr))
    
    with open(out_csv, 'a') as out:
        for i in range(min_rows):
            t_val = p_arr[i, 0]
            p_str = ",".join(f"{x:.2f}" for x in p_arr[i, 1:])
            t_str = ",".join(f"{x:.2f}" for x in t_arr[i, 1:])
            
            # Apply continuous window evaluation logic
            derived_label = compute_label(t_val, p_arr[:i+1, :], t_arr[:i+1, :], label)
            
            out.write(f"{t_val:.7f},{p_str},{t_str},{phi},{vel},{gid},{derived_label},{params},{seed}\n")
