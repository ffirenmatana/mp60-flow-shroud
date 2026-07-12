# Reef2Reef draft — post in DIY / Members' 3D printing

**Title:** CFD-designed 3D-printed shroud turns a bottom-mounted MP60 into a
low-profile gyre for my peninsula — sim code + build recipe included

---

I have an acro-dominant peninsula and wanted serious flow at the open end
without hanging a gyre on the view panel. The plan: MP60 through the bottom
glass (bare bottom, dry side in the cabinet above the sump), with a printed
replacement for the wet-side cage that turns the vertical discharge 90° and
fans it into a wide sheet aimed back toward the wall end — hidden inside the
rockwork.

Instead of guessing the duct shape, I ended up going full nerd: a lattice-
Boltzmann CFD solver running locally, driven by an optimization loop (a local
LLM proposes candidate geometries, my machine simulates them — dozens of runs,
including full 1.8 m tank-scale sims with rockwork in them). A few results
that surprised me and might be useful to others:

- **Turning vanes made the elbow worse.** All the HVAC-style vane/louver
  designs lost badly to a plain swept bend (loss coefficient 0.19 vs 0.6–2.4).
  At powerhead scale, vane friction and wakes cost more than the separation
  they prevent.
- **The widening fan absolutely needs vanes though** — without them the flow
  tunnels straight out the middle instead of spreading into the 90° arc.
- **Where the exit sits beats how the duct is shaped.** If the outlet fires
  at rockwork taller than itself, the flow just churns in the gap and dies —
  every geometry, every time. The exit needs to clear the rock directly in
  front of it by a couple of cm. Sheet angled 15° at the floor then sweeps
  the sand and wraps over the scape; 25° just face-plants into the rock.
- The final part is 179 mm tall off the glass, keeps ~97% of the pump's flow
  (per a prop-stall derating model), prints in one piece in PETG with
  supports only under the fan, and bayonets onto the wet side exactly like
  the stock cage (the mount is the stock cage mesh from asadler99's free
  "Ecotech MP60 Cover" on Cults3D — its Private Use license means I can't
  redistribute the mesh, so the repo has a one-command script that rebuilds
  the STL from the 3MF you download from Cults yourself).

Fair warning: this is simulation-driven design, 2D slices with a turbulence
model — great for ranking shapes, not gospel for absolute numbers. It hasn't
been wet-tested yet; printing this week, will report back with PAR-meter…
sorry, flow-meter results and detritus observations.

Everything is on GitHub (the parametric generator, the CFD solver, the
whole optimization log): **https://github.com/ffirenmatana/mp60-flow-shroud**

Photos attached: the part, a cutaway of the internals, and the tank-scale
flow simulation showing the sheet wrapping over the scape.

*Suggested attachments:*
- `v3_final_180.png` (the part)
- `agent/runs/tank_hi_mid.png` (winning tank flow field)
- `agent/runs/tank_sheet_steep.png` (the "trench of doom" failure mode)
- `cfd/S5_swept_0v.png` (elbow flow field)
