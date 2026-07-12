#!/usr/bin/env python3
"""Aggregate variant JSONs into a comparison table + bar figure."""
import glob
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

rows = []
for p in sorted(glob.glob('*.json')):
    rows.append(json.load(open(p)))

side = [r for r in rows if r['name'].startswith(('S', 'M'))]
plan = [r for r in rows if r['name'].startswith('P')]

print(f"{'variant':14s} {'K':>7s} {'unif':>6s} {'sep mm2':>8s} {'mass':>6s}")
for r in side:
    print(f"{r['name']:14s} {r['K_loss']:7.3f} {r['exit_nonuniformity']:6.3f} "
          f"{r['separation_area_mm2']:8.0f} {r['mass_balance']:6.3f}")
print()
print(f"{'variant':14s} {'unif':>6s} {'spread':>7s} {'outfrac':>8s} {'mass':>6s}")
for r in plan:
    print(f"{r['name']:14s} {r['exit_nonuniformity']:6.3f} "
          f"{r['downstream_spread_sigma_mm']:7.1f} "
          f"{r['downstream_frac_outside_duct_width']:8.3f} {r['mass_balance']:6.3f}")

fig, axs = plt.subplots(1, 3, figsize=(15, 4.5), dpi=110)
names = [r['name'] for r in side]
axs[0].bar(names, [r['K_loss'] for r in side], color='#378ADD')
axs[0].set_title('elbow total-pressure loss K (lower = better)')
axs[1].bar(names, [r['exit_nonuniformity'] for r in side], color='#1D9E75')
axs[1].set_title('elbow exit non-uniformity (lower = better)')
pn = [r['name'] for r in plan]
axs[2].bar(pn, [r['downstream_spread_sigma_mm'] for r in plan], color='#D85A30')
axs[2].set_title('fan downstream spread sigma, mm (higher = wider arc)')
for ax in axs:
    ax.tick_params(axis='x', rotation=25)
    ax.grid(axis='y', alpha=0.3)
fig.tight_layout()
fig.savefig('comparison.png')
print('\nwrote comparison.png')
