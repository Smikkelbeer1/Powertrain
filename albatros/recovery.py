"""Thermal landing recovery: can the sized design land without overheating?

Question answered: if the aircraft takes off, transitions and climbs, then
immediately turns back (descent -> back-transition -> landing hover ->
vertical descent), do the battery, motors and inverters stay below their
temperature limits? If not, how much level cruise is needed first to let the
hardware cool down before the (hot) landing phases?

The hardware is the baseline design from ``run_model``; nothing is re-sized.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from .cooling import Loop
from .inputs import Inputs
from .mission import Segment, mission_segments
from .propulsion import MotorSizing
from .simulation import ELECTRICAL_FLAGS, metrics, simulate

# Issues that make a flight path unacceptable (others, e.g. tip Mach, are
# properties of the baseline design and are only reported).
TEMPERATURE_FLAGS = {"battery temperature", "motor temperature", "inverter temperature"}
BLOCKING_FLAGS = ELECTRICAL_FLAGS | TEMPERATURE_FLAGS


def _landing_check(x: Inputs, rows: list[dict[str, Any]], issues: list[str],
                   margin_C: float) -> tuple[dict[str, float], list[str]]:
    """Peak landing temperatures, headroom to (limit - margin) and failure reasons."""
    limits = dict(battery=x.cell.temp_limit_C, motor=x.motor.limit_C,
                  inverter=x.inverter.temp_limit_C)
    peaks: dict[str, float] = {}
    reasons = sorted(set(issues) & ELECTRICAL_FLAGS)
    for part, limit in limits.items():
        peak = max(r[part + "_C"] for r in rows)
        peaks["peak_" + part + "_C"] = peak
        peaks[part + "_headroom_C"] = limit - margin_C - peak
        if peak > limit - margin_C:
            reasons.append(f"{part} temperature within {margin_C:g} C margin")
    return peaks, reasons


def landing_recovery(x: Inputs, design: dict[str, Any], max_cruise_s: float,
                     step_s: float = 10.0, margin_C: float = 5.0) -> dict[str, Any]:
    """Find the earliest TESTED level-cruise duration allowing the full landing.

    Hardware is reconstructed from ONE baseline design: Ns/Np, motor ratings,
    pumps, radiators and liquid inventory never change between trial durations.
    The baseline is sized for mission.cruise_s (or the configured fixed Np),
    not re-sized for every recovery trial. A float step is allowed.

    Prefix = takeoff + outbound transition + wingborne climb.
    Candidate = prefix + t seconds LEVEL cruise + wing descent + back-transition
                + landing hover + vertical descent.
    Descent therefore contributes cooling before back-transition. The answer is
    additional level-cruise time AFTER climb, not elapsed time since takeoff.

    We replay the full landing from each actual cruise state, including SOC,
    voltage sag, component and coolant temperatures. All component temperatures
    throughout landing must remain <= their limits minus margin_C. Prefix and
    cruise must also avoid actual temperature limits and electrical violations.
    The margin is a user-selected planning allowance, not a certification rule.

    Sequential grid search does NOT assume monotonic feasibility: more cruise
    can cool the hardware but also deplete the battery. Stop at the first passing
    sampled time. If t>0, the previous grid point failed, so a crossing may lie in
    that interval; a narrower earlier feasible window could still be missed.
    This is a sampled minimum, not a proof of the exact continuous minimum.
    """
    if (not math.isfinite(max_cruise_s) or not math.isfinite(step_s) or
            not math.isfinite(margin_C) or max_cruise_s < 0 or step_s <= 0 or margin_C < 0):
        raise ValueError("Recovery requires finite MAX >= 0, STEP > 0 and thermal margin >= 0")
    if math.ceil(max_cruise_s/step_s) > 10000:
        raise ValueError("Recovery search exceeds 10,000 trials; increase cruise step")
    # run_model may replace the MTOW (torque mode) and the cruise time (battery
    # mass fraction mode); apply both before comparing.
    x = deepcopy(x)
    x.aircraft.mass_kg = design["mtow_kg"]
    x.mission.cruise_s = design["cruise_s"]
    if json.loads(json.dumps(asdict(x))) != json.loads(json.dumps(design["inputs"])):
        raise ValueError("Recovery inputs must match the supplied baseline design")
    ns, np = design["series"], design["parallel"]
    loops = [Loop(**item) for item in design["cooling_loops"]]
    drives = design["drive_requirements"]
    motors = MotorSizing(power_W=[d["installed_peak_requirement_kW"]*1000 for d in drives],
                         torque_Nm=[d["rated_torque_Nm"] for d in drives],
                         mass_kg=[d["motor_mass_kg"] for d in drives],
                         driver=design["design_driver"])
    phases = mission_segments(x)
    # Locate the landing boundary even when nominal cruise_s=0 removes the
    # level-cruise Segment from the ordinary mission list.
    landing_start = next(i for i,s in enumerate(phases)
                         if s.name in ("cruise_descent", "back_transition"))
    prefix = [s for s in phases[:landing_start] if s.name != "cruise"]
    landing = phases[landing_start:]

    def cruise(duration: float) -> Segment:
        return Segment("cruise", duration, x.mission.cruise_height_m,
                       v0_m_s=x.aircraft.cruise_kmh/3.6, mode="wing")

    result: dict[str, Any] = dict(
        feasible=False, earliest_cruise_s=None, max_cruise_s=max_cruise_s, step_s=step_s,
        margin_C=margin_C, limits_C=dict(battery=x.cell.temp_limit_C, motor=x.motor.limit_C,
                                         inverter=x.inverter.temp_limit_C),
        prefix_phases=[s.name for s in prefix], landing_phases=[s.name for s in landing],
        stop_reason=None, trials=[], rows=[])

    out = simulate(x, ns, np, loops, motors, prefix)
    blocked = sorted(set(out.issues) & BLOCKING_FLAGS)
    if blocked:
        result["stop_reason"] = "outbound flight (before cruise) violates: " + ", ".join(blocked)
        result["rows"] = out.rows
        return result

    # Cruise is flown incrementally: each grid point continues from the previous
    # cruise state, so prefix+cruise is simulated only once in total.
    count = math.ceil(max_cruise_s/step_s - 1e-9)
    grid = [min(i*step_s, max_cruise_s) for i in range(count + 1)]
    state, cruise_rows, flown = out.state, [], 0.0
    for t in grid:
        if t > flown:
            leg = simulate(x, ns, np, loops, motors, [cruise(t - flown)], state)
            state, flown = leg.state, t
            cruise_rows.extend(leg.rows)
            blocked = sorted(set(leg.issues) & BLOCKING_FLAGS)
            if blocked:
                # Every longer candidate contains this cruise: no point searching on.
                result["stop_reason"] = f"cruise up to {t:g} s violates: " + ", ".join(blocked)
                break
        land = simulate(x, ns, np, loops, motors, landing, state)
        peaks, reasons = _landing_check(x, land.rows, land.issues, margin_C)
        m = metrics(land.rows)
        passed = not reasons
        result["trials"].append(dict(cruise_s=t, passed=passed, reasons=reasons,
                                     end_min_group_soc=m["end_min_group_soc"],
                                     other_issues=sorted(set(land.issues) - BLOCKING_FLAGS),
                                     **peaks))
        if passed:
            result.update(feasible=True, earliest_cruise_s=t,
                          rows=out.rows + cruise_rows + land.rows)
            break
    else:
        result["stop_reason"] = f"no tested cruise duration up to {max_cruise_s:g} s passed"
    if not result["feasible"] and not result["rows"]:
        result["rows"] = out.rows + cruise_rows + land.rows  # last trial, for inspection
    return result
