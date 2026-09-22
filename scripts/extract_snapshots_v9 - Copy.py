#!/usr/bin/env python3
"""
RDE Hybrid Dataset Generator v9 — SD Toolbox CJ Solver
=======================================================
Uses Caltech's Shock & Detonation Toolbox for accurate CJ speeds.
Replaces the broken approximate formula from v8.

Requirements:
    - Cantera 3.0.1+
    - SD Toolbox installed in conda env (see install guide)

Expected CJ speeds for H2-air:
    - phi=1.0, 1 atm, 300K: ~1960 m/s
    - phi=1.28, 0.95 atm, 287K: ~1850-1900 m/s  
    - phi=0.6, 1.7 atm, 312K: ~1700-1750 m/s
"""

import os
import re
import csv
import math
from pathlib import Path

try:
    import cantera as ct
    CANTERA_AVAILABLE = True
    print(f"Cantera {ct.__version__} loaded")
except ImportError:
    CANTERA_AVAILABLE = False
    print("WARNING: Cantera not found.")

# Try SD Toolbox first, fall back to CT-SD if available
try:
    from sdtoolbox.postshock import CJspeed
    SDT_AVAILABLE = True
    SDT_METHOD = "SDToolbox"
    print("SD Toolbox loaded")
except ImportError:
    try:
        from combustion_toolbox import CJspeed
        SDT_AVAILABLE = True
        SDT_METHOD = "CT-SD"
        print("Combustion Toolbox (CT-SD) loaded")
    except ImportError:
        SDT_AVAILABLE = False
        print("WARNING: No SD Toolbox found. CJ speeds will be skipped.")

ROOT = Path("C:/Users/User/Desktop/COMPLETED_PROJECTS/RDE_Reseacrh/CFD_Simulations")
CASES = [f"RDE_{i:02d}" for i in range(1, 13)]
FIELDS = ["p", "T", "H2", "O2", "H2O"]
MW = {"H2": 2.016, "O2": 32.00, "N2": 28.014, "H2O": 18.015}

# ============================================================
# FIELD READERS (same as v8)
# ============================================================

def read_scalar_field(case_dir, time_dir, field_name):
    field_file = case_dir / time_dir / field_name
    if not field_file.exists():
        return None
    with open(field_file, 'r') as f:
        content = f.read()
    match = re.search(r'internalField\s+(.*?);', content, re.DOTALL)
    if not match:
        return None
    field_content = match.group(1).strip()
    if field_content.startswith("uniform") and not field_content.startswith("uniform List"):
        val_str = field_content.replace("uniform", "").strip()
        try:
            return [float(val_str)]
        except ValueError:
            return None
    list_match = re.search(r'\((.*?)\)', field_content, re.DOTALL)
    if list_match:
        values_str = list_match.group(1)
        values = []
        for line in values_str.strip().splitlines():
            line = line.strip()
            if line:
                try:
                    values.append(float(line))
                except ValueError:
                    continue
        return values
    return None

def read_vector_magnitude(case_dir, time_dir, field_name):
    field_file = case_dir / time_dir / field_name
    if not field_file.exists():
        return None
    with open(field_file, 'r') as f:
        content = f.read()
    if not content or 'internalField' not in content:
        return None
    match = re.search(r'internalField\s+(.*?);', content, re.DOTALL)
    if not match:
        return None
    field_content = match.group(1).strip()
    if field_content.startswith("uniform") and not field_content.startswith("uniform List"):
        vec_str = field_content.replace("uniform", "").strip().strip("()").split()
        if len(vec_str) >= 3:
            try:
                mag = math.sqrt(sum(float(v)**2 for v in vec_str[:3]))
                return [mag]
            except ValueError:
                return None
        return None
    list_match = re.search(r'\((.*?)\)', field_content, re.DOTALL)
    if list_match:
        vectors_str = list_match.group(1)
        mags = []
        for line in vectors_str.strip().splitlines():
            line = line.strip().strip("()").split()
            if len(line) >= 3:
                try:
                    mag = math.sqrt(float(line[0])**2 + float(line[1])**2 + float(line[2])**2)
                    mags.append(mag)
                except ValueError:
                    continue
        return mags if mags else None
    return None

def compute_stats(data):
    if not data:
        return None, None, None, None
    n = len(data)
    avg = sum(data) / n
    mx = max(data)
    mn = min(data)
    if n > 1:
        variance = sum((x - avg)**2 for x in data) / (n - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0
    return avg, mx, mn, std

# ============================================================
# CASE PARAMETER EXTRACTION (same as v8 — mass fraction → mole fraction)
# ============================================================

def get_case_params(case_dir):
    sfd = case_dir / "system" / "setFieldsDict"
    params = {}
    if not sfd.exists():
        return params

    text = sfd.read_text()

    for field in ["T", "p", "H2", "O2", "H2O", "N2"]:
        pattern = r'volScalarFieldValue\s+' + field + r'\s+([0-9.eE+-]+)'
        matches = re.findall(pattern, text)
        if matches:
            params[field + "_default"] = float(matches[0])
            if len(matches) >= 2:
                params[field + "_ign"] = float(matches[1])

    Y = {
        "H2": params.get("H2_default", 0),
        "O2": params.get("O2_default", 0),
        "N2": params.get("N2_default", 0),
        "H2O": params.get("H2O_default", 0)
    }

    Y_total = sum(Y.values())
    if Y_total > 0:
        for k in Y:
            Y[k] /= Y_total

    moles = {k: Y[k] / MW[k] for k in Y if Y[k] > 0}
    total_moles = sum(moles.values())

    if total_moles > 0:
        X = {k: moles[k] / total_moles for k in moles}
        params["X_H2"] = X.get("H2", 0)
        params["X_O2"] = X.get("O2", 0)
        params["X_N2"] = X.get("N2", 0)
        params["X_H2O"] = X.get("H2O", 0)

        if X.get("O2", 0) > 0:
            phi = (X["H2"] / X["O2"]) / 2.0
            params["phi"] = phi
        else:
            params["phi"] = 0.0
    else:
        params["phi"] = 0.0

    params["Y_H2"] = Y.get("H2", 0)
    params["Y_O2"] = Y.get("O2", 0)
    params["Y_N2"] = Y.get("N2", 0)

    return params

# ============================================================
# SD TOOLBOX CJ SOLVER
# ============================================================

def run_cantera_sdt(phi, p0_pa, T0_k, Y_H2, Y_O2, Y_N2):
    """
    Compute CJ detonation speed using SD Toolbox.
    Returns dict with CJ speed, post-shock T, P, rho.
    """
    if not SDT_AVAILABLE:
        return {"cantera_success": False, "cantera_error": "SD Toolbox not available"}

    try:
        # Convert mass fractions to mole fractions for Cantera
        moles = {
            "H2": Y_H2 / MW["H2"],
            "O2": Y_O2 / MW["O2"],
            "N2": Y_N2 / MW["N2"]
        }
        total = sum(moles.values())
        X_H2 = moles["H2"] / total
        X_O2 = moles["O2"] / total
        X_N2 = moles["N2"] / total

        X_str = f'H2:{X_H2:.6f},O2:{X_O2:.6f},N2:{X_N2:.6f}'

        # Call SD Toolbox CJspeed
        # Signature: CJspeed(P1, T1, q, mech, fullOutput=False)
        cj_speed = CJspeed(p0_pa, T0_k, X_str, 'gri30.yaml')

        # Get post-shock state for T, P, rho
        gas = ct.Solution('gri30.yaml')
        gas.TPX = T0_k, p0_pa, X_str

        # Approximate post-CJ state using strong shock relations
        # For accurate post-shock state, use SDToolbox's postshock functions
        # Here we use Cantera equilibrium at approximate CJ conditions
        a1 = gas.sound_speed
        gamma = gas.cp / gas.cv
        M_cj = cj_speed / a1

        # Approximate post-shock T and P
        T_cj = T0_k * (2 * gamma * M_cj**2 - (gamma - 1)) * \
               ((gamma - 1) * M_cj**2 + 2) / ((gamma + 1)**2 * M_cj**2)
        P_cj = p0_pa * (2 * gamma * M_cj**2 - (gamma - 1)) / (gamma + 1)

        # Equilibrate at post-shock state
        gas.TP = max(T_cj, 500), P_cj
        try:
            gas.equilibrate('TP')
            T_eq = gas.T
            P_eq = gas.P
            rho_eq = gas.density
        except:
            T_eq = T_cj
            P_eq = P_cj
            rho_eq = gas.density

        return {
            "cantera_cj_speed_ms": float(cj_speed),
            "cantera_cj_t_k": float(T_eq),
            "cantera_cj_p_pa": float(P_eq),
            "cantera_cj_rho": float(rho_eq),
            "cantera_M_cj": float(M_cj),
            "cantera_success": True,
            "cantera_method": SDT_METHOD
        }

    except Exception as e:
        return {
            "cantera_success": False,
            "cantera_error": str(e),
            "cantera_method": SDT_METHOD if SDT_AVAILABLE else "none"
        }

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("RDE HYBRID DATASET GENERATOR v9 — SD Toolbox CJ Solver")
    print(f"Reading from: {ROOT}")
    print(f"SD Toolbox: {SDT_METHOD if SDT_AVAILABLE else 'NOT AVAILABLE'}")
    print("=" * 60)

    rows = []

    for case_name in CASES:
        print(f"\nProcessing {case_name}...")
        case_dir = ROOT / case_name
        if not case_dir.exists():
            print(f"  WARNING: {case_dir} not found, skipping")
            continue

        params = get_case_params(case_dir)
        phi = params.get("phi", 0)
        p0 = params.get("p_default", 101325)
        T0 = params.get("T_default", 300)
        Y_H2 = params.get("Y_H2", 0)
        Y_O2 = params.get("Y_O2", 0)
        Y_N2 = params.get("Y_N2", 0)

        print(f"  phi={phi:.3f}, p0={p0:.0f} Pa, T0={T0:.0f} K")

        cantera_results = run_cantera_sdt(phi, p0, T0, Y_H2, Y_O2, Y_N2)
        if cantera_results.get("cantera_success"):
            print(f"  {SDT_METHOD} CJ speed: {cantera_results['cantera_cj_speed_ms']:.1f} m/s (M={cantera_results['cantera_M_cj']:.2f})")
        else:
            print(f"  {SDT_METHOD} FAILED: {cantera_results.get('cantera_error', 'unknown')}")

        time_dirs = sorted([
            d.name for d in case_dir.iterdir() 
            if d.is_dir() 
            and d.name not in ["0", "constant", "system", "postProcessing"]
            and not d.name.startswith("processor")
            and not d.name.startswith(".")
        ], key=lambda x: float(x))

        print(f"  Found {len(time_dirs)} time folders")

        for time_dir in time_dirs:
            time_path = case_dir / time_dir
            if not time_path.exists():
                continue

            row = {
                "case": case_name, 
                "time": float(time_dir),
                "phi": phi,
                "p0_pa": p0,
                "T0_k": T0
            }
            row.update(params)
            row.update(cantera_results)

            for field in FIELDS:
                data = read_scalar_field(case_dir, time_dir, field)
                if data:
                    avg, mx, mn, std = compute_stats(data)
                    row[field + "_mean"] = avg
                    row[field + "_max"] = mx
                    row[field + "_min"] = mn
                    row[field + "_std"] = std
                    row[field + "_n"] = len(data)

            u_data = read_vector_magnitude(case_dir, time_dir, "U")
            if u_data:
                avg, mx, mn, std = compute_stats(u_data)
                row["U_mag_mean"] = avg
                row["U_mag_max"] = mx
                row["U_mag_min"] = mn
                row["U_mag_std"] = std
                row["U_mag_n"] = len(u_data)

            rows.append(row)

        case_snaps = len([r for r in rows if r['case'] == case_name])
        print(f"  Total snapshots: {case_snaps}")

    if not rows:
        print("ERROR: No snapshots found!")
        return

    all_columns = list(rows[0].keys())
    output_csv = ROOT / "RDE_hybrid_dataset_v9.csv"
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*60}")
    print(f"Saved {len(rows)} snapshots to: {output_csv}")
    print(f"Columns: {len(all_columns)}")
    print(f"Cases: {len(CASES)}")
    if SDT_AVAILABLE:
        success_count = sum(1 for r in rows if r.get("cantera_success"))
        print(f"SD Toolbox validated: {success_count}/{len(rows)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
