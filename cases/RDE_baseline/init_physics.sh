#!/bin/bash

echo "Initializing RDE Premixed Physics..."

# 1. Clean the old Non-Premixed species files
rm 0/Y* 0/O2 0/H2 0/N2 2>/dev/null

# 2. Fix Turbulence files (Rename 'fuel' to 'inlet', delete 'air' block)
for f in 0/*; do
    if [ -f "$f" ] && [[ ! "$f" =~ (p|U|T)$ ]]; then
        sed -i '/air/,/}/d' "$f"
        sed -i 's/fuel/inlet/g' "$f"
    fi
done

# 3. Inject Premixed Velocity (150 m/s upward injection)
cat << 'EOF' > 0/U
FoamFile { format ascii; class volVectorField; location "0"; object U; }
dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField {
    #includeEtc "caseDicts/setConstraintTypes"
    inlet  { type fixedValue; value uniform (0 150 0); }
    outlet { type zeroGradient; }
}
EOF

# 4. Inject Pressure Field
cat << 'EOF' > 0/p
FoamFile { format ascii; class volScalarField; location "0"; object p; }
dimensions [1 -1 -2 0 0 0 0];
internalField uniform 101325;
boundaryField {
    #includeEtc "caseDicts/setConstraintTypes"
    inlet  { type zeroGradient; }
    outlet { type zeroGradient; }
}
EOF

# 5. Inject Cantera Ignition Temperature
cat << 'EOF' > 0/T
FoamFile { format ascii; class volScalarField; location "0"; object T; }
dimensions [0 0 0 1 0 0 0];
internalField uniform 2748.62;
boundaryField {
    #includeEtc "caseDicts/setConstraintTypes"
    inlet  { type fixedValue; value uniform 300; }
    outlet { type zeroGradient; }
}
EOF

# 6. Inject Exact Mass Fractions for H2/Air
cat << 'EOF' > 0/Ydefault
FoamFile { format ascii; class volScalarField; location "0"; object Ydefault; }
dimensions [0 0 0 0 0 0 0];
internalField uniform 0;
boundaryField {
    #includeEtc "caseDicts/setConstraintTypes"
    inlet  { type fixedValue; value uniform 0; }
    outlet { type zeroGradient; }
}
EOF

cp 0/Ydefault 0/H2 && sed -i 's/uniform 0/uniform 0.0283/g' 0/H2
cp 0/Ydefault 0/O2 && sed -i 's/uniform 0/uniform 0.2265/g' 0/O2
cp 0/Ydefault 0/N2 && sed -i 's/uniform 0/uniform 0.7452/g' 0/N2

echo "Physics initialized successfully!"
