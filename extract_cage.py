#!/usr/bin/env python3
"""Extract cage.stl from the 'Ecotech MP60 Cover' 3MF.

The cage mesh is (c) asadler99, published under the Cults Private Use
license, which does not permit redistribution -- so this repo ships the
extractor instead of the mesh. Download the free 3MF yourself:

    https://cults3d.com/en/3d-model/home/ecotech-mp60-cover

then:

    python3 extract_cage.py ~/Downloads/EcotechV60Modified.3mf

writes cage.stl (reoriented: axis +z, bayonet rim at z=0) next to this
script, after which build_v3.py can generate the full shroud.
"""
import math
import os
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}


def main(path):
    with zipfile.ZipFile(path) as z:
        model_names = [n for n in z.namelist()
                       if n.endswith('.model') and 'Objects' in n] or \
                      [n for n in z.namelist() if n.endswith('3dmodel.model')]
        root = ET.fromstring(z.read(model_names[0]))

    objs = [o for o in root.findall('.//m:object', NS)
            if o.find('.//m:mesh', NS) is not None]
    # the cage is the largest mesh in the file
    obj = max(objs, key=lambda o: len(o.findall('.//m:vertex', NS)))
    V = [(float(v.get('x')), float(v.get('y')), float(v.get('z')))
         for v in obj.findall('.//m:vertex', NS)]
    T = [(int(t.get('v1')), int(t.get('v2')), int(t.get('v3')))
         for t in obj.findall('.//m:triangle', NS)]

    ymin = min(v[1] for v in V)
    W = [(x, z, y - ymin) for x, y, z in V]     # swap y/z, rim to z=0
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cage.stl')
    with open(out, 'wb') as f:
        f.write(b'\0' * 80)
        f.write(struct.pack('<I', len(T)))
        for a, b, c in T:
            p, q, r = W[a], W[c], W[b]          # swapped winding (mirrored)
            u = [q[i] - p[i] for i in range(3)]
            v = [r[i] - p[i] for i in range(3)]
            n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            L = math.sqrt(sum(x*x for x in n)) or 1
            f.write(struct.pack('<3f', *[x / L for x in n]))
            for pt in (p, q, r):
                f.write(struct.pack('<3f', *pt))
            f.write(b'\0\0')
    zs = [w[2] for w in W]
    print(f'cage.stl: {len(T)} tris, z {min(zs):.1f}..{max(zs):.1f} '
          f'(expect ~0..72 for the MP60 cage)')


if __name__ == '__main__':
    main(sys.argv[1])
