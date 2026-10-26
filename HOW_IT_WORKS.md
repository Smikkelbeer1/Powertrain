# How it works – Albatros Model III

This document explains what the powertrain sizing tool does, how each part of
the code works, and **why** the code is built the way it is. Read it together
with the code: every section names the file and function it describes.

Contents

1. [What the tool does](#1-what-the-tool-does)
2. [Running it](#2-running-it)
3. [The big picture: one design run, step by step](#3-the-big-picture-one-design-run-step-by-step)
4. [Worked example: 750 kg](#4-worked-example-750-kg)
5. [Inputs](#5-inputs)
6. [The physics, file by file](#6-the-physics-file-by-file)
7. [Battery sizing in detail (series and parallel)](#7-battery-sizing-in-detail-series-and-parallel)
8. [Mass and volume budget](#8-mass-and-volume-budget)
9. [The issue list: what every warning means](#9-the-issue-list-what-every-warning-means)
10. [Extra analyses: sweeps, torque mode, landing recovery](#10-extra-analyses-sweeps-torque-mode-landing-recovery)
11. [Coding design choices and why](#11-coding-design-choices-and-why)
12. [How to extend the model](#12-how-to-extend-the-model)
13. [Assumptions and limits](#13-assumptions-and-limits)
14. [Glossary](#14-glossary)

---

## 1. What the tool does

The tool answers one question:

> **For this MTOW and this battery mass, what powertrain do we get, how far
> can it fly, and how much does the rest of it weigh?**

The battery mass is **given** as a fraction of MTOW (`battery.mass_fraction`,
from the aircraft design team). The tool fits the biggest pack it can in that
mass and calculates the **maximum cruise time and range**. The older way of
working, where the battery is *sized* for a fixed mission, is still available:
set `battery.mass_fraction = 0` (see §7.2).

"Powertrain" here means everything that is energy related: the battery
(including BMS and packaging), the four motors (with their integrated
inverters), the cooling
system and the avionics' power supply. Everything that is *not* energy related
(MTOW, drag, propeller performance, rotor layout, mission) is delivered by
other departments and enters the tool as an input.

Outputs:

* battery: number of cells in **series** (Ns) and **parallel** (Np) that fit
  in the battery mass, total cell count, energy, volume
* the **maximum cruise time and mission range**, and which limit stops a
  longer flight
* motors: required peak power, peak torque, rpm, phase current and **mass**
* cooling: eight sized loops (flow, pump, radiator, fan) and their mass
* a **volume budget**: the volume of the battery packs, radiators, fans,
  pumps, hoses, reservoirs, motors and avionics
* a time history of the whole mission (CSV): power, current, voltage, SOC
  and temperatures every 2 seconds
* a mass budget: how much of the MTOW is left for airframe, rotors and payload
* a list of every limit the design violates

The aircraft has four rotors: two inner rotors (Ø 1.47 m) and two outer rotors
(Ø 1.04 m). Everywhere in the code they are numbered in the same order:

| index | name | diameter |
|---|---|---|
| 0 | `inner_L` | 1.47 m |
| 1 | `inner_R` | 1.47 m |
| 2 | `outer_L` | 1.04 m |
| 3 | `outer_R` | 1.04 m |

---

## 2. Running it

```bash
python -m albatros --mass 750                     # one design, MTOW given
python -m albatros --torque 600                   # one design, motor torque given
python -m albatros --sweep 600 1200 50 --csv out/sweep.csv --save-plot out/sweep.png
python -m albatros --sweep-torque 300 900 100 --csv out/torque_sweep.csv
python -m albatros --config configs/my_inputs.json --json out/design.json --csv out/mission.csv
python -m albatros --mass 750 --landing-recovery 600 10 5
python -m albatros --write-config configs/my_inputs.json
python -m pytest
```

`python -m albatros` runs the file `albatros/__main__.py`, which calls
`main()` in `albatros/cli.py`. One design takes a few seconds.

---

## 3. The big picture: one design run, step by step

Everything starts in `sizing.run_model(x)`, where `x` is the complete set of
inputs. The steps are:

```
              ┌────────────────────────────────────┐
 inputs ────► │ 0. validate inputs                 │  sizing.validate
              │ 1. torque mode? -> find MTOW        │  propulsion.mtow_for_torque
              │ 2. Ns from the voltage ceiling      │  sizing.series_count
              │ 3. motor power, torque and mass     │  propulsion.size_motors
              │ 4. Np: largest that fits in the     │  sizing.parallel_from_mass
              │    battery mass budget              │
              │    -> longest cruise that passes    │  sizing.max_cruise
              │    mission + every emergency case   │    └─ simulation.simulate (many times)
              │ 5. size the 8 cooling loops         │  cooling.design_cooling
              │ 6. full simulation incl. temps      │  simulation.simulate
              │    + 18 emergency branches          │
              │ 7. mass + volume budget, issues     │  sizing.run_model
              └────────────────────────────────────┘
                               │
                               ▼
          print_design (terminal), CSV, JSON, plots      reporting.py / plotting.py
```

The most important idea to explain to others:

> **The maximum cruise is not calculated with a single energy formula.** The
> tool *tries* different cruise times. For each one it flies the complete
> mission in a time simulation, plus a two-motor emergency starting at every
> airborne mission phase, and keeps the **longest** cruise for which nothing
> goes wrong. "Wrong" means: SOC below the reserve, cell current above its
> maximum, cell or bus voltage too low. (In the older automatic mode the same
> check is used to find the *smallest* Np for a fixed cruise.)

This is more work than an energy formula, but it automatically accounts for
everything that limits a battery in reality: energy, peak current, voltage
sag at low SOC, auxiliary loads, cooling power, and the emergency reserve.
The 750 kg example below shows why that matters: the flight is limited by
the emergency **current** while half the energy is still in the battery.

---

## 4. Worked example: 750 kg

Default inputs, `python -m albatros --mass 750`. The battery fraction 0.40 is a
**placeholder**; put the real value in your config.

| Result | Value |
|---|---|
| Battery budget | 0.40 × 750 = **300 kg** |
| Battery | **190S 19P = 3610 cells**, 58.5 kWh nominal |
| Cells / pack incl. packaging + BMS | 252.7 kg / 292.3 kg (7.7 kg unused: a 20th string would not fit) |
| **Max cruise / mission range** | **14.0 min / 79 km** |
| What stops a longer cruise | `cell current (emergency hover after landing hover)` |
| Motors (4×) | 103.8 kg (inner 29.4 kg, outer 22.5 kg each), inverters integrated |
| Cooling / avionics | 108.6 / 7.6 kg |
| Total powertrain | 512.3 kg → **237.7 kg left** of the 750 kg |
| Volume: battery packs / radiators / total | 142.9 L / 131.2 L / 446.0 L |
| Mission energy from battery | 29.6 kWh, ending at 50 % SOC |

Energy per mission phase (from the CSV):

| Phase | Duration | Energy | Peak power |
|---|---|---|---|
| take-off hover | 20 s | 1.84 kWh | 332 kW |
| vertical climb (accelerate, climb, brake) | 16 s | 1.58 kWh | 420 kW |
| transition | 20 s | 2.26 kWh | 413 kW |
| climb to 600 m | 180 s | 4.00 kWh | 80 kW |
| **cruise** | **842 s** | **11.33 kWh** | 48 kW |
| descent | 180 s | 0.79 kWh | 16 kW |
| back-transition | 20 s | 2.26 kWh | 413 kW |
| landing hover | 30 s | 2.77 kWh | 333 kW |
| vertical descent | 30 s | 2.77 kWh | 333 kW |

Lessons from this example:

* **The flight ends with 50 % SOC left.** Energy is not the problem. The
  two-rotor emergency needs ~490 kW from the battery, and as the battery
  empties its voltage drops, so the current rises. Below ~52 % SOC each of
  the 19 parallel cells would exceed the 45 A limit (§7.5). The levers are:
  * a higher short-term emergency current (`cell.emergency_max_current_A`),
    if the cell supplier allows it
  * more parallel cells (a higher battery fraction)
  * a different emergency requirement
* **Hover and transition set the peak power**, so they set the motor size.
* **Per cruise minute** the aircraft uses ~0.8 kWh. The take-off and landing
  phases together cost ~14 kWh, no matter how long the cruise is.
* The radiators are bigger than in the automatic-mode example (131 vs 107 L).
  The smaller battery carries more current per cell, so it makes more heat.
* For comparison, the older **automatic mode** (`mass_fraction = 0`, 50 min
  cruise) needs 190S 24P = 369 kg of battery, limited by `SOC reserve`.

---

## 5. Inputs

### 5.1 Where they live

All inputs are defined in `albatros/inputs.py` as dataclasses, one per
subject. Each field has a default value and a unit in its name.

**Part A – department inputs** (given to us, we don't design them)

| Section | Main fields |
|---|---|
| `aircraft` | `mass_kg` (MTOW), `diameters_m`, `cruise_kmh`, `emergency_pairs`, `emergency_s`, `emergency_inner_thrust_fraction`, `emergency_on_ground`, `normal_inner_thrust_fraction`, `tip_mach_limit` |
| `aerodynamics` | `drag_model` (`"lift_drag"` or `"polar"`), `lift_drag`, `wing_area_m2`, `cd0`, `k_induced` |
| `propeller` | `model` (`"constant"` or `"coefficients"`), `hover_fm`, `ct_hover`, `cruise_prop_eff`, `cruise_rpm`, tables `J`, `CT`, `CP` |
| `mission` | heights, climb/descent rates, hover and cruise durations, transition settings, time step `dt_s` |

**Part B – powertrain design choices** (ours)

| Section | Main fields |
|---|---|
| `motor` | `peak_torque_Nm` (torque mode), `mass_model` (`"family"`/`"fixed"`), `efficiency`, `rating_margin`, `density_kg_m3` (for volume), thermal data |
| `cell` | capacity, voltages (max 4.2 / nominal 3.6 / min 2.5 V), continuous and emergency max current, resistance, mass, size, OCV table |
| `battery` | **`mass_fraction`** (battery mass / MTOW, given by aircraft design), bus voltage window, SOC limits, packaging fraction, fixed Ns/Np overrides |
| `balancing` | passive balancing hardware |
| `inverter` | `integrated_in_motor` (default `True`), efficiency or detailed SiC loss model, mass/volume if separate, thermal data |
| `auxiliaries` | flight computers, sensors, actuators, DC/DC |
| `cooling` | coolant, hoses, pumps, radiators, fans, cold plates, available pod space |

### 5.2 Config files

`reporting.load_inputs()` starts from the defaults and then overwrites only
what the JSON file contains. A config file can therefore be tiny:

```json
{
  "_comment": "Heavier variant with the propeller team's data",
  "aircraft": {"mass_kg": 850},
  "propeller": {"model": "coefficients", "J": [0, 0.5, 1.0], "CT": [0.1, 0.07, 0.03], "CP": [0.04, 0.045, 0.035]}
}
```

* Unknown sections or keys raise an error. This catches typos such as
  `"mas_kg"`, which would otherwise be silently ignored.
* Keys starting with `_` are ignored, so you can write comments.
* Lists in JSON are converted to tuples, matching the dataclass types.
* Command-line flags (`--mass`, `--torque`, `--parallel`, `--inverter`)
  override the config file.

Provided configs:

| File | Purpose |
|---|---|
| `configs/example_department_inputs.json` | template listing only the department inputs (placeholders!) |
| `configs/legacy_model_III.json` | reproduces the original single-file `albatros_model_III.py` exactly |
| `configs/my_inputs.json` | a full dump of all inputs (`--write-config`), to edit freely |

---

## 6. The physics, file by file

The files are described in the order a run uses them.

### 6.1 `atmosphere.py` – air properties

`atmosphere(altitude_MSL, sea_level_temperature)` returns density,
temperature and speed of sound.

* Pressure follows the standard atmosphere (ISA troposphere):
  `p = 101325 · (T_ISA/288.15)^(g/(R·L))`, with `T_ISA = 288.15 − 0.0065·h`.
* Temperature is ISA **plus an offset**: with `sea_level_ambient_C = 25` the
  whole atmosphere is 10 °C warmer than ISA (a hot day, less dense air, more
  power needed).
* Density from the ideal gas law `ρ = p/(R·T)`.

Valid from −500 m to 11 km.

### 6.2 `mission.py` – the flight profile

A `Segment` is one phase of the flight with **constant accelerations**:

```
h(t)  = h0 + vz0·t + ½·az·t²      altitude
vz(t) = vz0 + az·t                vertical speed
V(t)  = max(0, v0 + ax·t)         horizontal speed
```

Each segment also has a `mode`, which tells `propulsion.py` which physics to use:

* `"hover"`: rotor-borne (hover, vertical climb)
* `"descent"`: rotor-borne vertical descent
* `"wing"`: wing-borne
* `"transition"`: imposed power

`active` lists the rotors that are running: all four normally, two in an
emergency.

`mission_segments(x)` builds the default profile:

1. `takeoff_hover`: 20 s on the ground
2. `vertical_accelerate`, `vertical_climb`, `vertical_brake`: up to 60 m at
   max 6 m/s, with 1 m/s² acceleration and braking. If 60 m is too low to
   reach 6 m/s, the profile becomes accelerate-then-brake.
3. `transition`: 20 s, accelerating from 0 to cruise speed
4. `cruise_climb`: wing-borne climb at 3 m/s to 600 m
5. `cruise`: 3000 s (50 min) at 234 km/h
6. `cruise_descent`: 3 m/s down to 60 m
7. `back_transition`: 20 s, decelerating to 0
8. `landing_hover`: 30 s
9. `vertical_descent`: 2 m/s down to the ground

Segments with zero duration are dropped.

`time_steps(segment, dt)` cuts a segment into steps of `dt_s` (2 s) and gives
the **midpoint** of every step. Forces and powers are evaluated at the
midpoint. That is more accurate than the start of the step, at no extra cost.

### 6.3 `propulsion.py` – what the rotors need

This is the core physics file. `propulsion(x, segment, t, ratings, cooling_drag)`
returns, for every rotor at that instant, a `RotorPoint`: thrust, shaft power,
rpm, torque, electrical frequency and tip Mach number.

**Thrust sharing** (`thrust_fractions`):

* With all four rotors, weight is shared in proportion to disc area (D²), so
  each inner rotor carries 33 % and each outer rotor 17 %. Alternatively a
  fixed inner fraction can be set.
* In an emergency (two rotors), the inner rotor carries
  `emergency_inner_thrust_fraction` (50 %) and the outer rotor the rest.

**Hover and vertical climb** (momentum theory):

```
v_i   = sqrt((vz/2)² + T/(2ρA)) − vz/2          induced velocity
P     = T · (vz + v_i) / FM                     shaft power
rpm   from  T = CT · ρ · n² · D⁴                 (n in rev/s)
```

* FM (figure of merit) is the efficiency of the rotor in hover compared to
  the ideal rotor.
* When climbing faster, `vz` grows and so does power. When accelerating
  upwards, thrust is `m·(g + az)`, so the 1 m/s² acceleration gives about
  10 % extra thrust.
* **Vertical descent** uses hover power. Simple momentum theory is not valid
  in descent (vortex-ring state), and we don't take credit for energy
  recovery. This is conservative.

**Wing-borne flight**:

```
required thrust = Drag + W·vz/V + m·ax
```

* Drag comes from `drag_N`: either `W / (L/D)`, or the polar
  `q·S·(cd0 + k·CL²)` with `CL = W/(q·S)`. The polar makes drag depend on
  speed and air density.
* With `propeller.model = "constant"`:
  `P = (D·V + W·vz + m·V·ax + cooling drag) / η_prop`, at fixed `cruise_rpm`.
* With `propeller.model = "coefficients"`, `solve_cruise_rotor` finds the
  rotational speed n at which `ρ·n²·D⁴·CT(J)` equals the required thrust, with
  `J = V/(nD)`. It uses bisection, because thrust increases with n. The power
  is then `ρ·n³·D⁵·CP(J)`, so efficiency follows from the data:
  `η = J·CT/CP`. In hover the table row at J = 0 gives CT₀ and CP₀, and
  `FM = CT₀^1.5·√(2/π)/CP₀` (`hover_constants`).

**Transition** is not solved aerodynamically, because that needs a flight
dynamics model:

* Every motor delivers a fixed fraction of a reference power. The default is
  **1.25 × that rotor's own hover power** (`mission.transition_power_reference
  = "hover"`).
* The alternative `"rating"` uses a fraction of the motor's peak rating. That
  is what the original Model III did; it was very conservative and made the
  battery much heavier, see §7.7.
* rpm moves linearly from hover rpm to `cruise_rpm` as speed builds up.

**Torque** everywhere is `Q = P/ω` with `ω = 2π·rpm/60`.

**Motor sizing** (`required_ratings`, `size_motors`):

1. Evaluate every mission segment (start and end) and the two emergency
   cases. The emergency is evaluated at cruise height, because the air is
   thinnest there, which is the worst case.
2. Peak power and peak torque per motor = the highest value found ×
   `rating_margin` (1.10).
3. Motor mass = `motor_family.mass_from_torque(peak torque)`, or the fixed
   masses if `mass_model = "fixed"`.

The **two-motor emergency** usually sets the motor rating, because two rotors
must then carry the whole aircraft. That is why the rated power (197/278 kW)
is much higher than normal hover power.

**Torque mode** (`mtow_for_torque`): if `motor.peak_torque_Nm > 0`, the
tool searches for the MTOW at which the most loaded motor needs exactly that
torque. Required torque grows steadily with mass, so it uses bisection:

* start between 1 and 100 kg, doubling the upper bound until it is high enough
* then halve the interval 60 times

Only the cheap rating calculation runs inside this loop, not the full simulation.

### 6.4 `motor_family.py` – motor mass from torque

The four HPDM motors give four (mass, peak torque) points. A power law
`m = a · T^b` is fitted by least squares on `log(m) = log(a) + b·log(T)`
(a straight line in log-log space). Result:

```
m = 0.754 · T_peak^0.610      (R² = 0.964 in log space)
```

* `mass_from_torque` and its inverse `torque_from_mass` are what the model uses.
* Outside 4.1–50 kg the line is extrapolated, and the run reports
  "motor mass outside HPDM data range".

The fit is written in plain Python (no numpy), because the formula is short
and this keeps the model free of extra packages.

### 6.5 `electrical.py` – battery, inverter, motor

The power chain per rotor:

```
battery DC ──► inverter ──► motor ──► shaft
             loss: 2 %    loss: 10 %
```

**Motor and inverter** (`inverter_point`):

* `P_motor_in = P_shaft / η_motor` (0.90)
* `inverter loss = P_motor_in · (1/η_inv − 1)` (0.98), or with
  `inverter.mode = "device"`: conduction + switching + gate losses of a SiC
  bridge.
* Phase current `I = P / (√3 · V_line · power factor)`, with
  `V_line = modulation · V_bus / √2`. It is reported, so the drive can be specified.
* The two losses become the heat sources for the motor and inverter in the
  thermal model.

**Integrated inverter.** By default `inverter.integrated_in_motor = True`:
the inverter is built into the motor housing, as for most motors of this type.

* Its **mass and volume** are part of the motor (the HPDM fit) and are not
  counted separately.
* It needs **no separate cold plate**.
* Its **losses and temperature are still calculated**. The electronics still
  turn 2 % of the power into heat inside the motor, and that heat still has
  to go into the cooling loop.

Set it to `False` for a separate inverter box. Then `mass_each_kg`,
`volume_each_L` and a cold plate per loop are added to the budgets.

**Battery** (`battery_point`): every cell is an ideal voltage source (the
open-circuit voltage, OCV) in series with a resistor (15 mΩ). For the pack:

```
V_oc = Ns · OCV(SOC)
R    = Ns · R_cell / Np
P    = I · (V_oc − I·R)            power delivered at the terminals
I    = 2P / (V_oc + √(V_oc² − 4RP))
heat = I² · R
```

* If `V_oc² − 4RP < 0`, the battery physically cannot deliver that power at
  this SOC. That raises a "battery maximum power exceeded" error, which the
  Np search treats as "too few cells".
* `OCV(SOC)` is linear interpolation in `cell.ocv_V` (11 values from 0 % to
  100 %, a placeholder table).
* The voltage of the **weakest** series group is checked separately, using
  `soc_min`.

**Solving it** (`electrical`): inverter current depends on bus voltage, and
bus voltage depends on how much current is drawn (sag). The function guesses
the voltage, computes the power, computes the new voltage, and repeats with
damping (averaging old and new) until the change is below 10 µV. This
normally takes a handful of iterations.

**Auxiliaries** (`auxiliary_power`): 3 flight computers, voter, sensors,
communications, BMS, actuators (more active in hover than in cruise) and BMS
boards. All of this is divided by the DC/DC efficiency.

**Battery sections** (`section_counts`): the 190 series groups are split over
four sections, one in each wing near a pod (48 + 48 + 47 + 47). Each section
has its own cooling loop.

### 6.6 `balancing.py` – passive balancing (ground only)

Cells drift apart in SOC. Passive balancing burns charge from the fullest
groups through a resistor. This file estimates, **on the ground before
flight**:

* the bleed current (≈ 0.1 A) and the heat per channel
* how many channels a board may run at once without exceeding its temperature limit
* the time to bring a 1 % spread down to 0.2 % (~21 h at 25P: passive
  balancing is slow; this is a finding, not an error)
* the mass of boards, channels and harness (1.7 kg)

It does not affect the flight. The flight simply starts with a 0.2 % spread
(`residual_soc_spread`).

### 6.7 `cooling.py` – cooling system

**Architecture.** There are 8 independent liquid loops, two per pod:

* **propulsion loop**: radiator → inverter → motor jacket → back (with an
  integrated inverter both sit in the same motor housing)
* **battery loop**: radiator → battery section cold plates → back

**Sizing a loop** (`make_loop`) is a chain:

1. **Coolant flow** from heat load and allowed temperature rise:
   `ṁ = Q / (cp · ΔT)`, with 15 K for propulsion and 5 K for battery loops.
   The flow is sized for 100 % of hover heat.
2. **Hose diameter** from the allowed velocity (1.5 m/s). Pressure loss uses
   Darcy–Weisbach: laminar `64/Re`, turbulent Blasius.
3. **Pump**: total pressure loss (hoses + radiator + jacket or cold plate) ×
   1.2 margin → pump power.
4. **Radiator duty** = 70 % of hover heat + pump power. Hover is short, and
   the thermal mass of the parts absorbs the rest; the transient simulation
   checks that this is enough.
5. **Radiator size** with the ε-NTU method: required effectiveness → NTU →
   required UA. The core volume is the larger of "enough face area for the
   airflow" and "enough UA" (assumed 100 kW/K per m³ of core).
6. **Fan** power: `fan pressure × air volume flow / fan efficiency`. The fan
   pressure is the radiator's air-side pressure drop (500 Pa) **minus the
   downwash credit** `cooling.hover_propwash_pressure_Pa` (see below).
7. **Masses** of radiator, pump, fan, hoses, coolant, reservoir, fittings,
   cold plates and thermal interface material.

**Battery cold plates** (`battery_plate`): for cylindrical cells,
side-contact "ribbons" of 20 cells. The thermal resistance per cell is

```
R = R_core + R_TIM + R_wall + 1/(h·A)
```

with h from the flow in the channel.

**Where sizing happens** (`design_cooling`): hover at 60 m with the battery
at its reserve SOC. Low SOC means lower voltage, so more current and more
battery heat; this is the hottest realistic steady point. Pump and fan power
are themselves battery load, so the sizing is repeated until the auxiliary
power stops changing.

**In flight** (`air_operation`): at altitude the air is thinner. Pushing the
same mass of air needs more pressure, so if the fan rating isn't enough, the
airflow is reduced (found by bisection) and the radiator rejects less heat.
Two things help the fan push air through the radiator:

* **Ram air** in forward flight. The resulting drag is added to the
  wing-borne power. At cruise speed ram pressure (~1600 Pa) is larger than
  the 500 Pa the radiators need, so the fans are almost idle in cruise.
* **Rotor downwash** whenever the rotors carry the aircraft (hover, vertical
  climb and descent, transition, emergency). The model subtracts
  `cooling.hover_propwash_pressure_Pa` from what the fans must deliver. Its
  energy is already part of the rotor power, so it is not charged again.
  The default is **0** (no credit, conservative), because the real value
  depends on where the radiators sit relative to the rotors. In theory the
  fully developed wake carries a pressure of about the disc loading (T/A, a
  few hundred to ~1400 Pa here), but a radiator only captures part of it.
  Get the value from the aero/propeller team.

With a large downwash credit the fans become small. They then have little
spare pressure for thin air: at 600 m the radiator needs ~6 % more pressure,
which can be 30 % more *fan* pressure. If the run reports "fan rating
insufficient at altitude", raise `cooling.fan_rating_margin` (e.g. 1.4).

**Temperatures** (`thermal_step`): every part is one lumped node,
`m·cp·dT/dt = heat in − heat to coolant`. Heat to the coolant is limited by
how much heat the flow can carry: `q = C·(1 − e^(−UA/C))·(T_part − T_coolant)`.

* Coolant flows inverter first, then motor.
* Large time steps are split into small sub-steps for numerical stability.
* A test checks that energy is conserved exactly.

### 6.8 `state.py` – what changes during flight

`State` holds:

* the SOC: the mean, and the weakest group
* temperatures of the 4 battery sections, 4 motors, 4 inverters and 8 coolant loops

`initial_state` sets the state at departure: the battery is full minus the
spread, and everything is at 30 °C.

### 6.9 `simulation.py` – flying the mission

`simulate(x, Ns, Np, loops, motors, segments, start_state, thermal, stop_on_electrical)`
loops over every segment and every 2 s step:

1. altitude and speed at the step midpoint
2. fan power and cooling drag (`air_operation`)
3. rotor power (`propulsion`)
4. battery current and voltage (`electrical`)
5. SOC update: `ΔSOC = I·dt / (Np · capacity · SOH · 3600)`
6. electrical checks: SOC reserve, cell current, cell voltage, bus voltage
7. temperatures (`thermal_step`), unless `thermal=False`
8. remaining checks: temperatures, fan, motor ratings, tip Mach, …
9. one output row (≈ 60 columns, including per-rotor values) for the CSV

At the end of every segment a **checkpoint** (a copy of the state) is
stored. Emergency cases start from these checkpoints.

* `thermal=False` and `stop_on_electrical=True` are used during battery
  sizing to make the many trial runs fast.
* `metrics(rows)` summarizes a run: energy, peak power, peak current,
  minimum voltage, end SOC and peak temperatures.

### 6.10 `sizing.py` – the design procedure

* `validate`: checks every input before anything runs (see §11.6).
* `series_count`: Ns, see §7.1.
* `parallel_from_mass`: Np from the battery mass budget, see §7.3.
* `max_cruise`: the longest cruise the battery can fly, see §7.4.
* `electrical_check`: "does this battery pass the mission and every
  emergency case?", used by both searches. Returns a list of reasons; an
  empty list means it passes.
* `emergency_checkpoints`: which checkpoints get an emergency case (§7.5).
* `size_parallel_count`: Np in the older automatic mode, see §7.6.
* `motor_issues`: warns when the motor fit is extrapolated.
* `run_model`: the procedure from §3, ending in one big result dictionary.
  That dictionary is printed, written to JSON, and used for sweeps.
* `sweep_values`: the list of values for `--sweep`.

### 6.11 `recovery.py` – can we land straight after climbing?

`landing_recovery(x, design, max_cruise_s, step_s, margin_C)` takes a
finished design (nothing is re-sized) and asks: if the aircraft turns back
right after the climb, do the battery, motor and inverter stay at least
`margin_C` below their temperature limits during descent, back-transition
and landing?

* It flies take-off → transition → climb once.
* It then tries 0, 10, 20 … s of level cruise. For each, it flies the whole
  landing from that exact state.
* It stops at the first cruise time that passes.
* Each cruise piece continues from the previous one, so the cruise is only
  simulated once in total.

The result is a *sampled* minimum: a feasible window shorter than one step
could be missed. For the 750 kg default it passes immediately (0 s); peak
landing temperatures are 33 °C cells, 52 °C motor, 36 °C inverter.

### 6.12 `reporting.py`, `plotting.py`, `cli.py`

* `reporting.py`: reads configs (`load_inputs`), writes config/CSV/JSON,
  prints the terminal summary (`print_design`, `print_recovery`) and builds
  sweep rows.
* `plotting.py`: for a single design, SOC/voltage, power, temperatures and
  altitude over time. For a sweep, battery, motor and remaining mass and
  motor temperature against the swept variable. Matplotlib is imported only
  when you ask for a plot.
* `cli.py`: turns command-line flags into inputs and calls the right functions.

---

## 7. Battery sizing in detail (series and parallel)

A battery pack is a grid of cells:

* cells in **series** add voltage
* cells in **parallel** add capacity and current

The total number of cells is `Ns × Np`, and the cell mass is
`Ns × Np × 70 g`. The two numbers are chosen by completely different rules.

### 7.1 Series count Ns – why the 4.2 V is used

`series_count`: `Ns = floor((bus_max_V − charge_margin_V) / cell.max_V)`
= floor(800 / 4.2) = **190**.

A cell's voltage is not fixed; it moves with its state of charge:

| Cell voltage | Meaning | Pack (190S) |
|---|---|---|
| 4.2 V (`max_V`) | fully charged, end of charging | **798 V** |
| 3.6 V (`nominal_V`) | average over a discharge (datasheet "nominal") | 684 V |
| 3.38 V | OCV at the 20 % reserve | 642 V (no load) |
| 2.5 V (`min_V`) | discharge cut-off, never go below | 475 V |

Ns is sized on **4.2 V** because the series count must make sure the pack
**never exceeds the highest voltage the inverters, cables, connectors and
contactors are rated for** (800 V here). The highest voltage the pack ever
has is right after charging: 4.2 V per cell. If Ns were sized on the nominal
3.6 V, you would get 800/3.6 = 222 cells in series. At full charge that is
222 × 4.2 = **932 V**, which would overload the 800 V components on every flight.

The other two voltages are not used to choose Ns, but they are checked:

* **2.5 V (cell minimum)** is checked every time step for the *weakest*
  group under load (the "cell voltage" check).
* **500 V (bus minimum, `bus_min_V`)** is the lowest voltage the motor drives
  accept. It is checked every step (the "bus voltage" check). With 190S this
  equals 2.63 V per cell, so in practice the bus limit is reached before the
  cell limit.
* **3.6 V (nominal)** is only used to report the nominal energy:
  `Ns · Np · 3.6 V · 4.5 Ah` = 77.0 kWh for 190S25P. The *real* energy the
  simulation draws follows the OCV table and the voltage sag, not the 3.6 V.

In short: **the maximum voltage sets Ns, the minimum voltages are limits the
simulation checks, and the nominal voltage is only used for reporting energy.**
This is standard practice for high-voltage packs.

Small note: the placeholder OCV table tops out at 4.15 V instead of 4.2 V, so
in the simulation a full pack rests at 788.5 V. Using 4.2 V for Ns is the
conservative choice either way.

If you want to change it:

* `battery.series_count` forces a fixed Ns.
* `battery.charge_margin_V` keeps extra distance from the 800 V ceiling (e.g.
  for charger tolerance).
* `battery.bus_max_V` changes the ceiling itself.

### 7.2 Three battery modes

`run_model` chooses one of three modes:

| Mode | When | Np | Cruise |
|---|---|---|---|
| **Battery mass fraction** (default) | `battery.mass_fraction > 0` | largest that fits in fraction × MTOW | **longest** that passes |
| Automatic sizing | `battery.mass_fraction = 0` | **smallest** that flies the set mission | `mission.cruise_s` (fixed) |
| Fixed pack | `battery.parallel_count > 0` | that value | `mission.cruise_s` (fixed), just checked |

The terminal output shows which mode ran (`Sizing mode:`).

### 7.3 Parallel count from the battery mass (default mode)

`parallel_from_mass` uses the same formula as the mass budget:

```
pack mass = Ns · Np · cell mass · (1 + packaging fraction) + BMS hardware
          = 190 · Np · 0.070 kg · 1.15                    + 1.7 kg
```

* The BMS hardware (monitor boards, one balancing channel per series group,
  master and harness) depends only on Ns, so it is subtracted from the
  budget first.
* What's left is divided by the mass of one 190-cell string (15.3 kg) and
  **rounded down**, because a partial string doesn't fit.
* At 750 kg: (300 − 1.7) / 15.3 = 19.5 → **19P**, 292.3 kg.

The battery cold plates, TIM and coolant are part of the cooling mass, not of
the battery fraction.

### 7.4 Maximum cruise: the search

`max_cruise` finds the longest cruise for which `electrical_check` passes. The
check covers:

1. The normal mission: no SOC below `minimum_soc` (20 %), no cell above
   45 A, no cell below 2.5 V and no bus below 500 V.
2. A **30 s two-motor emergency hover**, started from the state at the end
   of every **airborne** mission segment (9 checkpoints × 2 rotor pairs = 18
   cases), with the same limits, except for the emergency current limit (§7.5).

How it searches:

```
cruise 0 must pass (otherwise: error "cannot fly the mission even without cruise")
try 50 min, 100 min, 200 min …   until one fails          (doubling)
then halve the interval between "passes" and "fails" until it is 1 s wide
```

This works because a longer cruise can only make things worse: the SOC is
lower at every later checkpoint. Temperatures are switched off during the
search (`thermal=False`), which makes it much faster. The full thermal
simulation of the final mission comes afterwards. The line
`a longer cruise fails on:` shows which check fails just beyond the maximum,
and in which case.

**Range** is the horizontal distance of the whole mission (transition, climb,
cruise, descent, back-transition). Each segment contributes
`segment.distance() = v0·t + ½·a·t²`, and `mission_range_km` adds them up.

### 7.5 The emergency case and the cell current

The emergency (two rotors carry the whole aircraft for `aircraft.emergency_s`
= 30 s) is usually the hardest case for the battery. At 750 kg it needs
~490 kW. The same power at a lower battery voltage means more current:

| SOC | 90 % | 70 % | 55 % | 50 % | 30 % | 20 % |
|---|---|---|---|---|---|---|
| Cell current, 19P | 39.8 A | 42.4 A | 44.5 A | **45.3 A** | 48.9 A | 52.6 A |

Two settings control this case:

* **`aircraft.emergency_on_ground`** (default `False`): emergencies are only
  checked at airborne checkpoints (altitude above 0 m). The checkpoints before
  take-off, after the take-off hover at ground level and after landing are
  skipped. A motor failure on the ground just means "don't take off".
* **`cell.emergency_max_current_A`** (default 45 A): the cell current limit
  during the emergency, which is short.
  * The Molicel P45B datasheet only gives **45 A continuous (80 °C
    cut-off)**. That is a thermal limit, so a higher short-term current is
    physically plausible, but the datasheet has no pulse rating.
  * Keep 45 A until the supplier gives one.
  * As an illustration only, a 60 A limit would raise the 750 kg cruise from
    14 to 32 min.

Normal flight always uses `cell.max_current_A` (45 A).

Hover power grows with MTOW^1.5, while a battery that is a fixed fraction of
MTOW grows only linearly. So the heavier the aircraft, the harder the
emergency gets. With the defaults, 900 kg cannot fly the mission at all
("cannot fly the mission even without cruise"). A sweep shows where this
happens:

```bash
python -m albatros --sweep 600 900 50 --csv out/sweep.csv --save-plot out/sweep.png
```

### 7.6 Automatic mode: what decides Np

With `battery.mass_fraction = 0`, `size_parallel_count` finds the smallest
Np that passes `electrical_check` for the set `mission.cruise_s`:

```
try Np = 1, 2, 4, 8, 16, 32 …  until one works        (doubling)
then bisect between the last failure and the first success
then double-check Np−1, Np−2 … in case the result isn't perfectly monotonic
```

Results are cached, so no Np is ever simulated twice. The output line
`Why not one parallel string fewer:` shows which limit Np − 1 violates. That
tells you what is driving the battery size. The same messages appear after
`a longer cruise fails on:` in the default mode:

| Message | Battery is limited by | Levers |
|---|---|---|
| `SOC reserve` | **energy** | cruise time, L/D, propeller efficiency, reserve %, cell energy density |
| `cell current` | **peak power** (cell max 45 A) | transition/hover power, emergency case and its current limit, more parallel cells |
| `cell voltage` / `bus voltage` | **voltage sag** at low SOC under high load | cell resistance, bus minimum, reserve |
| `Battery equivalent-circuit maximum power exceeded` | the pack physically can't deliver the power | more cells or a lower-resistance cell |

A message ending in `(emergency hover after …)` means the emergency case
started at that checkpoint failed; without it, the normal mission failed.

### 7.7 Why the old version gave ~580 kg

In the original Model III, transition ran every motor at **100 % of its peak
rating**. That rating is sized for the two-motor emergency (×1.1), so during
transition the four motors together drew ≈ 950 kW of shaft power, about
**1.08 MW** from the battery. Np then had to be 38 just to keep each cell
below 45 A (`cell current`). Defining transition as 125 % of hover power
brings Np to 25, and the battery from 583 kg to 384 kg. The old behaviour is
still available with `mission.transition_power_reference = "rating"`.

---

## 8. Mass and volume budget

### 8.1 Mass

`run_model` adds up:

| Item | How it is computed |
|---|---|
| Cells | `Ns · Np · cell.mass_kg` (in the default mode Np follows from the battery budget) |
| Battery incl. packaging + BMS | cells × (1 + `noncooling_packaging_fraction` 0.15) + balancing hardware |
| Motors | sum of the four motor masses (HPDM fit) |
| Inverters | 0 if `integrated_in_motor` (part of the motor mass), else 4 × `inverter.mass_each_kg` |
| Cooling | sum over the 8 loops: radiator, pump, fan, hoses, coolant, reservoir, fittings, plates (battery only if the inverter is integrated), TIM |
| Avionics | flight computers + voter + other avionics/actuators |

`remaining_MTOW_kg = MTOW − total`. This is what is left for the airframe,
rotors, landing gear, payload, etc. If it is negative, the issue
"accounted subsystem mass exceeds MTOW" is raised.

**MTOW and battery mass are inputs, not results.** The tool does not iterate
"MTOW = airframe + payload + powertrain" by itself. Sweep MTOW (`--sweep`)
to see how range and remaining mass change, and compare that with what the
other departments need.

### 8.2 Volume

`run_model` also builds a volume budget, `volumes_L` (all values in litres,
outer volume of each part). The totals are printed under `-- Volume budget (L) --`.

| Part | How it is computed | 750 kg example |
|---|---|---|
| Battery packs | bare cell volume / `battery.volume_fill_fraction` (0.65). The other 35 % is cold plates, BMS, busbars and housing | 188.0 L (cells alone 122.2 L) |
| Radiators | sum of the 8 radiator core volumes from the cooling sizing | 107.1 L |
| Fans | radiator face area × `cooling.fan_face_coverage` × `cooling.fan_depth_m`, or, if `cooling.fan_volume_L_per_kW` > 0, that value × fan rating | 89.3 L (full coverage, no downwash credit) |
| Pumps | pump mass / `cooling.pump_density_kg_m3` | 2.3 L |
| Hoses | supply + return length × outer cross-section | 6.6 L |
| Reservoirs | coolant reserve per loop | 2.0 L |
| Motors | motor mass / `motor.density_kg_m3` (3500 kg/m³) | 29.7 L |
| Inverters | 0 if integrated, else 4 × `inverter.volume_each_L` | 0 L |
| Avionics | `auxiliaries.avionics_volume_L` (fixed estimate) | 20.0 L |
| **Total** | | **444.9 L** |

Notes:

* Coolant inside the radiators, hoses and cold plates sits *inside* those
  parts, so it is not counted twice. Only the reservoir reserve is a separate
  volume.
* The **battery and radiator** volumes follow from the sizing (cell geometry,
  required heat-exchanger size), so they change with the design.
* **Fan volume** depends on settings that are currently assumptions: a 5 cm
  layer over the whole radiator face (default), a partial layer
  (`fan_face_coverage`), or proportional to fan power (`fan_volume_L_per_kW`).
  Combined with a downwash credit, the fans can shrink a lot. At 750 kg,
  400 Pa of downwash credit cuts the fan rating from 9.3 to 1.8 kW and the fan
  mass from 10.9 to 3.4 kg. With 50 % coverage that gives 44 L of fans; with
  5 L/kW, 9 L.
* **Motor, pump and avionics** volumes use assumed densities or fixed values
  (placeholders, marked in `inputs.py`). Replace them with supplier data when
  available.
* The per-pod table (`radiator_packaging` in the JSON) shows the battery
  section and radiator core volume per pod. It also says whether the radiators
  fit in the space available per pod (`cooling.pod_core_face_available_m2`,
  `pod_core_volume_available_L`).

---

## 9. The issue list: what every warning means

Issues are collected in `simulation.py`, `sizing.py` and `balancing.py`, and
printed under `MODEL LIMIT EXCEEDANCES`. They are warnings about the
design; the run still completes.

| Issue | Meaning |
|---|---|
| `SOC reserve` | the weakest group went below `battery.minimum_soc` (only with a fixed Np) |
| `cell current` | cell current above `cell.max_current_A` (normal flight) or `cell.emergency_max_current_A` (two-rotor emergency) |
| `cell voltage` | weakest cell below `cell.min_V` under load |
| `bus voltage` | bus outside `bus_min_V … bus_max_V` |
| `battery / motor / inverter temperature` | lumped temperature above its limit |
| `fan rating insufficient at altitude` | the fan can't deliver design airflow in thin air |
| `motor peak power rating` / `motor peak torque rating` | demand above the installed rating |
| `motor electrical frequency limit` | `pole_pairs · rpm/60` above the drive limit |
| `indicative rotor tip Mach limit` | tip speed above Mach 0.85. The outer rotors at high hover rpm cause this |
| `inverter phase current rating` | above `inverter.phase_rms_limit_A` (if set) |
| `inverter device voltage margin` | full-charge voltage above 80 % of the device rating |
| `accounted subsystem mass exceeds MTOW` | powertrain heavier than the whole aircraft |
| `radiator core nacelle allowance exceeded` | radiators don't fit in the space per pod |
| `motor mass outside HPDM data range` | the mass fit is extrapolated |
| balancing messages | resistor overloaded, board too hot, etc. |

There is also a fixed list of **assumption warnings**, printed every time, to
remind readers what the model does *not* prove.

---

## 10. Extra analyses: sweeps, torque mode, landing recovery

* **MTOW sweep** (`--sweep START STOP STEP`) runs one full design per MTOW
  and writes one row per design: Ns, Np, cells, battery/motor/cooling mass,
  remaining mass, energy, temperatures and issues. Plot it with `--save-plot`.
  Failed points keep their error message instead of stopping the sweep.
* **Torque mode** (`--torque T`) gives four identical motors of T Nm and
  finds the MTOW they can carry (§6.3). `--sweep-torque` does this for a
  range of motors.
* **Landing recovery** (`--landing-recovery MAX STEP MARGIN`) is described
  in §6.11.

---

## 11. Coding design choices and why

### 11.1 A package of small modules instead of one big file

The original model was one file of ~1400 lines. It is now a package
(`albatros/`) with one file per subject (atmosphere, mission, propulsion, …).

*Why:*

* Each file can be read and checked on its own.
* A git diff shows immediately which subject a change touches.
* Several people can work on different parts without conflicts.
* The import order follows the physics:

```
inputs → atmosphere → mission → propulsion → electrical → cooling → simulation → sizing → cli
```

Lower modules never import higher ones, so there are no circular dependencies.

### 11.2 All inputs in dataclasses, split by owner

*Why dataclasses:*

* They give named, typed fields with default values.
* They can be converted to and from JSON automatically (`asdict`, `fields`).
* An editor shows what fields exist.

*Why Part A / Part B:* it makes ownership explicit. Department inputs can be
replaced as a block when new data arrives, without touching our design
choices, and it is clear which numbers we are allowed to optimise.

### 11.3 Units in every name

`mass_kg`, `shaft_W`, `temp_limit_C`, `flow_delta_K`. Unit mistakes are the
most common error in engineering code. With the unit in the name, a line like
`power_W / 1000` is obviously kW, and kW cannot be accidentally added to W.
`_C` is an absolute temperature in °C; `_K` is a temperature *difference*.

### 11.4 Config files that override defaults, with typo checks

*Why not just edit the code:*

* A JSON file records exactly which inputs a result was made with, and can
  be committed next to it.
* Different variants (department data, legacy, heavy variant) can coexist
  without copies of the code.
* Overriding only what's in the file keeps configs short.
* Rejecting unknown keys prevents the classic silent error where a misspelt
  key is ignored and the default is used.

### 11.5 Standard library only (matplotlib optional)

The model uses only Python's built-in modules. Matplotlib is needed only for
plots and is imported only when you ask for one.

*Why:*

* Anyone with Python 3.10+ can run it: no installation problems on
  university PCs or in CI.
* The calculations are scalar (one value per time step), where plain Python is
  as fast as numpy.

### 11.6 Validate early, with clear messages

`sizing.validate` checks every input before the calculation starts: positive
masses, efficiencies between 0 and 1, consistent tables, valid model names,
etc.

*Why:* a wrong input otherwise shows up minutes later as a confusing
`ZeroDivisionError` deep inside the cooling code. A message like "Propeller J
must increase" points straight at the cause.

### 11.7 Errors that mean "battery too small" vs. real errors

During the Np search, a too-small battery can make the equivalent circuit
impossible to solve ("Battery equivalent-circuit maximum power exceeded").
The search catches **only** those battery and cooling-convergence errors and
treats them as "infeasible, try more cells". Any other error is re-raised.

*Why:* a genuine input mistake must never be silently interpreted as "need
more batteries", which would give a wrong design without any warning.

### 11.8 Never modify the caller's inputs

`run_model` starts with `x = deepcopy(x)`. Torque mode, for example, changes
the MTOW inside the copy only.

*Why:* sweeps and the landing-recovery analysis reuse the same inputs
object. If `run_model` changed it, the second design of a sweep would
silently start from the first one's result.

### 11.9 Searches by bisection

Np (automatic mode), the maximum cruise, the MTOW in torque mode, the cruise
rpm, and the reduced fan airflow are all found by bisection or doubling +
bisection.

*Why:* each of these quantities moves steadily in one direction. Bisection
is simple and always converges, and the accuracy is predictable (every step
halves the uncertainty). It needs no derivatives and no starting guess.
Fancier solvers (Newton) can diverge.

### 11.10 One check, used by every search

`electrical_check` is the single place that decides "does this battery
pass?". The automatic Np search and the maximum-cruise search both call it.

*Why:* if the rules change (like the emergency settings in §7.5), they change
for every mode at once, and the modes can never disagree about what
"passing" means.

### 11.11 Fast simulation during sizing, full simulation once

The searches (max cruise, or Np in automatic mode) run dozens of simulations, with temperatures off and stopping
at the first electrical violation. Only the final design gets the full
thermal simulation of the mission and all 18 emergency cases.

*Why:* this keeps a design run at a few seconds, which makes sweeps of
dozens of designs practical.

### 11.12 Time-stepping simulation instead of energy formulas

*Why:* limits like voltage sag at low SOC, peak current, and temperature
build-up depend on **when** things happen, not just how much energy is used.
A time simulation captures this naturally, and it gives the mission CSV, which
is useful for checking the model and for other departments.

### 11.13 Midpoint time steps and thermal sub-steps

Powers are evaluated at the middle of each 2 s step. The thermal model splits
each step into smaller sub-steps when a part heats up quickly.

*Why:* midpoint evaluation is more accurate than evaluating at the start, at
no extra cost. Thermal sub-steps keep the temperature integration stable
without making the whole simulation use tiny steps.

### 11.14 Results as plain dictionaries

`run_model` returns a plain `dict` with numbers, strings and lists.

*Why:* it can be written to JSON directly. It can be read by any other tool
(Excel, MATLAB, another department's script), and it is easy to add a field
without breaking anything.

### 11.15 A legacy config and tests to protect the physics

`configs/legacy_model_III.json` reproduces the original single-file model
(including separate inverters).
During the restructuring, every number in the output JSON was compared
against the original. The largest difference was 2·10⁻¹⁵, which is
rounding-level.

`tests/test_model.py` (pytest) checks physical laws rather than particular numbers:

* hover power scales with mass^1.5
* the battery delivers exactly the requested power
* the thermal model conserves energy
* the CT/CP definitions hold
* torque mode hits the requested torque
* a fan-limited radiator never "creates" cooling
* landing recovery behaves sensibly

*Why:* tests catch accidental changes when someone edits the code. Checking
laws instead of exact numbers means a legitimate input change doesn't break
them.

### 11.16 Fixed rotor order and per-rotor lists

Every per-rotor quantity is a list of four values in the order
inner_L, inner_R, outer_L, outer_R (`inputs.NAMES`).

*Why:* inner and outer rotors are different sizes and need different
motors. One fixed order everywhere avoids mix-ups, and the loops in the code
stay simple.

### 11.17 Assumptions are printed, not hidden

Placeholder data is marked `PLACEHOLDER` in the code, and model limits are
listed in the module docstrings. Every run prints its assumption warnings.

*Why:* a conceptual model is only useful if readers know what it does *not*
prove. Printing the warnings makes sure they travel with the results.

---

## 12. How to extend the model

**Add a new input**

1. Add a field with a default and a unit in its name to the right dataclass
   in `inputs.py`.
2. Use it via `x.<section>.<field>`.
3. If it can be invalid, add a check in `sizing.validate`.

Config files and `--write-config` pick it up automatically.

**Add a new limit check**

In `simulation.simulate`, add `issues.add("my new check")` where the
condition is evaluated. If it should make the battery bigger, also add it to
`ELECTRICAL_FLAGS`. Document it in §9.

**Add a new output column**

Add it to the `row` dictionary in `simulate`; it then appears in the CSV
automatically. For a design-level number, add it to the dictionary returned
by `run_model` (and to `print_design` / `sweep_row` if wanted).

**Replace placeholder data**

Put the department data in a config file (start from
`configs/example_department_inputs.json`). There is no need to edit the code.

After any change, run `python -m pytest`.

---

## 13. Assumptions and limits

* **Transition** is imposed (power and rpm schedule), not a solved flight path.
* **Emergency:** two rotors hover for 30 s from every airborne mission
  checkpoint.
  * The battery, bus and cooling are assumed intact, and the hover is
    reached immediately.
  * The emergency cell current limit equals the continuous 45 A until a
    supplier pulse rating is known.
* **Battery fraction** covers cells, packaging and BMS. Battery cooling
  hardware is counted under cooling.
* **Hover** uses momentum theory with a figure of merit. **Descent** uses
  hover power (no energy recovery).
* **Battery:**
  * constant resistance and a placeholder OCV table
  * equal sharing between parallel cells
  * no ageing unless `soh` / `resistance_age_factor` are changed
* **Thermal:** one temperature per component (average, not the hottest point).
* **Cooling:** radiator, pump and fan performance and masses are uncalibrated
  estimates. Replace them with vendor data.
* **Motor efficiency** is constant (90 %); the motor mass comes from a
  four-point fit.
* **Not included:**
  * 6-DOF flight dynamics and control allocation
  * structures and certification
  * thermal runaway and fault isolation
  * charging

---

## 14. Glossary

| Term | Meaning |
|---|---|
| MTOW | maximum take-off mass |
| Ns / Np | number of cells in series / in parallel |
| SOC | state of charge, 1 = full, 0 = empty |
| SOH | state of health, remaining capacity fraction |
| OCV | open-circuit voltage: cell voltage without current |
| voltage sag | voltage drop `I·R` when current flows |
| C-rate | current relative to capacity: 1C empties the cell in one hour |
| FM | figure of merit: hover efficiency of a rotor vs. the ideal rotor |
| CT, CP, J | propeller thrust coefficient, power coefficient, advance ratio |
| L/D | lift-to-drag ratio |
| UA | heat conductance [W/K]: heat flow per degree temperature difference |
| ε-NTU | heat exchanger method linking effectiveness to size (UA) |
| ram drag | drag caused by air flowing through the radiators |
| lumped node | one temperature representing a whole component |
| bisection | repeatedly halving an interval to find where a condition switches |
| checkpoint | saved simulation state at the end of a mission segment |
