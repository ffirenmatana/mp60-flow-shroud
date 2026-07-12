#!/usr/bin/env python3
"""MP60 shroud v3 -- swept gothic-ridge elbow, sim-optimized, single print.

Reads agent/best.json (falls back to seed params) and generates the final
part. Architecture (prints rim-down, like the stock cage):

  stock cage (bayonet lugs + perforated intake barrel, imported mesh)
   -> anemone spike/spokes cut from the Ø71.6 bore
   -> ONE continuous swept duct loft:
        circle -> flat-floor "gothic tent" cross-section (R chevron
        ridges at >=50 deg -- every interior/exterior roof surface
        self-supports; NO turning vanes: CFD says K=0.20 vaneless vs
        0.61+ with anything else)
        vertical rise -> (90+tilt) deg swept bend -> widening fan
        declined by tilt deg (floor-directed jet)
   -> cambered fan splitter vanes (vertical plates, CFD: essential for
      the 90 deg arc spread), trimmed to the vaulted cavity
   -> corbel wedge under the fan root; outboard floor = bed supports

Output: mp60_shroud_v3.stl
"""
import json
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- pump selection ----------------
PUMPS = {
    'mp60': dict(cage='cage.stl', bore=71.6, z_face=72.0, spike_r=35.2,
                 spike_z=(57.5, 74.5), duct_w=95.0,
                 rib_ys=(-28.0, -10.0, 10.0, 28.0),
                 out='mp60_shroud_v3.stl', params=None),   # from agent/final.json
    # MP40: same architecture scaled by bore ratio 56.9/71.6 = 0.795
    'mp40': dict(cage='cage_mp40.stl', bore=56.9, z_face=57.0, spike_r=28.0,
                 spike_z=(43.0, 59.0), duct_w=76.0,
                 rib_ys=(-22.0, -8.0, 8.0, 22.0),
                 out='mp40_shroud_v3.stl',
                 params=dict(bend_r=49.0, duct_h=41.0, fan_len=72.0,
                             exit_w=200.0, area_ratio=1.4, n_vanes=6,
                             exp=2.4, tilt=15.0)),
}
PUMP_NAME = sys.argv[sys.argv.index('--pump') + 1] if '--pump' in sys.argv else 'mp60'
PUMP = PUMPS[PUMP_NAME]

# ---------------- parameters ----------------
BORE = PUMP['bore']
WALL = 3.2
Z_FACE = PUMP['z_face']
Z_JOIN = Z_FACE - 6.0
RISE = 14.0            # straight vertical run above the cage face
DUCT_W = PUMP['duct_w']  # duct width entering the fan
N_RIDGES = 5
CHEV = np.tan(np.radians(50))
VANE_T = 1.8
MY = 192
BORE_AREA = np.pi * (BORE / 2) ** 2

DEFAULTS = dict(bend_r=52.0, duct_h=48.0, fan_len=70.0, exit_w=185.0,
                area_ratio=1.19, n_vanes=4, exp=1.5, tilt=20.0)


WETSIDE_H = 4.0        # glass -> cage rim. EcoTech spec: wet side is
                       # 102 x 71mm and the cage itself is 72mm -- the rim
                       # sits ~flush on the glass (uncertainty +/-5mm).
MAX_TOTAL_H_GLASS = 180.0   # hard cap: part top above the tank floor.
# Tank-sim design rule still applies: rock directly in FRONT of the exit
# must sit 20-40mm BELOW the exit centerline (printed on build).


def load_params():
    p = dict(DEFAULTS)
    if PUMP['params']:
        p.update(PUMP['params'])
        print(f'params for {PUMP_NAME}:', p)
        return p
    bj = os.path.join(HERE, 'agent', 'final.json')
    if not os.path.exists(bj):
        bj = os.path.join(HERE, 'agent', 'best.json')
    if os.path.exists(bj):
        best = json.load(open(bj))
        p.update({k: best['params'][k] for k in DEFAULTS if k in best['params']})
        print('params from agent/best.json:', p)
    else:
        print('agent/best.json not found -- using seed params:', p)
    return p


P = load_params()
TILT = float(P['tilt'])
BEND_R = float(P['bend_r'])
FAN_LEN = float(P['fan_len'])
EXIT_W = float(P['exit_w'])
EXIT_AREA = float(P['area_ratio']) * BORE_AREA
N_VANES = int(P['n_vanes'])
FAN_EXP = float(P['exp'])
TURN = 90.0 + TILT
# fit under MAX_TOTAL_H_GLASS: part top = Z_FACE + RISE + BEND_R + crown
_cw = (DUCT_W - N_VANES * VANE_T) / (N_VANES + 1)
_h0 = max(6.0, (BORE_AREA - (N_VANES + 1) * 0.25 * CHEV * _cw**2) / DUCT_W)
_crown = _h0 / 2 + 0.5 * CHEV * _cw + WALL
RISE = 6.0
_budget = (MAX_TOTAL_H_GLASS - WETSIDE_H) - Z_FACE - RISE - _crown - 7.0
# -7: the circle->tent morph mid-bend rides above the pure tent crown
if BEND_R > _budget:
    print(f'height cap: bend_r {BEND_R} -> {max(30.0, _budget):.1f}')
    BEND_R = max(30.0, _budget)
Z_BEND0 = Z_FACE + RISE
EXIT_Z_GLASS = (WETSIDE_H + Z_FACE + RISE
                + BEND_R * np.sin(np.radians(TURN))
                - FAN_LEN * np.sin(np.radians(TILT)))
print(f'part top: {WETSIDE_H + Z_FACE + RISE + BEND_R + _crown:.0f}mm above glass '
      f'(cap {MAX_TOTAL_H_GLASS:.0f})')
print(f'exit centerline: {EXIT_Z_GLASS:.0f}mm above glass -> keep foreground '
      f'rock crest below ~{EXIT_Z_GLASS - 25:.0f}mm')


def smooth(t):
    return t * t * (3 - 2 * t)


# ---------------- path + frames ----------------
# path: vertical (z up) -> arc in xz around (BEND_R, 0, Z_BEND0) -> straight
ARC_LEN = np.radians(TURN) * BEND_R
L_PRE = Z_BEND0 - Z_JOIN
L_TOT = L_PRE + ARC_LEN + FAN_LEN


def frame(u):
    """u in [0, L_TOT] arc length -> (origin, tangent, n_up) in xz.
    n_up: in-section axis from floor toward roof (floor = inner radius)."""
    if u <= L_PRE:
        o = np.array([0.0, 0.0, Z_JOIN + u])
        t = np.array([0.0, 0.0, 1.0])
        n = np.array([-1.0, 0.0, 0.0])
        return o, t, n
    if u <= L_PRE + ARC_LEN:
        a = (u - L_PRE) / BEND_R
        o = np.array([BEND_R - BEND_R * np.cos(a), 0.0,
                      Z_BEND0 + BEND_R * np.sin(a)])
        t = np.array([np.sin(a), 0.0, np.cos(a)])
        n = np.array([-np.cos(a), 0.0, np.sin(a)])
        return o, t, n
    s = u - L_PRE - ARC_LEN
    a = np.radians(TURN)
    o0 = np.array([BEND_R - BEND_R * np.cos(a), 0.0,
                   Z_BEND0 + BEND_R * np.sin(a)])
    t = np.array([np.sin(a), 0.0, np.cos(a)])
    n = np.array([-np.cos(a), 0.0, np.sin(a)])
    return o0 + s * t, t, n


# ---------------- cross-sections (matched stations) ----------------

def channel_edges(s_fan, w):
    """y-positions bounding the N_VANES+1 channels at this section.
    In the riser/bend (s_fan=0) the fan pattern is scaled down with w so
    the roof valleys land on the future vane lines."""
    ys = vane_offsets(max(s_fan, 0.0), w)
    if s_fan <= 0:
        ys = [y * (w / DUCT_W) for y in ys]
    return np.array([-w / 2] + list(ys) + [w / 2])


def roof_shape(y, s_fan, w, area):
    """returns (h0, roof(y)): flat-floor height + chevron arches, one per
    channel, valleys on the vane centerlines (vanes are the springers)."""
    edges = channel_edges(s_fan, w)
    cw = np.diff(edges)
    tri = float((0.25 * CHEV * cw ** 2).sum())
    h0 = max(6.0, (area - tri) / w)
    ridge = np.zeros_like(y)
    for k in range(len(cw)):
        lo, hi = edges[k], edges[k + 1]
        mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
        m = (y >= lo) & (y <= hi)
        ridge[m] = CHEV * (half - np.abs(y[m] - mid))
    return h0, ridge


def section_profile(u):
    """returns (w, floor_off, z_top(yfrac), morph t) in section coords
    centered on the path: floor at floor_off, roof profile above."""
    # morph from circle to tent across the pre-run + first third of bend
    t = smooth(np.clip((u - 2.0) / (L_PRE + ARC_LEN / 3), 0, 1))
    # width / area schedules
    s_fan = np.clip((u - (L_PRE + ARC_LEN)) / FAN_LEN, 0, 1)
    w_duct = BORE + (DUCT_W - BORE) * t
    w = w_duct + (EXIT_W - w_duct) * s_fan ** FAN_EXP
    area = BORE_AREA + (EXIT_AREA - BORE_AREA) * s_fan
    return t, w, area, s_fan


def vane_offsets(s_fan, w):
    delta = (EXIT_W - DUCT_W) / 2
    ys = []
    for k in range(N_VANES):
        f = -1 + 2 * k / (N_VANES - 1)
        ys.append(f * DUCT_W / 4 + 0.5 * f * delta * s_fan ** FAN_EXP)
    return ys


def section_pts(u, grow=0.0):
    t, w, area, s_fan = section_profile(u)
    wg = w + 2 * grow
    eta = np.linspace(-1, 1, MY)
    y = eta * wg / 2
    r = BORE / 2 + grow
    # circle limbs (clipped inside |y|<r)
    yc = np.clip(y / max(r, 1e-6), -0.999, 0.999)
    circ_lo = -r * np.sqrt(1 - yc ** 2)
    circ_hi = r * np.sqrt(1 - yc ** 2)
    # tent limbs: chevron arch per channel, valleys on vane lines
    h0, ridge = roof_shape(np.clip(y, -w / 2, w / 2), s_fan, w, area)
    tent_lo = np.full(MY, -h0 / 2 - grow)
    tent_hi = h0 / 2 + ridge + grow
    lo = circ_lo * (1 - t) + tent_lo * t
    hi = circ_hi * (1 - t) + tent_hi * t
    o, tv, n = frame(u)
    yhat = np.array([0.0, 1.0, 0.0])
    bottom = o[None] + y[:, None] * yhat[None] + lo[:, None] * (-n)[None] * -1.0
    bottom = o[None] + y[:, None] * yhat[None] + lo[:, None] * n[None]
    top = o[None] + y[::-1, None] * yhat[None] + hi[::-1, None] * n[None]
    return np.vstack([bottom, top])


def duct_loft(grow=0.0, ext=0.0):
    us = np.concatenate([
        np.linspace(0 if grow else -6, L_PRE, 14),
        np.linspace(L_PRE + 1e-3, L_PRE + ARC_LEN, 42),
        np.linspace(L_PRE + ARC_LEN + 1e-3, L_TOT + ext, 40),
    ])
    secs = [section_pts(u, grow) for u in us]
    return loft_mesh(secs)


# ---------------- loft helpers (matched-station, strip caps) --------

def loft_mesh(sections):
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
                quad = [[q[0], q[2], q[1]] for q in quad]
            out += quad
        return out

    faces += cap(0, flip=True)
    faces += cap((len(sections) - 1) * n, flip=False)
    msh = trimesh.Trimesh(verts, np.array(faces), process=True)
    msh.fix_normals()
    return msh


def loft_quads(sections):
    """small convex-quad lofts (vanes, fins, corbel)."""
    n = len(sections[0])
    secs = [np.asarray(s, float) for s in sections]
    verts = np.vstack(secs + [secs[0].mean(0)[None], secs[-1].mean(0)[None]])
    ic0, ic1 = len(verts) - 2, len(verts) - 1
    faces = []
    for s in range(len(secs) - 1):
        a, b = s * n, (s + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces += [[a + i, b + i, b + j], [a + i, b + j, a + j]]
    base = (len(secs) - 1) * n
    for i in range(n):
        j = (i + 1) % n
        faces += [[ic0, j, i], [ic1, base + i, base + j]]
    msh = trimesh.Trimesh(verts, np.array(faces), process=True)
    msh.fix_normals()
    return msh


# ---------------- internals ----------------

def fan_vanes():
    """vertical plates following the cambered plan law, over-tall,
    trimmed to the vaulted cavity by boolean intersection."""
    parts = []
    u0 = L_PRE + ARC_LEN
    for k in range(N_VANES):
        secs = []
        for s in np.linspace(-0.04, 1.06, 30):
            u = u0 + s * FAN_LEN
            o, tv, n = frame(u)
            _, w, _, s_fan = section_profile(u)
            yk = vane_offsets(s_fan, w)[k]
            lo = o + n * (-40)
            hi = o + n * (+70)
            quad = np.array([
                [lo[0], yk - VANE_T / 2, lo[2]], [lo[0], yk + VANE_T / 2, lo[2]],
                [hi[0], yk + VANE_T / 2, hi[2]], [hi[0], yk - VANE_T / 2, hi[2]]])
            secs.append(quad)
        parts.append(loft_quads(secs))
    return parts


def straighteners():
    parts = []
    for ang in (90, 210, 330):
        a = np.radians(ang)
        r0, r1 = BORE / 2 - 14, BORE / 2 + 2
        th = 1.6 / 2
        px, py = np.cos(a), np.sin(a)
        qx, qy = -np.sin(a), np.cos(a)
        pts = np.array([[r0 * px - th * qx, r0 * py - th * qy],
                        [r1 * px - th * qx, r1 * py - th * qy],
                        [r1 * px + th * qx, r1 * py + th * qy],
                        [r0 * px + th * qx, r0 * py + th * qy]])
        secs = [np.column_stack([pts[:, 0], pts[:, 1], np.full(4, z)])
                for z in (Z_FACE + 1, Z_FACE + 19)]
        parts.append(loft_quads(secs))
    return parts


RIB_YS = PUMP['rib_ys']               # gusset positions (tube exists here)
RIB_T = 6.0                            # rib thickness
RIB_SLOPE = np.tan(np.radians(55))     # steeper than 45: shorter reach


def corbel():
    """Ribbed gussets from the riser wall to the fan-root underside.

    Replaces the old solid web: same load path (fan-root bending sheared
    into the riser tube), ~1/5 the visual bulk. Each rib's inner edge sits
    at the local tube surface x(y); 55-deg hypotenuse self-supports and
    the 12-18mm bays between ribs bridge cleanly."""
    o, tv, n = frame(L_PRE + ARC_LEN)
    _, w, area, _ = section_profile(L_PRE + ARC_LEN)
    h0, _ = roof_shape(np.zeros(1), 0.0, w, area)
    z_top = float((o - n * (h0 / 2 + WALL))[2]) + 1.5
    z_low = Z_JOIN + 2
    r_tube = BORE / 2 + WALL
    ribs = []
    for yk in RIB_YS:
        xi = float(np.sqrt(max(r_tube**2 - yk**2, 25.0))) - 1.5
        x_reach = xi + (z_top - z_low) / RIB_SLOPE
        tri = np.array([[xi, z_low], [x_reach, z_top], [xi, z_top]])
        secs = [np.column_stack([tri[:, 0], np.full(3, yy), tri[:, 1]])
                for yy in (yk - RIB_T / 2, yk + RIB_T / 2)]
        ribs.append(loft_quads(secs))
    return ribs


def bool_op(op, meshes):
    return trimesh.boolean.boolean_manifold(meshes, op)


def main():
    cage = trimesh.load(os.path.join(HERE, PUMP['cage']))
    z0, z1 = PUMP['spike_z']
    spike = trimesh.creation.cylinder(radius=PUMP['spike_r'],
                                      height=z1 - z0, sections=96)
    spike.apply_translation([0, 0, (z0 + z1) / 2])
    cage = bool_op('difference', [cage, spike])

    cavity = duct_loft(0.0, ext=WALL + 2)
    outer = duct_loft(WALL, ext=0.0)
    shell = bool_op('difference', [bool_op('union', [outer] + corbel()), cavity])

    internals = fan_vanes() + straighteners()
    internals = [bool_op('intersection', [p, cavity]) for p in internals]

    final = bool_op('union', [cage, shell] + internals)
    print('final: watertight', final.is_watertight,
          'faces', len(final.faces),
          'volume', round(final.volume / 1000, 1), 'cm3')
    v = final.vertices
    print(f'envelope x {v[:,0].min():.0f}..{v[:,0].max():.0f} '
          f'y {v[:,1].min():.0f}..{v[:,1].max():.0f} z 0..{v[:,2].max():.0f}')
    final.export(os.path.join(HERE, PUMP['out']))
    print('exported', PUMP['out'])

    nrm = final.face_normals
    area = final.area_faces
    ctr = final.triangles_center
    bad = (nrm[:, 2] < -np.cos(np.radians(50))) & (ctr[:, 2] > 2.0)
    print(f'overhang >50deg: {area[bad].sum():.0f} mm2 '
          f'({100 * area[bad].sum() / area.sum():.1f}% of surface)')


if __name__ == '__main__':
    main()
