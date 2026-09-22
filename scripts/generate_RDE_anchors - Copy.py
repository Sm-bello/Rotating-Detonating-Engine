#!/usr/bin/env python3
"""
RDE Anchor Case Generator — Run this in WSL
Generates all 12 anchor cases directly on your machine.
No downloads, no heredoc issues.
"""

import os
import shutil
import subprocess

# ============================================================
# CONFIG — Adjust paths if your setup differs
# ============================================================
ROOT = "/mnt/c/Users/User/Desktop/COMPLETED_PROJECTS/RDE_Reseacrh/CFD_Simulations"
SRC_CASE = "RDE_PHI_2D"  # Your working reference case

# Anchor matrix (12 cases, 5 parameters each)
# Order: [phi, p0, T0, T_ign, p_ign]
ANCHORS = [
    [1.28, 95757, 287, 1597, 869104],
    [1.24, 192652, 397, 1668, 622140],
    [0.60, 171667, 312, 1952, 952472],
    [1.18, 137430, 361, 1533, 472364],
    [1.00, 125495, 332, 2441, 583059],
    [0.73, 182547, 324, 2001, 317923],
    [0.73, 83400, 364, 2350, 378216],
    [1.37, 154430, 377, 1809, 483684],
    [0.91, 118381, 338, 2233, 759723],
    [1.07, 148036, 267, 2300, 783379],
    [0.80, 109767, 292, 2161, 684580],
    [1.03, 174009, 253, 1888, 966067],
]

def compute_species(phi):
    """Compute mass fractions from equivalence ratio."""
    Y_O2 = 0.232
    Y_H2_stoich_mass = 0.126
    Y_H2 = phi * Y_H2_stoich_mass * Y_O2
    Y_H2 = min(Y_H2, 0.5)  # sanity cap
    Y_N2 = 1.0 - Y_H2 - Y_O2
    Y_H2O = 0.0
    return Y_H2, Y_O2, Y_H2O, Y_N2

def write_setFieldsDict(case_dir, T0, p0, T_ign, p_ign, Y_H2, Y_O2, Y_H2O, Y_N2):
    Y_H2_ign = Y_H2 * 0.5
    Y_O2_ign = Y_O2 * 0.5
    Y_H2O_ign = 0.0
    Y_N2_ign = 1.0 - Y_H2_ign - Y_O2_ign - Y_H2O_ign

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  2406                                  |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      setFieldsDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

defaultFieldValues
(
    volVectorFieldValue U     ( 0 0 0 )
    volScalarFieldValue T     {T0:.0f}
    volScalarFieldValue p     {p0:.0f}
    volScalarFieldValue H2    {Y_H2:.5f}
    volScalarFieldValue O2    {Y_O2:.5f}
    volScalarFieldValue H2O   {Y_H2O:.5f}
    volScalarFieldValue N2    {Y_N2:.5f}
);

regions
(
    boxToCell
    {{
        box ( 0.040 0.000 0.000 ) ( 0.080 0.025 0.001 );
        fieldValues
        (
            volScalarFieldValue T     {T_ign:.0f}
            volScalarFieldValue p     {p_ign:.0f}
            volScalarFieldValue H2    {Y_H2_ign:.5f}
            volScalarFieldValue O2    {Y_O2_ign:.5f}
            volScalarFieldValue H2O   {Y_H2O_ign:.5f}
            volScalarFieldValue N2    {Y_N2_ign:.5f}
        );
    }}
);

// ************************************************************************* //
"""
    with open(os.path.join(case_dir, "system", "setFieldsDict"), "w") as f:
        f.write(content)

def modify_field(case_dir, field_name, value, is_scalar=True):
    """Use foamDictionary to safely modify a field."""
    field_file = os.path.join(case_dir, "0", field_name)
    if not os.path.exists(field_file):
        print(f"  WARNING: {field_file} not found, skipping")
        return

    cmd = ["foamDictionary", field_file, "-entry", "internalField", "-set", f"uniform {value}"]
    subprocess.run(cmd, capture_output=True)

    # Also update outlet boundary
    cmd = ["foamDictionary", field_file, "-entry", "boundaryField.outlet.value", "-set", f"uniform {value}"]
    subprocess.run(cmd, capture_output=True)

    if field_name == "p":
        cmd = ["foamDictionary", field_file, "-entry", "boundaryField.outlet.fieldInf", "-set", str(value)]
        subprocess.run(cmd, capture_output=True)
    elif field_name in ["T", "rho", "H2", "O2", "N2", "H2O"]:
        cmd = ["foamDictionary", field_file, "-entry", "boundaryField.outlet.inletValue", "-set", f"uniform {value}"]
        subprocess.run(cmd, capture_output=True)

def setup_case(idx, params):
    case_id = f"RDE_{idx+1:02d}"
    phi, p0, T0, T_ign, p_ign = params

    print(f"\n{'='*60}")
    print(f"Setting up {case_id}")
    print(f"  phi={phi}, p0={p0:.0f} Pa, T0={T0:.0f} K")
    print(f"  T_ign={T_ign:.0f} K, p_ign={p_ign:.0f} Pa")

    case_dir = os.path.join(ROOT, case_id)
    src_dir = os.path.join(ROOT, SRC_CASE)

    if not os.path.exists(src_dir):
        print(f"ERROR: Source case {SRC_CASE} not found at {src_dir}")
        return False

    # Remove old, copy fresh
    if os.path.exists(case_dir):
        shutil.rmtree(case_dir)
    shutil.copytree(src_dir, case_dir)

    # Compute species
    Y_H2, Y_O2, Y_H2O, Y_N2 = compute_species(phi)
    rho0 = p0 / (287.0 * T0)

    # Write setFieldsDict
    write_setFieldsDict(case_dir, T0, p0, T_ign, p_ign, Y_H2, Y_O2, Y_H2O, Y_N2)

    # Modify 0/ fields using foamDictionary
    modify_field(case_dir, "p", p0)
    modify_field(case_dir, "T", T0)
    modify_field(case_dir, "rho", f"{rho0:.4f}")
    modify_field(case_dir, "H2", f"{Y_H2:.5f}")
    modify_field(case_dir, "O2", f"{Y_O2:.5f}")
    modify_field(case_dir, "N2", f"{Y_N2:.5f}")
    modify_field(case_dir, "H2O", f"{Y_H2O:.5f}")

    # Run setFields
    result = subprocess.run(
        ["setFields"],
        cwd=case_dir,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: setFields failed: {result.stderr}")
    else:
        print(f"  setFields OK")

    print(f"  {case_id} READY at {case_dir}")
    return True

def main():
    print("="*60)
    print("RDE ANCHOR CASE GENERATOR")
    print("="*60)
    print(f"Root directory: {ROOT}")
    print(f"Source case:    {SRC_CASE}")
    print(f"Generating:     {len(ANCHORS)} anchor cases")

    success = 0
    for i, params in enumerate(ANCHORS):
        if setup_case(i, params):
            success += 1

    print(f"\n{'='*60}")
    print(f"DONE: {success}/{len(ANCHORS)} cases generated successfully")
    print(f"{'='*60}")
    print("\nTo run a single case:")
    print("  cd {ROOT}/RDE_01 && reactingFoam | tee log.reactingFoam")
    print("\nTo run all cases in parallel, create a batch script or use:")
    print("  for d in RDE_*/; do (cd $d && reactingFoam > log.reactingFoam 2>&1 &); done")

if __name__ == "__main__":
    main()
