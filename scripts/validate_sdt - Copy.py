#!/usr/bin/env python3
"""
Quick validation script for SD Toolbox CJ speeds.
Run this after installing SD Toolbox to verify correct values.
"""

import sys
import os

# Robust import logic
try:
    # Try the most common import paths
    from sdtoolbox.postshock import CJspeed
    print("✓ SD Toolbox imported successfully (sdtoolbox)")
except ImportError:
    try:
        from SDToolbox import CJspeed
        print("✓ SD Toolbox imported successfully (SDToolbox)")
    except ImportError:
        print("✗ SD Toolbox not found.")
        print("Check if 'sdtoolbox.pth' is in your site-packages and points to the correct folder.")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)

# Test cases matching your RDE anchors
test_cases = [
    # (P1_Pa, T1_K, phi, expected_m_s)
    (95757, 287, 1.280, 1850),    # RDE_01
    (192652, 397, 1.240, 1900),   # RDE_02  
    (171667, 312, 0.600, 1700),   # RDE_03
    (137430, 361, 1.180, 1850),   # RDE_04
    (125495, 332, 1.000, 1900),   # RDE_05
    (182547, 324, 0.730, 1750),   # RDE_06
    (83400, 364, 0.730, 1650),    # RDE_07
    (154430, 377, 1.370, 1800),   # RDE_08
    (118381, 338, 0.910, 1850),   # RDE_09
    (148036, 267, 1.070, 1800),   # RDE_10
    (109767, 292, 0.800, 1750),   # RDE_11
    (174009, 253, 1.030, 1800),   # RDE_12
]

print("\n" + "="*60)
print("CJ SPEED VALIDATION")
print("="*60)

for p_pa, t_k, phi, expected in test_cases:
    X_O2 = 1.0 / (1.0 + 2.0*phi + 3.76)
    X_H2 = 2.0 * phi * X_O2
    X_N2 = 3.76 * X_O2

    X_str = f'H2:{X_H2:.6f},O2:{X_O2:.6f},N2:{X_N2:.6f}'

    try:
        # Note: Ensure gri30.yaml is in your current working directory or Cantera's data path
        cj = CJspeed(p_pa, t_k, X_str, 'gri30.yaml')
        status = "✓" if abs(cj - expected) < 200 else "⚠"
        print(f"{status} phi={phi:.3f}, p={p_pa/101325:.2f}atm, T={t_k}K → CJ={cj:.1f} m/s (expected ~{expected})")
    except Exception as e:
        print(f"✗ phi={phi:.3f} FAILED: {e}")

print("\n" + "="*60)
print("If all checks show ✓ with CJ speeds ~1600-2000 m/s, you're good to run v9.")
print("="*60)