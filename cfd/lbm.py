#!/usr/bin/env python3
"""2D lattice-Boltzmann (D2Q9 + Smagorinsky LES) for the MP60 shroud.

Two planes:
  side : meridional slice of the 90-degree elbow (separation / turning loss)
  plan : top view of the fan diffuser (arc spread / vane camber)

Fidelity note: 2D slices with an LES closure give trend-level answers --
relative loss coefficients, separation zones, exit uniformity -- which is
what's needed to rank geometry variants. Not absolute-accurate CFD.

Usage: lbm.py <variant-name>   (see VARIANTS at bottom)
"""
import json
import sys

import numpy as np

RES = 0.4          # mm per lattice cell
U0 = 0.05          # lattice inlet speed (mean); parabolic profile peaks 1.5x
RAMP = 6000        # soft-start steps
RE = 5000.0        # Reynolds number on bore diameter (LES-stabilized;
                   # real flow ~2e4 -- rankings transfer, absolutes indicative)
CSM = 0.14         # Smagorinsky constant
BORE = 71.6        # MP60 cage discharge bore, mm (measured from 3MF)

C = np.array([(0,0),(1,0),(0,1),(-1,0),(0,-1),(1,1),(-1,1),(-1,-1),(1,-1)])
W = np.array([4/9] + [1/9]*4 + [1/36]*4)
OPP = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])


def feq(rho, ux, uy):
    cu = 3.0 * (C[:, 0, None, None] * ux + C[:, 1, None, None] * uy)
    usq = 1.5 * (ux * ux + uy * uy)
    return W[:, None, None] * rho * (1.0 + cu + 0.5 * cu * cu - usq)


def edge_feq(ux1, uy1):
    cu = 3.0 * (C[:, 0, None] * ux1 + C[:, 1, None] * uy1)
    usq = 1.5 * (ux1 * ux1 + uy1 * uy1)
    return (W[:, None] * (1.0 + cu + 0.5 * cu * cu - usq)).astype(np.float32)


def run(name, cfg):
    fluid, inlet, outlet_axis, extent = build_geometry(cfg)
    for axis, side in cfg['open_edges']:
        edge = fluid[:, -1] if axis == 'x' else (fluid[-1] if side > 0 else fluid[0])
        assert edge.any(), f'open edge {axis}{side} has no fluid cells'
    ny, nx = fluid.shape
    solid = ~fluid
    # half-way bounce-back masks: nb_solid[i] = the upstream neighbor in
    # direction i is a wall, so reflect in place instead of streaming.
    # Mass can then only enter/leave through the inlet/outlet BCs.
    nb_solid = np.stack([np.roll(solid, (C[i, 1], C[i, 0]), axis=(0, 1))
                         for i in range(9)])
    nu = U0 * (BORE / RES) / cfg.get('re', RE)
    tau0 = 0.5 + 3.0 * nu
    print(f'[{name}] grid {nx}x{ny}, tau0={tau0:.5f}', flush=True)

    rho = np.ones((ny, nx), np.float32)
    ux = np.zeros((ny, nx), np.float32)
    uy = np.zeros((ny, nx), np.float32)
    f = feq(rho, ux, uy).astype(np.float32)

    steps = cfg.get('steps', 30000)
    warm = int(steps * 0.6)
    acc = {'n': 0, 'ux': np.zeros_like(ux), 'uy': np.zeros_like(uy),
           'rho': np.zeros_like(rho)}

    iy, ix = inlet
    prof = cfg['inlet_prof']          # per-inlet-cell parabolic weights
    act = cfg.get('actuator')
    slip_top = cfg.get('slip_top', False)
    for it in range(steps):
        rho = np.maximum(f.sum(0), 0.2)
        ux = (f * C[:, 0, None, None]).sum(0) / rho
        uy = (f * C[:, 1, None, None]).sum(0) / rho
        ux[solid] = 0; uy[solid] = 0

        fe = feq(rho, ux, uy)
        fneq = f - fe
        pxx = (C[:, 0, None, None]**2 * fneq).sum(0)
        pyy = (C[:, 1, None, None]**2 * fneq).sum(0)
        pxy = (C[:, 0, None, None] * C[:, 1, None, None] * fneq).sum(0)
        q = np.sqrt(pxx**2 + pyy**2 + 2 * pxy**2)
        tau = 0.5 * (tau0 + np.sqrt(tau0**2 + 18.0 * (CSM**2) * q / rho))
        f += (fe - f) / tau

        post = f.copy()
        for i in range(1, 9):
            rolled = np.roll(post[i], (C[i, 1], C[i, 0]), axis=(0, 1))
            f[i] = np.where(nb_solid[i], post[OPP[i]], rolled)

        if slip_top:
            # specular free surface on the top row: reflect vertical only
            tr = ny - 1
            f[4, tr, :] = post[2, tr, :]
            f[7, tr, :] = post[6, tr, :]
            f[8, tr, :] = post[5, tr, :]
        if prof is not None:
            # inlet: equilibrium, parabolic profile, soft start
            amp = U0 * min(1.0, (it + 1) / RAMP)
            uin_x = (cfg['u_in'][0] * amp * prof).astype(np.float32)
            uin_y = (cfg['u_in'][1] * amp * prof).astype(np.float32)
            rho1 = np.ones_like(prof, np.float32)
            cu = 3.0 * (C[:, 0, None] * uin_x + C[:, 1, None] * uin_y)
            usq = 1.5 * (uin_x**2 + uin_y**2)
            f[:, iy, ix] = W[:, None] * rho1 * (1.0 + cu + 0.5 * cu * cu - usq)
        if act is not None:
            # actuator disc: local density, forced velocity -> conserves mass
            ay, ax_ = act
            amp = cfg.get('u_jet', U0) * min(1.0, (it + 1) / RAMP)
            dx_, dy_ = cfg.get('act_dir', (-1.0, 0.0))
            ra = rho[ay, ax_].astype(np.float32)
            cu = 3.0 * (C[:, 0, None] * (amp * dx_) + C[:, 1, None] * (amp * dy_))
            f[:, ay, ax_] = (W[:, None] * ra * (1.0 + cu + 0.5 * cu * cu
                             - 1.5 * amp * amp)).astype(np.float32)
        # open boundaries: fixed-pressure (rho=1) equilibrium outlet with
        # the neighbor's velocity, outward component clipped >= 0
        for axis, side in cfg['open_edges']:
            if axis == 'x':
                uxs, uys = ux[:, -3].copy(), uy[:, -3].copy()
                if side > 0: uxs = np.maximum(uxs, 0)
                fo = edge_feq(uxs, uys)
                f[:, :, -2] = fo; f[:, :, -1] = fo
            elif side > 0:
                uxs, uys = ux[-3, :].copy(), np.maximum(uy[-3, :], 0)
                fo = edge_feq(uxs, uys)
                f[:, -2, :] = fo; f[:, -1, :] = fo
            else:
                uxs, uys = ux[2, :].copy(), np.minimum(uy[2, :], 0)
                fo = edge_feq(uxs, uys)
                f[:, 1, :] = fo; f[:, 0, :] = fo

        if it >= warm and it % 10 == 0:
            acc['n'] += 1
            acc['ux'] += ux; acc['uy'] += uy; acc['rho'] += rho
        if it % 4000 == 0:
            umax = float(np.hypot(ux, uy).max())
            print(f'[{name}] step {it} umax={umax:.3f}', flush=True)
            if not np.isfinite(umax) or umax > 0.6:
                print(f'[{name}] DIVERGED', flush=True); return

    for k in ('ux', 'uy', 'rho'):
        acc[k] /= acc['n']
    metrics = cfg['metrics_fn'](acc, fluid, cfg, extent)
    metrics['name'] = name
    with open(f'{name}.json', 'w') as fh:
        json.dump(metrics, fh, indent=1)
    np.savez_compressed(f'{name}.npz', ux=acc['ux'], uy=acc['uy'],
                        rho=acc['rho'], fluid=fluid, extent=np.array(extent))
    plot(name, acc, fluid, extent)
    print(f'[{name}] done: {json.dumps(metrics)}', flush=True)


def plot(name, acc, fluid, extent):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    um = np.hypot(acc['ux'], acc['uy']) / U0
    um[~fluid] = np.nan
    fig, ax = plt.subplots(figsize=(11, 7), dpi=110)
    im = ax.imshow(um, origin='lower', extent=extent, cmap='turbo',
                   vmin=0, vmax=1.6)
    ny, nx = fluid.shape
    xs = np.linspace(extent[0], extent[1], nx)
    ys = np.linspace(extent[2], extent[3], ny)
    ax.streamplot(xs, ys, acc['ux'], acc['uy'], color='w', linewidth=0.5,
                  density=1.6, arrowsize=0.7)
    ax.contourf(xs, ys, (~fluid).astype(float), levels=[0.5, 1.5],
                colors=['#404040'])
    ax.set_title(f'{name}  |u|/U0 time-averaged')
    ax.set_xlabel('mm'); ax.set_ylabel('mm')
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(f'{name}.png')
    plt.close(fig)


# ---------------- geometry ----------------

def mm_grid(xmin, xmax, ymin, ymax):
    nx = int((xmax - xmin) / RES)
    ny = int((ymax - ymin) / RES)
    x = xmin + (np.arange(nx) + 0.5) * RES
    y = ymin + (np.arange(ny) + 0.5) * RES
    X, Y = np.meshgrid(x, y)
    return X, Y, (xmin, xmax, ymin, ymax)


def build_geometry(cfg):
    return cfg['geom_fn'](cfg)


def geom_side(cfg):
    br, dh, il, fl, eh = (cfg[k] for k in ('bend_r', 'duct_h', 'inlet_len',
                                           'fan_len', 'exit_h'))
    hb = cfg.get('entry_w', BORE) / 2
    X, Y, ext = mm_grid(-hb - 10, br + fl + 1.0, 0, il + br + dh / 2 + 10)

    inlet_rect = (np.abs(X) <= hb) & (Y <= il)
    dx, dy = X - br, Y - il
    r = np.hypot(dx, dy)
    phi = np.degrees(np.arctan2(dy, dx)) % 360
    t = np.clip((180 - phi) / 90, 0, 1)
    h = 2 * hb + (dh - 2 * hb) * t
    in_bend = (phi >= 90) & (phi <= 180) & (r >= br - h/2) & (r <= br + h/2)
    floor = il + br - dh / 2
    ceil = il + br + dh / 2 - (dh - eh) * np.clip((X - br) / fl, 0, 1)
    in_fan = (X >= br) & (Y >= floor) & (Y <= ceil)
    fluid = inlet_rect | in_bend | in_fan

    vt = cfg.get('vane_t', 1.8)
    for rk in cfg.get('vanes', []):
        vane = (np.abs(r - rk) <= vt/2) & (phi >= 84) & (phi <= 186)
        fluid &= ~vane

    sel = inlet_rect & (Y <= 2 * RES + 0.01)
    iy, ix = np.where(sel)
    cfg['inlet_prof'] = 1.5 * (1.0 - (X[sel] / hb)**2)
    cfg['u_in'] = (0.0, 1.0)
    cfg['open_edges'] = [('x', +1)]
    cfg['metrics_fn'] = metrics_side
    return fluid, (iy, ix), 'x', ext


def metrics_side(acc, fluid, cfg, ext):
    ny, nx = fluid.shape
    ux, uy, rho = acc['ux'], acc['uy'], acc['rho']
    xs = np.linspace(ext[0], ext[1], nx)
    ys = np.linspace(ext[2], ext[3], ny)

    def plane_tp(mask, un):
        p = rho[mask] / 3.0
        u2 = ux[mask]**2 + uy[mask]**2
        w = np.maximum(un[mask], 0) + 1e-12
        return float(((p + 0.5 * u2) * w).sum() / w.sum())

    j_in = np.searchsorted(ys, 4.0)
    in_mask = np.zeros_like(fluid); in_mask[j_in] = fluid[j_in]
    tp_in = plane_tp(in_mask, uy)
    flux_in = float((uy[j_in] * fluid[j_in]).sum() * RES)
    ub = flux_in / (fluid[j_in].sum() * RES)

    i_out = nx - 4
    out_mask = np.zeros_like(fluid); out_mask[:, i_out] = fluid[:, i_out]
    tp_out = plane_tp(out_mask, ux)
    flux_out = float((ux[:, i_out] * fluid[:, i_out]).sum() * RES)
    ue = flux_out / (fluid[:, i_out].sum() * RES)

    k_loss = (tp_in - tp_out) / (0.5 * ub**2)
    uxo = ux[:, i_out][fluid[:, i_out]]
    uni = float(np.std(uxo) / (np.abs(np.mean(uxo)) + 1e-12))
    rev = float((uxo < 0).mean())
    interior = fluid.copy(); interior[:, :np.searchsorted(xs, 0)] = False
    sep = float(((ux < -0.05 * U0) & interior).sum() * RES**2)
    return {'K_loss': round(k_loss, 3),
            'exit_net_u': round(ue / U0, 3),
            'mass_balance': round(flux_out / (flux_in + 1e-12), 3),
            'exit_nonuniformity': round(uni, 3),
            'exit_reversed_frac': round(rev, 3),
            'separation_area_mm2': round(sep, 0)}


def geom_miter(cfg):
    """Mitered 90-degree corner with quarter-arc louver blades.

    Vertical inlet (width = duct depth DD after the circle->rect morph,
    modeled 2D from the morph exit), 45-degree diagonal back wall,
    horizontal duct of height H, blades = arcs centered on the inner
    corner. Blade arc spans theta in [90+trunc, 180] degrees.
    """
    dd, h, il, fl, eh = (cfg[k] for k in ('duct_d', 'duct_h', 'inlet_len',
                                          'fan_len', 'exit_h'))
    hb = dd / 2
    X, Y, ext = mm_grid(-hb - 8, hb + fl + 1.0, 0, il + h + 8)
    floor = il
    inlet_rect = (np.abs(X) <= hb) & (Y <= floor)
    # horizontal duct: from the diagonal back wall to the exit
    diag = (X + hb) >= (Y - floor)          # fluid on +x side of 45-deg wall
    in_duct = (Y >= floor) & (Y <= floor + h) & diag
    ceil = floor + h - (h - eh) * np.clip((X - hb) / fl, 0, 1)
    in_duct &= (Y <= ceil)
    fluid = inlet_rect | in_duct

    vt = cfg.get('vane_t', 1.8)
    trunc = cfg.get('trunc', 0)             # degrees cut off the top of blades
    r = np.hypot(X - hb, Y - floor)
    th = np.degrees(np.arctan2(Y - floor, X - hb))
    for rk in cfg.get('blades', []):
        blade = (np.abs(r - rk) <= vt/2) & (th >= 90 + trunc) & (th <= 180)
        fluid &= ~blade

    sel = inlet_rect & (Y <= 2 * RES + 0.01)
    iy, ix = np.where(sel)
    cfg['inlet_prof'] = 1.5 * (1.0 - (X[sel] / hb)**2)
    cfg['u_in'] = (0.0, 1.0)
    cfg['open_edges'] = [('x', +1)]
    cfg['metrics_fn'] = metrics_side
    return fluid, (iy, ix), 'x', ext


def geom_plan(cfg):
    dw, ew, fl, p = (cfg[k] for k in ('duct_w', 'exit_w', 'fan_len', 'exp'))
    plen = cfg.get('plenum', 60)
    X, Y, ext = mm_grid(-14, fl + plen, -(ew/2 + 28), ew/2 + 28)
    fluid = np.ones_like(X, bool)

    s = np.clip(X / fl, 0, 1)
    halfw = dw/2 + (ew - dw)/2 * s**p
    wall = (X <= fl) & (np.abs(Y) >= halfw) & (np.abs(Y) <= halfw + 2.5)
    fluid &= ~wall
    duct_zone = (X <= fl) & (np.abs(Y) > halfw + 2.5)
    fluid &= ~duct_zone

    n = cfg.get('vanes', 0)
    delta = (ew - dw) / 2
    if n:
        for k in range(n):
            fk = -1 + 2 * k / (n - 1)
            y0 = fk * dw / 4
            yk = y0 + 0.5 * fk * delta * s**p
            vane = (X >= 6) & (X <= fl) & (np.abs(Y - yk) <= 1.0)
            fluid &= ~vane

    sel = (X <= ext[0] + 2 * RES + 0.01) & (np.abs(Y) < dw/2)
    iy, ix = np.where(sel)
    cfg['inlet_prof'] = 1.5 * (1.0 - (Y[sel] / (dw/2))**2)
    cfg['u_in'] = (1.0, 0.0)
    cfg['open_edges'] = [('x', +1), ('y', +1), ('y', -1)]
    cfg['metrics_fn'] = metrics_plan
    return fluid, (iy, ix), 'x', ext


def metrics_plan(acc, fluid, cfg, ext):
    ny, nx = fluid.shape
    ux, uy = acc['ux'], acc['uy']
    xs = np.linspace(ext[0], ext[1], nx)
    ys = np.linspace(ext[2], ext[3], ny)
    fl, ew = cfg['fan_len'], cfg['exit_w']

    i_exit = np.searchsorted(xs, fl + 2)
    row = fluid[:, i_exit]
    uxe = ux[:, i_exit]
    open_slot = row & (np.abs(ys) <= ew/2)
    flux = uxe[open_slot]
    uni = float(np.std(flux) / (np.abs(np.mean(flux)) + 1e-12))
    i_in = np.searchsorted(xs, -8)
    flux_in = float((ux[:, i_in] * fluid[:, i_in]).sum() * RES)
    flux_out = float(flux.sum() * RES)

    i_far = np.searchsorted(xs, fl + 40)
    uxf = np.clip(ux[:, i_far], 0, None)
    mom = uxf**2
    tot = mom.sum() + 1e-12
    frac_outside = float(mom[np.abs(ys) > cfg['duct_w']/2].sum() / tot)
    yc = float((mom * ys).sum() / tot)
    spread = float(np.sqrt((mom * (ys - yc)**2).sum() / tot))
    return {'exit_nonuniformity': round(uni, 3),
            'mass_balance': round(flux_out / (flux_in + 1e-12), 3),
            'downstream_frac_outside_duct_width': round(frac_outside, 3),
            'downstream_spread_sigma_mm': round(spread, 1),
            'centroid_offset_mm': round(yc, 1)}


VARIANTS = {
    # fair swept bends: morph done upstream, constant-height slice (area-
    # consistent 2D). Answers: does the swept bend beat the mitered corner?
    'S5_swept_0v': dict(geom_fn=geom_side, entry_w=45, bend_r=52, duct_h=45,
                        inlet_len=40, fan_len=70, exit_h=45, vanes=[]),
    'S6_swept_2v': dict(geom_fn=geom_side, entry_w=45, bend_r=52, duct_h=45,
                        inlet_len=40, fan_len=70, exit_h=45, vanes=[40, 55]),
    # mitered corner + louver cascade (the printable architecture)
    'M0_miter0':   dict(geom_fn=geom_miter, duct_d=42, duct_h=45, inlet_len=40,
                        fan_len=70, exit_h=45, blades=[]),
    'M2_miter2':   dict(geom_fn=geom_miter, duct_d=42, duct_h=45, inlet_len=40,
                        fan_len=70, exit_h=45, blades=[14, 30]),
    'M3_miter3':   dict(geom_fn=geom_miter, duct_d=42, duct_h=45, inlet_len=40,
                        fan_len=70, exit_h=45, blades=[12, 22, 34]),
    'M3_trunc':    dict(geom_fn=geom_miter, duct_d=42, duct_h=45, inlet_len=40,
                        fan_len=70, exit_h=45, blades=[12, 22, 34], trunc=25),
    # plan view: fan spread + vane camber
    'P0_novane':   dict(geom_fn=geom_plan, duct_w=95, exit_w=185, fan_len=70,
                        exp=2.0, vanes=0),
    'P1_4v_exp2':  dict(geom_fn=geom_plan, duct_w=95, exit_w=185, fan_len=70,
                        exp=2.0, vanes=4),
    'P2_4v_exp15': dict(geom_fn=geom_plan, duct_w=95, exit_w=185, fan_len=70,
                        exp=1.5, vanes=4),
    'P3_6v_exp2':  dict(geom_fn=geom_plan, duct_w=95, exit_w=185, fan_len=70,
                        exp=2.0, vanes=6),
}

def geom_tank(cfg):
    """Closed 2D side-view peninsula tank. Jet actuator = shroud exit
    (momentum source at local density -> mass-conserving); free surface
    approximated as specular slip; pump body = solid block at the
    non-wall end. Answers gyre-vs-diffuse at tank scale."""
    global RES
    RES = cfg.get('res', 1.4)
    L, H = cfg.get('tank_l', 1800), cfg.get('tank_h', 550)
    X, Y, ext = mm_grid(0, L, 0, H)
    fluid = np.ones_like(X, bool)
    fluid &= ~(X < 6); fluid &= ~(X > L - 6); fluid &= ~(Y < 6)
    # pump body (cage + wet side) at the non-wall end
    fluid &= ~((X > L - 140) & (X < L - 30) & (Y < 215))
    # rockwork: half-ellipse mounds (cx, half_w, height); the first hides
    # the pump/outlet, the second is a mid-tank bommie, third near-wall
    for cx, hw, hh in cfg.get('rocks', [(L - 420, 130, 240),
                                        (L * 0.45, 150, 300), (300, 110, 220)]):
        fluid &= ~(((X - cx) / hw) ** 2 + (Y / hh) ** 2 < 1.0)
    eh = cfg['exit_h']
    z0 = cfg.get('exit_z', 165)
    tilt = np.radians(cfg.get('tilt', 0.0))
    cfg['act_dir'] = (-float(np.cos(tilt)), -float(np.sin(tilt)))
    act = (X > L - 175) & (X < L - 160) & (Y >= z0) & (Y <= z0 + eh)
    cfg['actuator'] = np.where(act & fluid)
    cfg['inlet_prof'] = None
    cfg['u_in'] = (0.0, 0.0)
    cfg['open_edges'] = []
    cfg['slip_top'] = True
    cfg['metrics_fn'] = metrics_tank
    return fluid, (np.array([], int), np.array([], int)), 'x', ext


def metrics_tank(acc, fluid, cfg, ext):
    ny, nx = fluid.shape
    ux, uy = acc['ux'], acc['uy']
    um = np.hypot(ux, uy)
    xs = np.linspace(ext[0], ext[1], nx)
    ys = np.linspace(ext[2], ext[3], ny)
    XX, YY = np.meshgrid(xs, ys)
    uj = cfg.get('u_jet', U0)
    L = ext[1]
    coral = fluid & (XX > 100) & (XX < 900) & (YY > 30) & (YY < 350)
    wall = fluid & (XX > 30) & (XX < 200) & (YY > 40) & (YY < 300)
    bot = fluid & (YY > 15) & (YY < 70) & (XX > 200) & (XX < 1500)
    top = fluid & (YY > 380) & (YY < 520) & (XX > 200) & (XX < 1500)
    floor_band = fluid & (YY > 8) & (YY < 40) & (XX > 120) & (XX < L - 200)
    rocks = cfg.get('rocks', [(L - 420, 130, 240), (L * 0.45, 150, 300),
                              (300, 110, 220)])
    wraps, deads = [], []
    for cx, hw, hh in rocks:
        crest = fluid & (np.abs(XX - cx) < hw) & (YY > hh + 8) & (YY < hh + 70)
        lee = fluid & (XX > cx - hw - 160) & (XX < cx - hw) & (YY > 15) & (YY < hh * 0.8)
        if crest.any(): wraps.append(float(um[crest].mean() / uj))
        if lee.any(): deads.append(float((um[lee] < 0.04 * uj).mean()))
    return {
        'coral_mean_u': round(float(um[coral].mean() / uj), 4),
        'coral_frac_gt_10pct': round(float((um[coral] > 0.10 * uj).mean()), 3),
        'coral_frac_gt_25pct': round(float((um[coral] > 0.25 * uj).mean()), 3),
        'wall_arrival_u': round(float(um[wall].mean() / uj), 4),
        'gyre_index': round(float((-ux[bot].mean() + ux[top].mean()) / uj), 4),
        'floor_sweep_u': round(float(np.abs(ux[floor_band]).mean() / uj), 4),
        'rock_wrap_u': round(float(np.mean(wraps)), 4) if wraps else 0,
        'lee_dead_frac': round(float(np.mean(deads)), 3) if deads else 0,
        'tank_mean_u': round(float(um[fluid].mean() / uj), 4),
    }


if __name__ == '__main__':
    if sys.argv[1] == '--config':
        cfg = json.load(open(sys.argv[2]))
        name = cfg.pop('name')
        cfg['geom_fn'] = {'side': geom_side, 'miter': geom_miter,
                          'plan': geom_plan, 'tank': geom_tank}[cfg.pop('plane')]
        run(name, cfg)
    else:
        name = sys.argv[1]
        run(name, VARIANTS[name])
