#!/usr/bin/env python3
"""
Minimal example extractor for OpenFOAM time directories produced by RDE_PHI_2D.

Reads selected fields (p, T, H2, O2, U) from a time directory and writes a
compressed NumPy archive.  This is intentionally simple so the community can
extend it for batch extraction toward the RDE-72 format.

Usage
-----
  python scripts/extract_fields.py cases/RDE_PHI_2D 0.0005 -o snapshot_0.0005.npz
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np


def read_foam_scalar(path: Path) -> np.ndarray:
    """Parse a basic OpenFOAM volScalarField (uniform or nonuniform List)."""
    text = path.read_text()
    # nonuniform List
    m = re.search(r"nonuniform\s+List<scalar>\s*\n\s*(\d+)\s*\n\((.*?)\)", text, re.S)
    if m:
        n = int(m.group(1))
        values = np.fromstring(m.group(2).replace("\n", " "), sep=" ", dtype=np.float64)
        if values.size != n:
            raise ValueError(f"{path}: expected {n} values, got {values.size}")
        return values
    # uniform
    m = re.search(r"internalField\s+uniform\s+([-+eE0-9.]+)", text)
    if m:
        # we need the mesh size; caller should pass nCells if uniform
        return np.array([float(m.group(1))])
    raise ValueError(f"Cannot parse scalar field: {path}")


def read_foam_vector(path: Path) -> np.ndarray:
    """Parse a basic OpenFOAM volVectorField (returns shape (n, 3))."""
    text = path.read_text()
    m = re.search(
        r"nonuniform\s+List<vector>\s*\n\s*(\d+)\s*\n\((.*?)\)", text, re.S
    )
    if m:
        n = int(m.group(1))
        # vectors appear as (x y z)
        nums = re.findall(r"[-+eE0-9.]+", m.group(2))
        arr = np.array([float(x) for x in nums], dtype=np.float64).reshape(-1, 3)
        if arr.shape[0] != n:
            raise ValueError(f"{path}: expected {n} vectors, got {arr.shape[0]}")
        return arr
    m = re.search(
        r"internalField\s+uniform\s+\(\s*([-+eE0-9.]+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)\s*\)",
        text,
    )
    if m:
        return np.array([[float(m.group(1)), float(m.group(2)), float(m.group(3))]])
    raise ValueError(f"Cannot parse vector field: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("case", type=Path, help="Path to OpenFOAM case root")
    ap.add_argument("time", type=str, help="Time directory name, e.g. 0.0005")
    ap.add_argument("-o", "--output", type=Path, default=Path("snapshot.npz"))
    ap.add_argument(
        "--fields",
        nargs="+",
        default=["p", "T", "H2", "O2", "U"],
        help="Field names to extract",
    )
    args = ap.parse_args()

    tdir = args.case / args.time
    if not tdir.is_dir():
        raise SystemExit(f"Time directory not found: {tdir}")

    data = {}
    for name in args.fields:
        fpath = tdir / name
        if not fpath.exists():
            print(f"  skip (missing): {name}")
            continue
        if name == "U":
            data["U"] = read_foam_vector(fpath)
            print(f"  U shape {data['U'].shape}")
        else:
            data[name] = read_foam_scalar(fpath)
            print(f"  {name} shape {data[name].shape}")

    data["time"] = float(args.time)
    np.savez_compressed(args.output, **data)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
