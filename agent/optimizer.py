#!/usr/bin/env python3
"""Local CFD optimization agent for the MP60 fan shroud.

Runs entirely on this machine + the M4 mini:
  * heavy compute (lattice-Boltzmann sims) -> this MacBook Pro, parallel
  * proposal/analysis brain -> qwen3:14b via Ollama on the mini
    (LOCAL_LLM_BASE, default http://10.10.10.7:11434) -- zero cloud tokens
  * falls back to a built-in heuristic proposer if qwen is unreachable
    or emits unparseable JSON, so the loop never stalls.

Architecture under optimization (fixed by print + interface constraints):
  stock cage intake -> vertical morph -> VANELESS swept elbow with
  gothic-ridge cross-section -> widening fan with cambered vanes ->
  arched exit windows.  (Swept-vaneless beat mitered-louver K=0.20 vs
  1.29 and vaned-swept 0.61 in the seed matrix; fan vanes are kept
  because without them the fan tunnels: spread 20mm vs 46mm.)

Parameters (bounds in SPACE):
  bend_r     elbow centerline radius
  duct_h     duct height after morph
  fan_len    fan/diffuser length
  exit_w     exit arc width   <- the gyre-vs-diffuse axis
  area_ratio exit area / bore area
  n_vanes    fan splitter vanes
  exp        wall/vane camber law exponent

Scoring:
  tier A (every candidate): elbow slice sim (K, uniformity) + fan plan
  sim (spread, uniformity). Pump derating from K via a propeller-stall
  model: MP60 QD free flow 7500 GPH (7.89 L/s), bore O71.6 -> v0 1.96
  m/s at 100% (run point 70% -> 5.52 L/s), stall head ~0.40 m
  (propeller pumps die against small heads). Q = Qf*(1-dP/dPstall)^0.7.
  score = delivered exit momentum x arc-coverage x uniformity bonus.
  tier B (finalists): full 1.8 m closed-tank gyre sim -> coral-zone flow
  fraction + wall-arrival + gyre index decide gyre-vs-diffuse.

Usage:
  optimizer.py            run/resume the loop (state in state.json)
  optimizer.py --status   print current state
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFD = os.path.join(HERE, '..', 'cfd')
PY = sys.executable
RUNS = os.path.join(HERE, 'runs')
STATE_F = os.path.join(HERE, 'state.json')
LOG_F = os.path.join(HERE, 'log.md')

LLM_BASE = os.environ.get('LOCAL_LLM_BASE', 'http://10.10.10.7:11434')
LLM_MODEL = os.environ.get('LOCAL_LLM_MODEL', 'qwen3:14b')

SPACE = {
    'bend_r':     (44, 70),
    'duct_h':     (36, 56),
    'fan_len':    (55, 105),
    'exit_w':     (120, 260),
    'area_ratio': (1.00, 1.45),
    'n_vanes':    (2, 6),
    'exp':        (1.2, 2.6),
    'tilt':       (0, 35),
}
INT_KEYS = {'n_vanes'}
BORE = 71.6
BORE_AREA = 3.14159265 * (BORE / 2) ** 2      # 4026 mm^2
Q_FREE = 5.52e-3        # m^3/s at 70% drive (7500 GPH spec at 100%)
DP_STALL = 1000 * 9.81 * 0.40                 # Pa, propeller stall head
RHO = 1025.0            # saltwater

N_PER_ROUND = int(os.environ.get('OPT_N_PER_ROUND', 4))
MAX_ROUNDS = int(os.environ.get('OPT_MAX_ROUNDS', 8))
PLATEAU_EPS = 0.01      # <1% improvement over 2 rounds -> stop
SIM_STEPS = int(os.environ.get('OPT_SIM_STEPS', 40000))
TANK_STEPS = int(os.environ.get('OPT_TANK_STEPS', 90000))


# ---------------- LLM ----------------

def ask_qwen(system, user, timeout=300):
    body = json.dumps({
        'model': LLM_MODEL,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user}],
        'temperature': 0.4,
    }).encode()
    req = urllib.request.Request(
        LLM_BASE + '/v1/chat/completions', data=body,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    txt = out['choices'][0]['message']['content']
    txt = re.sub(r'<think>.*?</think>', '', txt, flags=re.S)
    m = re.search(r'\{.*\}', txt, flags=re.S)
    return json.loads(m.group(0)) if m else None


def propose_qwen(history, n):
    hist = [{'params': h['params'], 'score': h['score'],
             'K': h['metrics'].get('K_loss'),
             'spread': h['metrics'].get('spread')}
            for h in history if h.get('score') is not None]
    hist = sorted(hist, key=lambda x: -x['score'])[:14]
    sysmsg = ('You are the proposal engine of a CFD shape optimizer for a '
              'reef-pump duct. Respond with STRICT JSON only: '
              '{"candidates":[{...},...],"analysis":"<=3 sentences"}. '
              'Each candidate must contain exactly the keys ' +
              ', '.join(SPACE) + '. Higher score is better. Explore AND '
              'exploit: at least one candidate near the best, one testing '
              'an unexplored region. exit_w is the sheet-vs-diffuse axis: '
              'wide+thin exit = gyre-like sheet, narrow+tall = diffuse. '
              'tilt aims the jet at the tank floor (detritus sweeping); '
              'the outlet sits behind rockwork the flow must wrap over.')
    user = json.dumps({'bounds': SPACE, 'history': hist, 'propose_n': n})
    got = ask_qwen(sysmsg, user)
    cands = []
    for c in (got or {}).get('candidates', []):
        try:
            cands.append(clip(c))
        except Exception:
            pass
    return cands[:n], (got or {}).get('analysis', '')


def clip(c):
    out = {}
    for k, (lo, hi) in SPACE.items():
        v = float(c[k])
        v = max(lo, min(hi, v))
        out[k] = int(round(v)) if k in INT_KEYS else round(v, 2)
    return out


def propose_fallback(history, n, seed):
    import random
    rnd = random.Random(seed)
    best = max([h for h in history if h.get('score') is not None],
               key=lambda h: h['score'], default=None)
    cands = []
    for i in range(n):
        c = {}
        for k, (lo, hi) in SPACE.items():
            if best and i < n - 1:
                span = (hi - lo) * 0.12
                c[k] = best['params'][k] + rnd.gauss(0, span)
            else:
                c[k] = lo + rnd.random() * (hi - lo)
        cands.append(clip(c))
    return cands


# ---------------- sims + scoring ----------------

def sim_cfgs(p, tag):
    side = {'name': f'{tag}_side', 'plane': 'side', 'entry_w': p['duct_h'],
            'bend_r': p['bend_r'], 'duct_h': p['duct_h'], 'inlet_len': 40,
            'fan_len': p['fan_len'], 'exit_h': p['duct_h'], 'vanes': [],
            'steps': SIM_STEPS}
    exit_h = max(12.0, p['area_ratio'] * BORE_AREA / p['exit_w'])
    plan = {'name': f'{tag}_plan', 'plane': 'plan', 'duct_w': 95,
            'exit_w': p['exit_w'], 'fan_len': p['fan_len'], 'exp': p['exp'],
            'vanes': p['n_vanes'], 'steps': SIM_STEPS}
    return side, plan, exit_h


def run_sims(cfgs):
    procs = []
    for cfg in cfgs:
        cp = os.path.join(RUNS, cfg['name'] + '.cfg.json')
        json.dump(cfg, open(cp, 'w'))
        log = open(os.path.join(RUNS, cfg['name'] + '.log'), 'w')
        procs.append(subprocess.Popen(
            [PY, os.path.join(CFD, 'lbm.py'), '--config', cp],
            cwd=RUNS, stdout=log, stderr=subprocess.STDOUT))
    for pr in procs:
        pr.wait()


def load_metrics(name):
    p = os.path.join(RUNS, name + '.json')
    return json.load(open(p)) if os.path.exists(p) else None


def score(p, side_m, plan_m):
    if not side_m or not plan_m:
        return None, {}
    if not (0.9 < side_m.get('mass_balance', 0) < 1.1):
        return None, {}
    K = side_m['K_loss']
    if K > 10 or K < -1:
        return None, {'unconverged_K': K}
    # extra turn arc for the floor-directed tilt (bend sim runs 90 deg)
    K = K * (90 + p.get('tilt', 0)) / 90
    # pump derating (propeller stall model)
    q = Q_FREE
    for _ in range(6):
        v = q / (BORE_AREA * 1e-6)
        dp = max(0.0, K) * 0.5 * RHO * v * v
        q = Q_FREE * max(0.05, 1 - dp / DP_STALL) ** 0.7
    exit_h = max(12.0, p['area_ratio'] * BORE_AREA / p['exit_w'])
    a_exit = p['exit_w'] * exit_h * 1e-6
    v_exit = q / a_exit
    mom = q * v_exit                       # N/rho, delivered momentum flux
    arc = min(1.0, plan_m['downstream_frac_outside_duct_width'] / 0.35) \
        if plan_m['downstream_frac_outside_duct_width'] < 0.35 else 1.0
    arc *= min(1.0, plan_m['downstream_spread_sigma_mm'] / 45.0)
    uni = 1.0 / (1.0 + 0.5 * plan_m['exit_nonuniformity'])
    s = mom * (0.5 + 0.5 * arc) * uni * 100
    detail = {'K_loss': K, 'Q_lps': round(q * 1000, 2),
              'v_exit': round(v_exit, 3), 'exit_h': round(exit_h, 1),
              'spread': plan_m['downstream_spread_sigma_mm'],
              'outfrac': plan_m['downstream_frac_outside_duct_width'],
              'plan_uni': plan_m['exit_nonuniformity']}
    return round(float(s), 4), detail


# ---------------- main loop ----------------

def log_md(txt):
    with open(LOG_F, 'a') as fh:
        fh.write(txt + '\n')
    print(txt, flush=True)


def seed_history():
    """Fold the hand-run seed matrix into round-0 history (unscored
    composites, but they anchor qwen's picture of the landscape)."""
    hist = []
    seeds = {
        'S5_swept_0v': dict(bend_r=52, duct_h=45, fan_len=70, exit_w=185,
                            area_ratio=1.19, n_vanes=4, exp=1.5),
    }
    for name, p in seeds.items():
        sm = json.load(open(os.path.join(CFD, name + '.json')))
        pm = json.load(open(os.path.join(CFD, 'P2_4v_exp15.json')))
        pm = {**pm, 'downstream_spread_sigma_mm': pm['downstream_spread_sigma_mm'],
              'downstream_frac_outside_duct_width': pm['downstream_frac_outside_duct_width']}
        s, d = score(p, sm, pm)
        hist.append({'params': p, 'score': s, 'metrics': d,
                     'tag': 'seed_' + name})
    return hist


def main():
    os.makedirs(RUNS, exist_ok=True)
    if os.path.exists(STATE_F):
        state = json.load(open(STATE_F))
    else:
        state = {'round': 0, 'history': seed_history(), 'best': None}
        log_md('# MP60 shroud optimization log\n')
        log_md(f'seeded: {json.dumps(state["history"], default=str)[:400]}')

    if '--status' in sys.argv:
        print(json.dumps(state, indent=1)[:2000]); return

    while state['round'] < MAX_ROUNDS:
        rnd = state['round'] + 1
        log_md(f'\n## round {rnd}  ({time.strftime("%H:%M")})')
        try:
            cands, analysis = propose_qwen(state['history'], N_PER_ROUND)
            src = 'qwen'
        except Exception as e:
            cands, analysis = [], f'(qwen unavailable: {e})'
            src = 'fallback'
        if len(cands) < N_PER_ROUND:
            cands += propose_fallback(state['history'],
                                      N_PER_ROUND - len(cands), seed=rnd)
        log_md(f'proposer: {src}. {analysis}')

        cfgs, metas = [], []
        for i, p in enumerate(cands):
            tag = f'r{rnd}c{i}'
            side, plan, _ = sim_cfgs(p, tag)
            cfgs += [side, plan]
            metas.append((tag, p))
        t0 = time.time()
        run_sims(cfgs)
        log_md(f'{len(cfgs)} sims in {(time.time()-t0)/60:.1f} min')

        for tag, p in metas:
            s, d = score(p, load_metrics(f'{tag}_side'),
                         load_metrics(f'{tag}_plan'))
            state['history'].append(
                {'params': p, 'score': s, 'metrics': d, 'tag': tag})
            log_md(f'- {tag} {json.dumps(p)} -> score={s} {json.dumps(d)}')

        scored = [h for h in state['history'] if h.get('score')]
        best = max(scored, key=lambda h: h['score'])
        state['best'] = best
        state['round'] = rnd
        json.dump(state, open(STATE_F, 'w'), indent=1)
        json.dump(best, open(os.path.join(HERE, 'best.json'), 'w'), indent=1)
        log_md(f'best so far: {best["tag"]} score={best["score"]}')

        if rnd >= 4:
            recent = sorted((h['score'] for h in scored), reverse=True)
            older = [h['score'] for h in scored[:-2 * N_PER_ROUND]]
            if older and recent[0] <= max(older) * (1 + PLATEAU_EPS):
                log_md('plateau -> stopping tier A early')
                break

    # ---- tier B: tank-scale gyre vs diffuse on aspect-distinct finalists
    scored = sorted([h for h in state['history'] if h.get('score')],
                    key=lambda h: -h['score'])
    finalists, seen = [], set()
    for h in scored:
        aspect = ('sheet' if h['params']['exit_w'] >= 180 else 'diffuse') \
            + ('_steep' if h['params'].get('tilt', 0) >= 18 else '_shallow')
        if aspect not in seen:
            finalists.append((aspect, h)); seen.add(aspect)
        if len(finalists) == 3:
            break
    log_md('\n## tier B: tank-scale gyre sims')
    cfgs = []
    for aspect, h in finalists:
        exit_h = max(12.0, h['params']['area_ratio'] * BORE_AREA
                     / h['params']['exit_w'])
        cfgs.append({'name': f'tank_{aspect}', 'plane': 'tank',
                     'exit_h': exit_h, 'u_jet': 0.06, 're': 4000,
                     'steps': TANK_STEPS, 'tilt': h['params'].get('tilt', 0),
                     'exit_z': 165})
        log_md(f'- tank_{aspect}: {h["tag"]} exit {h["params"]["exit_w"]}x'
               f'{exit_h:.0f}mm v_exit={h["metrics"]["v_exit"]}m/s')
    run_sims(cfgs)
    for aspect, h in finalists:
        m = load_metrics(f'tank_{aspect}')
        log_md(f'- tank_{aspect} -> {json.dumps(m)}')
        h['tank'] = m
    # qwen writes the verdict; heuristics decide if it cannot
    try:
        verdict = ask_qwen(
            'You are a reef flow expert. STRICT JSON: '
            '{"winner":"<one of the given keys>","why":"<=4 sentences"}. '
            'Goals, in order: (1) floor_sweep_u high -- the jet must scour '
            'detritus off the bottom; (2) rock_wrap_u high and '
            'lee_dead_frac low -- flow must climb over the rockwork in '
            'front of the outlet; (3) gyre_index and wall_arrival_u high '
            '-- broad return to the wall end of the peninsula.',
            json.dumps({a: h.get('tank') for a, h in finalists}))
    except Exception:
        verdict = None
    if not verdict:
        fs = {a: (h['tank'].get('floor_sweep_u', 0) + h['tank'].get('rock_wrap_u', 0)
                  - h['tank'].get('lee_dead_frac', 0) + h['tank'].get('gyre_index', 0))
              for a, h in finalists if h.get('tank')}
        w = max(fs, key=fs.get)
        verdict = {'winner': w, 'why': 'heuristic: coral coverage + gyre index'}
    log_md(f'\n## VERDICT: {json.dumps(verdict)}')
    winner = dict(finalists)[verdict['winner']] if verdict['winner'] in dict(finalists) else scored[0]
    json.dump({'params': winner['params'], 'metrics': winner['metrics'],
               'tank': winner.get('tank'), 'verdict': verdict},
              open(os.path.join(HERE, 'best.json'), 'w'), indent=1)
    state['done'] = True
    json.dump(state, open(STATE_F, 'w'), indent=1)
    log_md('\nDONE. best.json written -- feed to build_v3.py')


if __name__ == '__main__':
    main()
