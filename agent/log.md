# MP60 shroud optimization log

seeded: [{"params": {"bend_r": 52, "duct_h": 45, "fan_len": 70, "exit_w": 185, "area_ratio": 1.19, "n_vanes": 4, "exp": 1.5}, "score": 0.3944, "metrics": {"K_loss": 0.20199999999999999, "Q_lps": 5.34, "v_exit": 1.114, "exit_h": 25.9, "spread": 45.7, "outfrac": 0.388, "plan_uni": 1.017}, "tag": "seed_S5_swept_0v"}]

## round 1  (18:46)
proposer: qwen. Candidates include variants near the historical best (bend_r=55, exit_w=200) and explore extremes like narrow exits (exit_w=120) and high tilt (30°). Prioritizes improving K and spread through parameter diversification.
8 sims in 15.5 min
- r1c0 {"bend_r": 55.0, "duct_h": 48.0, "fan_len": 75.0, "exit_w": 200.0, "area_ratio": 1.2, "n_vanes": 5, "exp": 1.6, "tilt": 10.0} -> score=0.293 {"K_loss": 0.19, "Q_lps": 5.35, "v_exit": 1.107, "exit_h": 24.2, "spread": 42.0, "outfrac": 0.236, "plan_uni": 1.294}
- r1c1 {"bend_r": 60.0, "duct_h": 50.0, "fan_len": 80.0, "exit_w": 260, "area_ratio": 1.4, "n_vanes": 6, "exp": 2.5, "tilt": 20.0} -> score=0.2945 {"K_loss": 0.17844444444444443, "Q_lps": 5.36, "v_exit": 0.951, "exit_h": 21.7, "spread": 62.9, "outfrac": 0.705, "plan_uni": 1.46}
- r1c2 {"bend_r": 45.0, "duct_h": 36, "fan_len": 55, "exit_w": 120, "area_ratio": 1.0, "n_vanes": 2, "exp": 1.2, "tilt": 0} -> score=0.2774 {"K_loss": 0.17, "Q_lps": 5.37, "v_exit": 1.333, "exit_h": 33.6, "spread": 22.1, "outfrac": 0.021, "plan_uni": 0.655}
- r1c3 {"bend_r": 65.0, "duct_h": 55.0, "fan_len": 100.0, "exit_w": 180.0, "area_ratio": 1.45, "n_vanes": 3, "exp": 2.0, "tilt": 15.0} -> score=0.1976 {"K_loss": 0.2555, "Q_lps": 5.3, "v_exit": 0.907, "exit_h": 32.4, "spread": 35.2, "outfrac": 0.144, "plan_uni": 1.212}
best so far: seed_S5_swept_0v score=0.3944

## round 2  (19:04)
proposer: qwen. Explored variants near the top-performing exit_w=185 with adjusted spread and tilt, while testing extreme exit_w=260 (sheet jet) and tilt=35 (floor-targeting) to explore uncharted regions.
8 sims in 15.2 min
- r2c0 {"bend_r": 52.0, "duct_h": 45.0, "fan_len": 70.0, "exit_w": 190.0, "area_ratio": 1.2, "n_vanes": 4, "exp": 1.6, "tilt": 5.0} -> score=0.3565 {"K_loss": 0.22061111111111112, "Q_lps": 5.32, "v_exit": 1.102, "exit_h": 25.4, "spread": 43.5, "outfrac": 0.31, "plan_uni": 1.054}
- r2c1 {"bend_r": 50.0, "duct_h": 44.0, "fan_len": 65.0, "exit_w": 180.0, "area_ratio": 1.15, "n_vanes": 4, "exp": 1.4, "tilt": 0} -> score=0.4189 {"K_loss": 0.146, "Q_lps": 5.39, "v_exit": 1.163, "exit_h": 25.7, "spread": 45.8, "outfrac": 0.457, "plan_uni": 0.993}
- r2c2 {"bend_r": 60.0, "duct_h": 50.0, "fan_len": 80.0, "exit_w": 260, "area_ratio": 1.4, "n_vanes": 6, "exp": 2.5, "tilt": 20.0} -> score=0.2945 {"K_loss": 0.17844444444444443, "Q_lps": 5.36, "v_exit": 0.951, "exit_h": 21.7, "spread": 62.9, "outfrac": 0.705, "plan_uni": 1.46}
- r2c3 {"bend_r": 44, "duct_h": 36, "fan_len": 55, "exit_w": 120, "area_ratio": 1.0, "n_vanes": 2, "exp": 1.2, "tilt": 35} -> score=0.2716 {"K_loss": 0.2361111111111111, "Q_lps": 5.31, "v_exit": 1.319, "exit_h": 33.6, "spread": 22.1, "outfrac": 0.021, "plan_uni": 0.655}
best so far: r2c1 score=0.4189

## round 3  (19:22)
proposer: qwen. The best historical candidate (score 0.4189) is near the lower bend_r/duct_h range with moderate exit_w. Exploration candidates test higher exit_w (gyre-like sheet), increased tilt (detritus sweeping), and extreme area_ratio/n_vanes combinations. The fourth candidate probes unexplored low-bend_r/duct_h territory with balanced parameters.
8 sims in 14.1 min
- r3c0 {"bend_r": 50.0, "duct_h": 44.0, "fan_len": 65.0, "exit_w": 180.0, "area_ratio": 1.15, "n_vanes": 4, "exp": 1.4, "tilt": 0} -> score=0.4189 {"K_loss": 0.146, "Q_lps": 5.39, "v_exit": 1.163, "exit_h": 25.7, "spread": 45.8, "outfrac": 0.457, "plan_uni": 0.993}
- r3c1 {"bend_r": 55.0, "duct_h": 48.0, "fan_len": 75.0, "exit_w": 220.0, "area_ratio": 1.3, "n_vanes": 5, "exp": 1.8, "tilt": 15.0} -> score=0.2433 {"K_loss": 0.1995, "Q_lps": 5.34, "v_exit": 1.02, "exit_h": 23.8, "spread": 42.1, "outfrac": 0.196, "plan_uni": 1.414}
- r3c2 {"bend_r": 65.0, "duct_h": 55.0, "fan_len": 100.0, "exit_w": 150.0, "area_ratio": 1.45, "n_vanes": 3, "exp": 2.2, "tilt": 25.0} -> score=0.1854 {"K_loss": 0.2798333333333333, "Q_lps": 5.28, "v_exit": 0.904, "exit_h": 38.9, "spread": 28.8, "outfrac": 0.075, "plan_uni": 0.924}
- r3c3 {"bend_r": 48.0, "duct_h": 40.0, "fan_len": 80.0, "exit_w": 200.0, "area_ratio": 1.25, "n_vanes": 6, "exp": 2.0, "tilt": 10.0} -> score=0.348 {"K_loss": 0.2677777777777778, "Q_lps": 5.29, "v_exit": 1.05, "exit_h": 25.2, "spread": 52.8, "outfrac": 0.501, "plan_uni": 1.189}
best so far: r2c1 score=0.4189

## round 4  (19:37)
proposer: qwen. Top candidates cluster near the best historical score (0.4189) with slight parameter adjustments. Unexplored regions include low-exit_w (130) and high-tilt (30), testing detritus-sweeping potential. Area_ratio and exp variations aim to balance jet coherence (exp=1.3-2.4) with flow spread (spread=22-63).
8 sims in 15.4 min
- r4c0 {"bend_r": 52.0, "duct_h": 46.0, "fan_len": 68.0, "exit_w": 185.0, "area_ratio": 1.18, "n_vanes": 4, "exp": 1.5, "tilt": 2.0} -> score=0.3508 {"K_loss": 0.16355555555555557, "Q_lps": 5.37, "v_exit": 1.131, "exit_h": 25.7, "spread": 39.9, "outfrac": 0.296, "plan_uni": 1.03}
- r4c1 {"bend_r": 58.0, "duct_h": 48.0, "fan_len": 72.0, "exit_w": 190.0, "area_ratio": 1.22, "n_vanes": 5, "exp": 1.6, "tilt": 10.0} -> score=0.2413 {"K_loss": 0.1811111111111111, "Q_lps": 5.36, "v_exit": 1.091, "exit_h": 25.9, "spread": 37.4, "outfrac": 0.142, "plan_uni": 1.238}
- r4c2 {"bend_r": 46.0, "duct_h": 38.0, "fan_len": 60.0, "exit_w": 130.0, "area_ratio": 1.05, "n_vanes": 3, "exp": 1.3, "tilt": 30.0} -> score=0.2484 {"K_loss": 0.2293333333333333, "Q_lps": 5.32, "v_exit": 1.258, "exit_h": 32.5, "spread": 23.3, "outfrac": 0.025, "plan_uni": 0.791}
- r4c3 {"bend_r": 62.0, "duct_h": 52.0, "fan_len": 90.0, "exit_w": 250.0, "area_ratio": 1.4, "n_vanes": 6, "exp": 2.4, "tilt": 25.0} -> score=0.3017 {"K_loss": 0.1878333333333333, "Q_lps": 5.35, "v_exit": 0.949, "exit_h": 22.5, "spread": 56.6, "outfrac": 0.622, "plan_uni": 1.368}
best so far: r2c1 score=0.4189
plateau -> stopping tier A early

## tier B: tank-scale gyre sims
- tank_sheet_shallow: r2c1 exit 180.0x26mm v_exit=1.163m/s
- tank_sheet_steep: r4c3 exit 250.0x23mm v_exit=0.949m/s
- tank_diffuse_shallow: r1c2 exit 120x34mm v_exit=1.333m/s
- tank_sheet_shallow -> {"coral_mean_u": 0.0012, "coral_frac_gt_10pct": 0.0, "coral_frac_gt_25pct": 0.0, "wall_arrival_u": 0.0, "gyre_index": 0.0157, "floor_sweep_u": 0.0485, "rock_wrap_u": 0.0691, "lee_dead_frac": 1.0, "tank_mean_u": 0.0946, "name": "tank_sheet_shallow"}
- tank_sheet_steep -> {"coral_mean_u": 0.0026, "coral_frac_gt_10pct": 0.0, "coral_frac_gt_25pct": 0.0, "wall_arrival_u": 0.0001, "gyre_index": 0.0071, "floor_sweep_u": 0.071, "rock_wrap_u": 0.0719, "lee_dead_frac": 1.0, "tank_mean_u": 0.0782, "name": "tank_sheet_steep"}
- tank_diffuse_shallow -> {"coral_mean_u": 0.0052, "coral_frac_gt_10pct": 0.0, "coral_frac_gt_25pct": 0.0, "wall_arrival_u": 0.0001, "gyre_index": -0.0014, "floor_sweep_u": 0.0363, "rock_wrap_u": 0.0984, "lee_dead_frac": 0.995, "tank_mean_u": 0.1117, "name": "tank_diffuse_shallow"}

## VERDICT: {"winner": "sheet_steep", "why": "sheet_steep has the highest floor_sweep_u (0.071), meeting the first goal. While its rock_wrap_u (0.0719) is moderate and lee_dead_frac (1.0) is high, it's the best among options for the first priority. Gyre_index and wall_arrival_u are lower than sheet_shallow, but secondary goals are less critical."}

DONE. best.json written -- feed to build_v3.py
