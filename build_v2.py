#!/usr/bin/env python3
"""MP60 quarter-fan shroud v2 -- single-piece print, sim-driven geometry.

Architecture (z up, cage rim at z=0, prints in this orientation):
  stock cage (imported mesh, bayonet lugs + perforated intake barrel)
    -> anemone spike/spokes removed from the discharge bore
  vertical morph duct: circle O71.6 -> rounded-rect 95(y) x 42(x)
    with 3 anti-swirl straightener fins
  mitered 90-degree corner: 45-degree diagonal back wall +
    quarter-arc louver turning blades (all surfaces >= 45 deg, printable)
  horizontal fan: width 95 -> 185 (x^p law side walls), 4 cambered
    splitter vanes, roof = per-channel 50-degree chevron vaults
    (self-supporting; vanes are the springers), exit = 5 arched windows
  corbel: 45-degree wedge under the fan floor root

Output: mp60_shroud_v2.stl (+ component STLs for inspection)
"""
import numpy as np
import trimesh

# ---------------- parameters (sim winners marked SIM) ----------------
BORE = 71.6         # cage discharge bore diameter (measured from 3MF)
WALL = 3.2
DUCT_W = 95.0       # horizontal duct width at fan start (y)
DUCT_D = 42.0       # vertical duct depth after morph (x)
DUCT_H = 45.0       # horizontal duct height in the corner box
Z_FACE = 72.0       # cage discharge face
Z_JOIN = 66.0       # duct overlaps cage throat down to here
Z_FLOOR = 96.0      # horizontal duct interior floor
FLOOR_TOP = Z_FLOOR + DUCT_H          # flat roof of corner box (141)
X_INNER = DUCT_D / 2                  # inner corner x (+21)
X_FAN0 = 26.0       # fan vanes / vaults start (= diagonal top)
X_EXIT = 110.0      # interior exit face
EXIT_W = 185.0      # interior exit width
EXIT_AREA = 4800.0  # mm^2, ~1.19x bore area
FAN_EXP = 2.0       # SIM: side wall / vane camber law exponent
N_VANES = 4         # SIM: fan splitter vanes
BLADES = [12, 22, 34]   # SIM: louver blade radii from inner corner
BLADE_TRUNC = 25.0  # SIM: degrees truncated from blade top (printability)
BLADE_T = 2.0
VANE_T = 1.8
CHEV = np.tan(np.radians(50))   # chevron vault slope
MY = 192            # transverse samples for fan sections
BORE_AREA = np.pi * (BORE / 2)**2


def smooth(t):
    return t * t * (3 - 2 * t)


# ---------------- generic loft helpers ----------------

def loft_mesh(sections):
    """Loft for matched-station sections: each section is bottom pts
    0..M-1 (left->right) then top pts M..2M-1 (right->left). End caps are
    vertical strips pairing bottom station i with top station 2M-1-i --
    exact for non-convex arched sections."""
    n = len(sections[0])
    m = n // 2
    verts = np.vstack(sections)
    faces = []
    for s in range(len(sections) - 1):
        a, b = s * n, (s + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces += [[a + i, b + i, b + j], [a + i, b + j, a + j]]

    def cap(base, flip):
        out = []
        for i in range(m - 1):
            bi, bj = base + i, base + i + 1
            ti, tj = base + (n - 1 - i), base + (n - 2 - i)
            quad = [[bi, bj, tj], [bi, tj, ti]]
            if flip:
                quad = [[t[0], t[2], t[1]] for t in quad]
            out += quad
        return out

    faces += cap(0, flip=True)
    faces += cap((len(sections) - 1) * n, flip=False)
    m = trimesh.Trimesh(verts, np.array(faces), process=True)
    m.fix_normals()
    return m


def loft_with_centroids(sections):
    """loft_mesh but caps need centroid vertices appended."""
    n = len(sections[0])
    secs = [np.asarray(s, float) for s in sections]
    verts = np.vstack(secs)
    c0 = secs[0].mean(0)
    c1 = secs[-1].mean(0)
    verts = np.vstack([verts, c0[None], c1[None]])
    i_c0, i_c1 = len(verts) - 2, len(verts) - 1
    faces = []
    for s in range(len(secs) - 1):
        a, b = s * n, (s + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces += [[a + i, b + i, b + j], [a + i, b + j, a + j]]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i_c0, j, i])                       # bottom cap
        base = (len(secs) - 1) * n
        faces.append([i_c1, base + i, base + j])         # top cap
    m = trimesh.Trimesh(verts, np.array(faces), process=True)
    m.fix_normals()
    return m


# ---------------- vertical morph duct ----------------

def rrect_pts(w, d, r, n=128):
    """rounded rect, width w (y), depth d (x), corner radius r, CCW in xy."""
    r = min(r, w / 2 - 0.01, d / 2 - 0.01)
    cx, cy = d / 2 - r, w / 2 - r
    pts = []
    for i in range(n):
        a = 2 * np.pi * i / n
        px, py = np.cos(a), np.sin(a)
        pts.append([np.sign(px) * cx + r * px, np.sign(py) * cy + r * py])
    return np.array(pts)


def vertical_duct(grow=0.0):
    secs = []
    z0, z1 = Z_JOIN - (6 if grow == 0 else 0), Z_FLOOR + (14 if grow == 0 else 0)
    zm0, zm1 = Z_FACE + 4, Z_FLOOR - 2
    for z in np.linspace(z0, z1, 36):
        t = smooth(np.clip((z - zm0) / (zm1 - zm0), 0, 1))
        w = BORE + (DUCT_W - BORE) * t + 2 * grow
        d = BORE + (DUCT_D - BORE) * t + 2 * grow
        r = BORE / 2 + (10 - BORE / 2) * t + grow
        p2 = rrect_pts(w, d, r)
        secs.append(np.column_stack([p2[:, 0], p2[:, 1], np.full(len(p2), z)]))
    return loft_with_centroids(secs)


# ---------------- horizontal duct / fan (matched-station sections) ----

def half_width(x, grow=0.0):
    s = np.clip((x - X_FAN0) / (X_EXIT - X_FAN0), 0, 1)
    return DUCT_W / 2 + (EXIT_W - DUCT_W) / 2 * s**FAN_EXP + grow


def vane_positions(x):
    """centerlines of the N_VANES cambered vanes at station x."""
    s = np.clip((x - X_FAN0) / (X_EXIT - X_FAN0), 0, 1)
    delta = (EXIT_W - DUCT_W) / 2
    ys = []
    for k in range(N_VANES):
        f = -1 + 2 * k / (N_VANES - 1)
        ys.append(f * DUCT_W / 4 + 0.5 * f * delta * s**FAN_EXP)
    return np.array(ys)


def roof_profile(x, eta):
    """interior roof height z(y) at station x; eta in [-1,1] maps to y."""
    w = half_width(x)
    y = eta * w
    if x <= X_FAN0:
        top = min(FLOOR_TOP, Z_FLOOR + max(0.5, (x + X_INNER) * 1.0))
        return np.full_like(y, top), y
    ramp = smooth(np.clip((x - X_FAN0) / 8.0, 0, 1))
    vp = vane_positions(x)
    edges = np.concatenate([[-w], vp, [w]])
    area_target = 95 * 45 + (EXIT_AREA - 95 * 45) * \
        np.clip((x - X_FAN0) / (X_EXIT - X_FAN0), 0, 1)
    cw = np.diff(edges) - VANE_T
    tri = 0.25 * CHEV * ramp * (cw**2)
    net_w = cw.sum()
    zs = Z_FLOOR + max(6.0, (area_target - tri.sum()) / net_w)
    zs = min(zs, FLOOR_TOP)
    z = np.full_like(y, zs)
    for k in range(len(cw)):
        lo, hi = edges[k] + VANE_T / 2, edges[k + 1] - VANE_T / 2
        mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
        m = (y >= lo) & (y <= hi)
        z[m] = zs + ramp * CHEV * (half - np.abs(y[m] - mid))
    return z, y


def fan_section(x, grow=0.0):
    eta = np.linspace(-1, 1, MY)
    z_top, y = roof_profile(x, eta)
    w = half_width(x, grow)
    y = eta * w
    zf = Z_FLOOR - grow
    zt = z_top + grow * 1.55   # vertical offset ~= 3.2mm true on 50-deg vaults
    bottom = np.column_stack([np.full(MY, x), y, np.full(MY, zf)])
    top = np.column_stack([np.full(MY, x), y[::-1], zt[::-1]])
    return np.vstack([bottom, top])


def horizontal_duct(grow=0.0):
    x0 = -X_INNER + 0.6 - grow
    x1 = X_EXIT + (8 if grow == 0 else grow)
    xs = np.concatenate([np.linspace(x0, X_FAN0, 30),
                         np.linspace(X_FAN0 + 1e-3, x1, 60)])
    secs = [fan_section(x, grow) for x in xs]
    return loft_mesh(secs)


# ---------------- internals ----------------

def louver_blades():
    parts = []
    th0, th1 = np.radians(90 + BLADE_TRUNC), np.radians(180)
    for rb in BLADES:
        secs = []
        for th in np.linspace(th1, th0, 24):
            cx = X_INNER + rb * np.cos(th)
            cz = Z_FLOOR + rb * np.sin(th)
            nx, nz = np.cos(th), np.sin(th)      # arc normal
            h = BLADE_T / 2
            quad = [[cx + nx * s, yy, cz + nz * s]
                    for s, yy in [(-h, -47.0), (-h, 47.0), (h, 47.0), (h, -47.0)]]
            secs.append(np.array(quad, float))
        parts.append(loft_with_centroids(secs))
    return parts


def fan_vanes():
    parts = []
    xs = np.linspace(X_FAN0 - 6, X_EXIT + 2, 40)
    for k in range(N_VANES):
        secs = []
        for x in xs:
            yk = vane_positions(x)[k]
            quad = np.array([[x, yk - VANE_T/2, Z_FLOOR - 2],
                             [x, yk + VANE_T/2, Z_FLOOR - 2],
                             [x, yk + VANE_T/2, FLOOR_TOP + 14],
                             [x, yk - VANE_T/2, FLOOR_TOP + 14]])
            secs.append(quad)
        parts.append(loft_with_centroids(secs))
    return parts


def straighteners():
    parts = []
    for ang in (90, 210, 330):
        a = np.radians(ang)
        r0, r1 = BORE / 2 - 14, BORE / 2 + 2
        t = 1.6 / 2
        px, py = np.cos(a), np.sin(a)
        qx, qy = -np.sin(a), np.cos(a)
        pts = np.array([[r0*px - t*qx, r0*py - t*qy], [r1*px - t*qx, r1*py - t*qy],
                        [r1*px + t*qx, r1*py + t*qy], [r0*px + t*qx, r0*py + t*qy]])
        secs = [np.column_stack([pts[:, 0], pts[:, 1], np.full(4, z)])
                for z in (Z_FACE - 3, Z_FACE + 19)]
        parts.append(loft_with_centroids(secs))
    return parts


def corbel():
    x0, z0 = X_INNER + WALL - 1, Z_JOIN + 2
    x1 = x0 + 1.19 * (Z_FLOOR - WALL - z0)   # 50-deg corbel
    tri = np.array([[x0, z0], [x1, Z_FLOOR - WALL + 0.5], [x0, Z_FLOOR - WALL + 0.5]])
    secs = []
    for y in (-DUCT_W/2 - 2, DUCT_W/2 + 2):
        secs.append(np.column_stack([tri[:, 0], np.full(3, y), tri[:, 1]]))
    return loft_with_centroids(secs)


def bool_op(op, meshes):
    return trimesh.boolean.boolean_manifold(meshes, op)


def main():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    cage = trimesh.load(os.path.join(here, 'cage.stl'))

    spike_cut = trimesh.creation.cylinder(radius=35.2, height=17,
                                          sections=96)
    spike_cut.apply_translation([0, 0, 65.5])
    cage = bool_op('difference', [cage, spike_cut])

    cav_v = vertical_duct(0.0)
    out_v = vertical_duct(WALL)
    cav_h = horizontal_duct(0.0)
    out_h = horizontal_duct(WALL)

    cavity = bool_op('union', [cav_v, cav_h])
    outer = bool_op('union', [out_v, out_h, corbel()])
    shell = bool_op('difference', [outer, cavity])

    internals = louver_blades() + fan_vanes() + straighteners()
    internals = [bool_op('intersection', [p, cavity]) for p in internals]

    final = bool_op('union', [cage, shell] + internals)
    print('final: watertight', final.is_watertight, 'faces', len(final.faces),
          'volume', round(final.volume / 1000, 1), 'cm3')
    zmax = final.vertices[:, 2].max()
    xr = final.vertices[:, 0].min(), final.vertices[:, 0].max()
    yr = final.vertices[:, 1].min(), final.vertices[:, 1].max()
    print(f'envelope: x {xr[0]:.0f}..{xr[1]:.0f}  y {yr[0]:.0f}..{yr[1]:.0f}  z 0..{zmax:.0f}')

    final.export(os.path.join(here, 'mp60_shroud_v2.stl'))
    shell.export(os.path.join(here, 'v2_shell_only.stl'))
    print('exported mp60_shroud_v2.stl')

    # overhang audit (print orientation = as modeled, rim on bed)
    n = final.face_normals
    area = final.area_faces
    down = n[:, 2] < -np.cos(np.radians(50))     # steeper than 50 deg overhang
    ctr = final.triangles_center
    bad = down & (ctr[:, 2] > 2.0)
    print(f'overhang >50deg area: {area[bad].sum():.0f} mm2 '
          f'({100 * area[bad].sum() / area.sum():.1f}% of surface)')
    zs = ctr[bad][:, 2]
    if len(zs):
        import collections
        hist = collections.Counter((zs // 10 * 10).astype(int))
        print('  by z-band:', dict(sorted(hist.items())))


if __name__ == '__main__':
    main()
