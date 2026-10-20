# Albatros Model III – eVTOL powertrain sizing

Conceptual sizing tool for the energy side of a four-rotor eVTOL (two inner
rotors Ø1.47 m, two outer rotors Ø1.04 m). It takes the aircraft and mission
data from the other departments and uses them to size:

* **motors**: peak power, peak torque and **mass** (from the HPDM mass–torque fit)
* **battery**: cells in **series** (from the bus voltage) and in **parallel** (the
  smallest number that flies the mission and every emergency case), total
  cell count, energy and **mass**
* **cooling**: eight liquid loops (pumps, hoses, radiators, fans) and their mass
* **checks**: temperatures, SOC reserve, cell current and voltage, bus voltage,
  rotor tip Mach and radiator packaging, shown in a mass budget against MTOW

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

python -m albatros --mass 750                 # design for an MTOW of 750 kg
python -m albatros --torque 600               # 600 Nm motors: which MTOW can they carry?
python -m albatros --sweep 600 1200 50 --csv out/sweep.csv --save-plot out/sweep.png
python -m albatros --sweep-torque 300 900 100 --csv out/torque_sweep.csv
python -m albatros --config configs/example_department_inputs.json --json out/design.json
python -m pytest                              # run the tests
```

`python -m albatros --help` lists every option.

**New to the code? Read [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).** It
covers every module, a worked 750 kg example, battery sizing in detail, and
why the code is structured the way it is.

## Main input: MTOW *or* torque

| Mode | How | What happens |
|---|---|---|
| **MTOW-driven** (default) | `--mass 750` or `aircraft.mass_kg` | The torque each motor needs at this MTOW is computed, and the motor mass follows from the HPDM fit |
| **Torque-driven** | `--torque 600` or `motor.peak_torque_Nm > 0` | All four motors get this peak torque; the tool searches for the largest MTOW they can carry, then sizes everything else |

MTOW is the variable we optimise for. Use `--sweep` to see how battery,
motor and cooling mass, and the mass left over for the airframe, change with it.

## Inputs: who provides what

All inputs are in [`albatros/inputs.py`](albatros/inputs.py), split into two parts:

**Part A: department inputs.** These come from other teams. Don't "design" them.

| Section | Contents |
|---|---|
| `aircraft` | MTOW, rotor diameters, cruise speed, emergency rotor pairs |
| `aerodynamics` | drag: `"lift_drag"` (one L/D) or `"polar"` (`cd0`, `k_induced`, wing area) |
| `propeller` | `"constant"` (FM + cruise efficiency) or `"coefficients"` (CT/CP vs J tables) |
| `mission` | flight profile: heights, speeds, durations |

**Part B: powertrain design choices.** These are ours: `motor`, `cell`,
`battery`, `balancing`, `inverter`, `auxiliaries`, `cooling`.

Recommended workflow:

1. `python -m albatros --write-config configs/my_inputs.json` writes every input to a file.
2. Edit the file, or start from
   [`configs/example_department_inputs.json`](configs/example_department_inputs.json),
   which only lists the department values. Anything you leave out keeps its default.
3. `python -m albatros --config configs/my_inputs.json`

[`configs/legacy_model_III.json`](configs/legacy_model_III.json) reproduces the
original single-file `albatros_model_III.py` exactly (fixed 40 kg motors).

### Propeller coefficients

The standard definitions are used, with *n* in **revolutions per second**:

```
J  = V / (n D)          CT = T / (rho n² D⁴)
eta = J CT / CP         CP = P / (rho n³ D⁵)
```

The table must start at J = 0. That row gives the hover thrust coefficient
and the figure of merit, FM = CT₀^1.5 · √(2/π) / CP₀. In cruise the tool finds
the rpm that delivers the required thrust and reads the power from CP.
**The tables currently in the code are placeholders.**

### Motor mass

[`albatros/motor_family.py`](albatros/motor_family.py) fits
`m = a · T_peak^b` through the HPDM motors (≈ `0.754 · T^0.610`). The required
peak torque is the largest torque in the mission and emergency cases, times
`motor.rating_margin`. It also includes the transition, which is usually the
highest-torque point. Set `motor.mass_model = "fixed"` to use your own masses instead.

## Code layout

```
albatros/
  inputs.py        all inputs (dataclasses): edit or override via JSON
  atmosphere.py    ISA troposphere with a temperature offset
  mission.py       mission segments and time stepping
  propulsion.py    rotor power/torque, propeller coefficients, drag, motor sizing
  motor_family.py  HPDM mass-torque fit
  electrical.py    battery equivalent circuit, inverter, auxiliaries
  balancing.py     passive BMS balancing estimate
  cooling.py       cooling loop sizing and transient thermal network
  state.py         simulation state (SOC, temperatures)
  simulation.py    time simulation and limit checks
  sizing.py        run_model(): the complete design procedure
  recovery.py      landing recovery: can we land right after climbing without overheating?
  reporting.py     JSON config loading, terminal/CSV/JSON output
  plotting.py      matplotlib plots
  cli.py           command-line interface
configs/           example input files
docs/              HOW_IT_WORKS.md: detailed explanation of the code
tests/             pytest checks (energy conservation, scaling laws, ...)
```

How `run_model` works, step by step:

1. **Torque mode only:** find the MTOW for the given torque.
2. **Ns** = the largest number of cells that stays under the bus voltage ceiling.
3. Size the **motors**: power, torque and mass.
4. Find the smallest **Np** that flies the mission and all emergency branches.
5. Size the **cooling** loops at the end-of-mission hover point.
6. Run the full thermal simulation of the mission and the emergencies.
7. Build the **mass budget** and the list of issues.

## Main assumptions and limits

* Hover and climb use momentum theory with a figure of merit. Transition is
  **imposed** as a fraction of the motor rating, not solved aerodynamically.
* Emergency: two rotors (one inner and one outer) hover for 30 s, starting
  from the end of every mission segment. The battery, bus and cooling are
  assumed intact.
* Battery: constant-resistance Thevenin model with a placeholder OCV table and
  equal current sharing between parallel cells.
* Thermal: lumped nodes (average temperatures, not hot-spot or junction temperatures).
* Radiator, pump and fan masses use uncalibrated estimates. Replace them with vendor data.
* No 6-DOF flight dynamics, structures, certification or thermal-runaway analysis.

Detailed source references are in the docstrings of each module.
