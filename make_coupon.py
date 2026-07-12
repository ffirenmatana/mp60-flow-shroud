#!/usr/bin/env python3
"""Mount test coupon: the bottom slice of the shroud (bayonet + barrel).

Prints in ~30 min to verify the twist-lock seats before committing to the
full ~2-day print. Geometry is IDENTICAL to the full part's mount region --
it's a boolean cut, not a re-model -- so a good coupon fit == a good part fit.

    make_coupon.py            # mp60 (default)
    make_coupon.py --pump mp40
"""
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
CUT_Z = 22.0            # coupon height: full bayonet engagement + grip

SRC = {'mp60': 'mp60_shroud_v3.stl', 'mp40': 'mp40_shroud_v3.stl'}
name = sys.argv[sys.argv.index('--pump') + 1] if '--pump' in sys.argv else 'mp60'

part = trimesh.load(os.path.join(HERE, SRC[name]))
# capped plane slice keeps z <= CUT_Z; the z=0 rim is already closed, so
# only the new top face is capped. Doesn't require a watertight input, so
# the float32 slivers in the exported STL are a non-issue here.
coupon = part.slice_plane(plane_origin=[0, 0, CUT_Z],
                          plane_normal=[0, 0, -1], cap=True)
coupon.fix_normals()
out = os.path.join(HERE, f'{name}_mount_coupon.stl')
coupon.export(out)
cv = coupon.vertices
print(f'{name} coupon: watertight={coupon.is_watertight} '
      f'z 0..{cv[:, 2].max():.1f}mm  vol {coupon.volume/1000:.1f}cm3')
print('exported', os.path.basename(out))
