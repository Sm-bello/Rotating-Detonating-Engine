#!/bin/bash
# rde_preflight.sh — Run this INSIDE RDE_baseline/

BASE="."
PASS=0; WARN=0; FAIL=0

ok()   { echo "  [PASS] $1"; ((PASS++)); }
warn() { echo "  [WARN] $1"; ((WARN++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }
hdr()  { echo -e "\n=== $1 ==="; }

# -------------------------------------------------------
hdr "1. MESH BOUNDS (blockMeshDict)"
# -------------------------------------------------------
BM="constant/polyMesh/blockMeshDict"
[ ! -f "$BM" ] && BM="system/blockMeshDict"
if [ -f "$BM" ]; then
    echo "  File: $BM"
    python3 - "$BM" <<'PYEOF'
import re, sys
with open(sys.argv[1]) as f: txt = f.read()
nums = re.findall(r'\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)', txt)
if nums:
    xs = [float(r[0]) for r in nums]
    ys = [float(r[1]) for r in nums]
    zs = [float(r[2]) for r in nums]
    print(f"  x: [{min(xs):.5f}, {max(xs):.5f}]  span={max(xs)-min(xs):.5f} m")
    print(f"  y: [{min(ys):.5f}, {max(ys):.5f}]  span={max(ys)-min(ys):.5f} m")
    print(f"  z: [{min(zs):.5f}, {max(zs):.5f}]  span={max(zs)-min(zs):.5f} m")
    print(f"  THERMAL BOX check: x=[0.02,0.08] y=[0.01,0.025] -> ", end="")
    ok = min(xs)<=0.02 and max(xs)>=0.08 and min(ys)<=0.01 and max(ys)>=0.025
    print("INSIDE mesh" if ok else "*** OUT OF BOUNDS — fix set_thermal_damage box ***")
else:
    print("  Could not parse vertex coords from blockMeshDict")
PYEOF
    ok "blockMeshDict found and parsed"
else
    warn "blockMeshDict not found — mesh may be pre-generated only"
fi

# -------------------------------------------------------
hdr "2. H2 INLET PATCH (0/H2)"
# -------------------------------------------------------
H2="0/H2"
if [ ! -f "$H2" ]; then
    fail "0/H2 not found — injector fault function will break"
else
    ok "0/H2 exists"
    echo "  Patch structure:"
    python3 - "$H2" <<'PYEOF'
import re, sys
with open(sys.argv[1]) as f: txt = f.read()
patches = re.findall(r'(\w+)\s*\{[^}]*type\s+(\w+)[^}]*\}', txt, re.DOTALL)
uniforms = [(m.start(), m.group()) for m in re.finditer(r'uniform\s+[\d.eE+-]+', txt)]
print(f"  Patches found: {[p[0] for p in patches]}")
print(f"  'uniform' occurrences: {len(uniforms)}")
for i,(pos,val) in enumerate(uniforms):
    line = txt[:pos].count('\n')+1
    print(f"    [{i}] line {line}: {val.strip()}")
if len(uniforms) == 1:
    print("  -> set_injector_fault: count=1 is CORRECT (only 1 uniform)")
elif len(uniforms) > 1:
    print("  -> REVIEW: multiple uniforms — verify which index is the inlet in set_injector_fault")
PYEOF
fi

# -------------------------------------------------------
hdr "3. 0/nut — TURBULENCE WALL BC"
# -------------------------------------------------------
if [ ! -f "0/nut" ]; then
    warn "0/nut NOT found — set_roughness will silently skip"
    echo "  If running turbulent: create 0/nut with nutkWallFunction on wall patches"
    echo "  If running laminar: roughness requires a different BC mechanism (e.g. roughWall in 0/U)"
else
    ok "0/nut exists"
    python3 - "0/nut" <<'PYEOF'
import re, sys
with open(sys.argv[1]) as f: txt = f.read()
walls = re.findall(r'(\w+)\s*\{[^}]*nutkWallFunction[^}]*\}', txt, re.DOTALL)
rough = re.findall(r'(\w+)\s*\{[^}]*nutkRoughWallFunction[^}]*\}', txt, re.DOTALL)
all_patches = re.findall(r'(\w+)\s*\{[^}]*type\s+\w+[^}]*\}', txt, re.DOTALL)
print(f"  nutkWallFunction patches: {walls}")
print(f"  nutkRoughWallFunction patches (already rough): {rough}")
if walls:
    print(f"  -> set_roughness will upgrade these to nutkRoughWallFunction")
elif not rough:
    print("  -> WARN: no wall patches with nutkWallFunction found")
PYEOF
fi

# -------------------------------------------------------
hdr "4. U INLET PATCH (for multi-wave perturbation)"
# -------------------------------------------------------
if [ ! -f "0/U" ]; then
    fail "0/U not found"
else
    ok "0/U exists"
    python3 - "0/U" <<'PYEOF'
import re, sys
with open(sys.argv[1]) as f: txt = f.read()
matches = list(re.finditer(r'value\s+uniform\s+\(0\s+([\d.]+)\s+0\)', txt))
print(f"  'value uniform (0 VEL 0)' occurrences: {len(matches)}")
for m in matches:
    line = txt[:m.start()].count('\n')+1
    print(f"    line {line}: vel={m.group(1)} m/s")
if len(matches) >= 1:
    print("  -> set_phi_vel and set_multiwave will target this pattern: OK")
else:
    print("  -> WARN: pattern not found — check your U inlet BC format")
PYEOF
fi

# -------------------------------------------------------
hdr "5. CONTROLDICT PROBE POSITIONS vs MESH BOUNDS"
# -------------------------------------------------------
CD="system/controlDict"
[ ! -f "$CD" ] && CD="../system/controlDict"
if [ -f "$CD" ]; then
    python3 - "$CD" "$BM" <<'PYEOF'
import re, sys

with open(sys.argv[1]) as f: cd = f.read()
probes = re.findall(r'\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)', cd)
print(f"  Probe count in controlDict: {len(probes)}")

bm_path = sys.argv[2] if len(sys.argv)>2 else ""
try:
    with open(bm_path) as f: bm = f.read()
    verts = re.findall(r'\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)', bm)
    if verts:
        xs=[float(v[0]) for v in verts]; ys=[float(v[1]) for v in verts]; zs=[float(v[2]) for v in verts]
        xmin,xmax = min(xs),max(xs); ymin,ymax = min(ys),max(ys); zmin,zmax = min(zs),max(zs)
        out = []
        for p in probes:
            px,py,pz = float(p[0]),float(p[1]),float(p[2])
            if not (xmin<=px<=xmax and ymin<=py<=ymax and zmin<=pz<=zmax):
                out.append(p)
        if out:
            print(f"  PROBES OUTSIDE MESH BOUNDS ({len(out)}):")
            for p in out: print(f"    {p}")
        else:
            print(f"  All {len(probes)} probes within mesh bounds: OK")
except:
    print("  (mesh bounds not available — skipping probe range check)")
PYEOF
    ok "controlDict probe check done"
else
    fail "system/controlDict not found"
fi

# -------------------------------------------------------
hdr "6. SWEEP SCRIPT DRY-RUN (logic only, no foamRun)"
# -------------------------------------------------------
SWEEP="$(dirname $0)/rde_sweep_v5.sh"
[ ! -f "$SWEEP" ] && SWEEP="../../rde_sweep_v5.sh"
if [ ! -f "$SWEEP" ]; then
    warn "rde_sweep_v5.sh not found next to this script — skipping dry-run"
else
    echo "  Checking bash syntax..."
    if bash -n "$SWEEP" 2>&1; then
        ok "Sweep script syntax valid"
    else
        fail "Sweep script has syntax errors — fix before running"
    fi

    echo ""
    echo "  Simulating case name generation (no foamRun)..."
    python3 - <<'PYEOF'
import math

lean  = [0.65,0.68,0.70,0.73,0.75,0.78,0.80,0.83,0.85,0.90,0.95,1.00]
rich  = [1.10,1.20,1.30,1.40,1.50,1.55,1.60,1.80]
mw    = [(2,0.10),(2,0.15),(2,0.20),(2,0.25),(2,0.30),
         (3,0.10),(3,0.15),(3,0.20),(3,0.25),(3,0.30)]
trans = [0.87,0.92,0.96,1.01,1.06,1.14,1.24,1.36]
inj   = [(1,0.90),(1,1.00),(1,1.20),(2,0.90),(2,1.00),
         (2,1.20),(4,0.90),(4,1.00),(4,1.20),(4,1.40)]
ks    = [10,50,100,150,200,300,400,500]
thot  = [600,900,1200,1500,1800,2100,2400,2700]
comb  = [(2,10),(2,50),(2,100),(2,200),(4,50),(4,100),(4,200),(4,300)]

groups = {
    "lean":       lean,
    "rich":       rich,
    "multiwave":  mw,
    "transition": trans,
    "injector":   inj,
    "roughness":  ks,
    "thermal":    thot,
    "combined":   comb,
}
total = sum(len(v) for v in groups.values())
print(f"  {'Group':<14} {'Cases':>6}")
print(f"  {'-'*22}")
for g,v in groups.items():
    print(f"  {g:<14} {len(v):>6}")
print(f"  {'-'*22}")
print(f"  {'TOTAL':<14} {total:>6}  {'OK' if total==72 else '*** NOT 72 ***'}")
PYEOF
fi

# -------------------------------------------------------
hdr "7. CSV COLUMN COUNT ESTIMATE"
# -------------------------------------------------------
python3 - <<'PYEOF'
n_probes = 40
cols = 1 + n_probes + n_probes + 6   # Time + P1-P40 + T1-T40 + meta cols
print(f"  P columns : {n_probes}")
print(f"  T columns : {n_probes}")
print(f"  Meta cols : 6  (Phi Vel GroupID Label CaseParams Damage_Seed)")
print(f"  Total cols: {cols}")
rows_per_case = 200  # ~5ms / 25us per probe write
total_cases   = 72
est_rows = rows_per_case * total_cases
print(f"  Estimated rows @ {rows_per_case}/case x 72: {est_rows:,}")
print(f"  Sliding windows (size=50,step=10): ~{max(0,(rows_per_case-50)//10 * total_cases):,} windows")
PYEOF

# -------------------------------------------------------
hdr "SUMMARY"
# -------------------------------------------------------
echo "  PASS: $PASS   WARN: $WARN   FAIL: $FAIL"
if [ $FAIL -gt 0 ]; then
    echo "  STATUS: FIX FAILURES before running sweep"
elif [ $WARN -gt 0 ]; then
    echo "  STATUS: Review warnings — sweep may run but some groups may skip"
else
    echo "  STATUS: All checks passed — safe to run rde_sweep_v5.sh"
fi
