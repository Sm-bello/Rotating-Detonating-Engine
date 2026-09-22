#!/usr/bin/env python3
"""
RDE Cantera Validator + Parameter Sweep
Generates 72 cases using Cantera for fast thermo/chemistry validation.
Run in Windows Anaconda where Cantera is installed.
"""

import numpy as np
import pandas as pd
import cantera as ct
from pathlib import Path
import csv

# ============================================================
# CONFIG
# ============================================================
OUTPUT_DIR = Path("C:/Users/User/Desktop/COMPLETED_PROJECTS/RDE_Reseacrh/ML_Dataset")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Anchor parameters (from your 12 CFD cases)
ANCHORS = [
    {"case": "RDE_01", "phi": 1.28, "p0": 95757, "T0": 287, "T_ign": 1597, "p_ign": 869104},
    {"case": "RDE_02", "phi": 1.24, "p0": 192652, "T0": 397, "T_ign": 1668, "p_ign": 622140},
    {"case": "RDE_03", "phi": 0.60, "p0": 171667, "T0": 312, "T_ign": 1952, "p_ign": 952472},
    {"case": "RDE_04", "phi": 1.18, "p0": 137430, "T0": 361, "T_ign": 1533, "p_ign": 472364},
    {"case": "RDE_05", "phi": 1.00, "p0": 125495, "T0": 332, "T_ign": 2441, "p_ign": 583059},
    {"case": "RDE_06", "phi": 0.73, "p0": 182547, "T0": 324, "T_ign": 2001, "p_ign": 317923},
    {"case": "RDE_07", "phi": 0.73, "p0": 83400, "T0": 364, "T_ign": 2350, "p_ign": 378216},
    {"case": "RDE_08", "phi": 1.37, "p0": 154430, "T0": 377, "T_ign": 1809, "p_ign": 483684},
    {"case": "RDE_09", "phi": 0.91, "p0": 118381, "T0": 338, "T_ign": 2233, "p_ign": 759723},
    {"case": "RDE_10", "phi": 1.07, "p0": 148036, "T0": 267, "T_ign": 2300, "p_ign": 783379},
    {"case": "RDE_11", "phi": 0.80, "p0": 109767, "T0": 292, "T_ign": 2161, "p_ign": 684580},
    {"case": "RDE_12", "phi": 1.03, "p0": 174009, "T0": 253, "T_ign": 1888, "p_ign": 966067},
]

def run_cantera(phi, p0_pa, T0_k):
    """
    Run Cantera for H2/air detonation properties.
    Returns CJ speed, post-shock T/p, equilibrium composition.
    """
    try:
        # Use GRI-Mech 3.0 or a simpler H2 mechanism
        gas = ct.Solution('gri30.yaml')

        # Convert phi to mole fractions
        # phi = (X_H2 / X_O2) / (X_H2/X_O2)_stoich
        # stoich: H2 + 0.5 O2 -> H2O, so stoich ratio = 2.0 (moles H2 / moles O2)
        X_O2 = 0.21  # air
        X_N2 = 0.79
        X_H2 = phi * 0.5 * X_O2  # stoich ratio is 2:1 H2:O2

        # Normalize
        total = X_H2 + X_O2 + X_N2
        X_H2 /= total
        X_O2 /= total
        X_N2 /= total

        gas.TPX = T0_k, p0_pa, f'H2:{X_H2}, O2:{X_O2}, N2:{X_N2}'

        # CJ detonation speed
        cj_speed = ct.Detonation.cj_speed(gas)

        # CJ state (post-detonation equilibrium)
        cj_state = ct.Detonation.cj_state(gas)

        result = {
            "cj_speed_m_s": float(cj_speed),
            "cj_pressure_pa": float(cj_state.P),
            "cj_temperature_k": float(cj_state.T),
            "cj_density_kg_m3": float(cj_state.density),
            "cj_h2_mass_fraction": float(cj_state.Y[gas.species_index('H2')]),
            "cj_o2_mass_fraction": float(cj_state.Y[gas.species_index('O2')]),
            "cj_h2o_mass_fraction": float(cj_state.Y[gas.species_index('H2O')]),
            "success": True,
            "error": None
        }

    except Exception as e:
        result = {
            "cj_speed_m_s": np.nan,
            "cj_pressure_pa": np.nan,
            "cj_temperature_k": np.nan,
            "cj_density_kg_m3": np.nan,
            "cj_h2_mass_fraction": np.nan,
            "cj_o2_mass_fraction": np.nan,
            "cj_h2o_mass_fraction": np.nan,
            "success": False,
            "error": str(e)
        }

    return result

def main():
    print("=" * 60)
    print("RDE CANTERA VALIDATOR + PARAMETER SWEEP")
    print(f"Cantera version: {ct.__version__}")
    print("=" * 60)

    results = []

    for anchor in ANCHORS:
        print(f"\nRunning Cantera for {anchor['case']}...")
        print(f"  phi={anchor['phi']}, p0={anchor['p0']:.0f} Pa, T0={anchor['T0']:.0f} K")

        cantera_result = run_cantera(anchor['phi'], anchor['p0'], anchor['T0'])

        row = {
            "case": anchor['case'],
            "phi": anchor['phi'],
            "p0_pa": anchor['p0'],
            "T0_k": anchor['T0'],
            "T_ign_k": anchor['T_ign'],
            "p_ign_pa": anchor['p_ign'],
            **cantera_result
        }

        results.append(row)

        if cantera_result['success']:
            print(f"  CJ speed: {cantera_result['cj_speed_m_s']:.1f} m/s")
            print(f"  CJ T: {cantera_result['cj_temperature_k']:.1f} K")
            print(f"  CJ p: {cantera_result['cj_pressure_pa']:.0f} Pa")
        else:
            print(f"  ERROR: {cantera_result['error']}")

    # Save results
    df = pd.DataFrame(results)
    output_csv = OUTPUT_DIR / "RDE_cantera_validation.csv"
    df.to_csv(output_csv, index=False)

    print(f"\n{'='*60}")
    print(f"Saved Cantera results to: {output_csv}")
    print(f"Cases: {len(df)} | Successful: {df['success'].sum()}")
    print(f"{'='*60}")

    # Summary statistics
    print("\nSUMMARY:")
    print(f"  CJ speed range: {df['cj_speed_m_s'].min():.1f} - {df['cj_speed_m_s'].max():.1f} m/s")
    print(f"  CJ T range: {df['cj_temperature_k'].min():.1f} - {df['cj_temperature_k'].max():.1f} K")
    print(f"  CJ p range: {df['cj_pressure_pa'].min():.0f} - {df['cj_pressure_pa'].max():.0f} Pa")

    # Identify edge cases for additional CFD
    print("\nEdge cases (potential CFD verification targets):")

    # Near-extinction (low CJ speed)
    low_cj = df.nsmallest(3, 'cj_speed_m_s')
    print("\n  Lowest CJ speed (near-extinction risk):")
    for _, row in low_cj.iterrows():
        print(f"    {row['case']}: {row['cj_speed_m_s']:.1f} m/s")

    # Highest pressure (strongest detonation)
    high_p = df.nlargest(3, 'cj_pressure_pa')
    print("\n  Highest CJ pressure:")
    for _, row in high_p.iterrows():
        print(f"    {row['case']}: {row['cj_pressure_pa']:.0f} Pa")

if __name__ == "__main__":
    main()
