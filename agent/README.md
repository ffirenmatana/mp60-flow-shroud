# Local optimization agent

Self-contained loop that perfects the MP60 shroud geometry using only
local hardware — no cloud tokens.

```
┌────────────────────┐    proposals+analysis   ┌───────────────────┐
│ M4 MacBook Pro     │ <────────────────────── │ M4 mini           │
│ optimizer.py       │                         │ Ollama qwen3:14b  │
│ 8x parallel LBM    │ ──────────────────────> │ 10.10.10.7:11434  │
│ sims per round     │    history JSON         └───────────────────┘
└────────────────────┘
```

## Run / resume / status

```bash
cd ~/Claude/Projects/MP60-flow-shroud/agent
../cfd-env-or-your-python optimizer.py          # runs or resumes
python3 optimizer.py --status                   # peek at state
tail -f log.md                                  # live narrative
```

State lives in `state.json`; kill and rerun anytime, it resumes.
`best.json` always holds the current winner → feed to `build_v3.py`.

## What a round does

1. qwen (mini) reads the scored history, proposes 4 candidates + a
   2-sentence analysis (logged). Fallback: local Gaussian/random proposer.
2. Each candidate → 2 sims on this Mac (elbow slice + fan plan),
   8 processes in parallel, 40k steps each.
3. Composite score = pump-derated exit momentum × arc coverage ×
   uniformity (see optimizer.py docstring for the MP60 stall model).
4. Plateau detection stops early; max 8 rounds.

## Tier B (the decider)

Top 3 aspect/tilt-distinct finalists get a 90k-step closed-tank sim:
1.8 m peninsula with rockwork (scape in front of the outlet, mid
bommie, near-wall structure), specular free surface, jet actuator at
the shroud exit angled down by the candidate's `tilt`.

Scored on: floor_sweep (detritus scouring), rock_wrap (climbing the
scape), lee_dead_frac (dead zones behind rocks), gyre_index +
wall_arrival (peninsula return loop). qwen renders the verdict;
a metric heuristic decides if it can't.

## Knobs

Env: `OPT_MAX_ROUNDS`, `OPT_N_PER_ROUND`, `OPT_SIM_STEPS`,
`OPT_TANK_STEPS`, `LOCAL_LLM_BASE`, `LOCAL_LLM_MODEL`.
Search space + physical constants at the top of optimizer.py.
Rock layout: `rocks` in `cfd/lbm.py::geom_tank` — edit to match the
real scape once it exists.
