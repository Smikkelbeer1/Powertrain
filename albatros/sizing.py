"""Top-level design calculation: from inputs to a complete powertrain design.

run_model() does, in order:
  1. (torque-driven mode only) find the MTOW the given motor torque can carry
  2. series count Ns from the bus voltage ceiling
  3. motor power, torque and MASS                 (propulsion.size_motors)
  4. smallest parallel count Np that flies the mission AND every emergency
     case without violating SOC / current / voltage limits (bisection)
  5. cooling loops for that battery              (cooling.design_cooling)
  6. full thermal simulation of the mission and all emergency branches
  7. mass and volume budget: battery, cooling, motors, (inverters), avionics
"""
from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from . import motor_family
from .balancing import balancing_report
from .cooling import design_cooling
from .electrical import section_counts
from .inputs import ALL, NAMES, Inputs
from .mission import Segment, mission_segments
from .propulsion import MotorSizing, mtow_for_torque, size_motors
from .simulation import ELECTRICAL_FLAGS, metrics, simulate

WARNINGS = [
    "Control/CG alignment unverified; mixed-pair selection and thrust split are assumptions.",
    "Transition path imposed; full power does not prove constant-altitude transition.",
    "Cooling and component masses use uncalibrated estimates; compare vendor maps.",
    "Two-motor contingency assumes intact battery/bus/cooling and immediate attained hover; "
    "no fault-transition/landing analysis.",
]


def validate(x: Inputs) -> None:
    """Fail early with a clear message instead of a confusing error later."""
    a, m, b, c, cell, z = x.aircraft, x.mission, x.battery, x.cooling, x.cell, x.balancing
    aero, p, mot = x.aerodynamics, x.propeller, x.motor
    if a.mass_kg <= 0 or len(a.diameters_m) != 4 or min(a.diameters_m) <= 0:
        raise ValueError("Positive mass and exactly four positive rotor diameters required")
    # Motor
    if len(mot.peak_kW) != 4 or min(mot.peak_kW) < 0:
        raise ValueError("Four non-negative motor peak ratings required")
    if mot.mass_model not in ("family", "fixed"):
        raise ValueError("motor.mass_model must be family or fixed")
    if len(mot.mass_each_kg) != 4 or min(mot.mass_each_kg) <= 0:
        raise ValueError("Four positive motor masses required (motor.mass_each_kg)")
    if mot.peak_torque_Nm < 0 or mot.rating_margin <= 0:
        raise ValueError("Motor peak torque must be >= 0 and rating margin > 0")
    # Aerodynamics and propeller (department inputs)
    if m.transition_power_reference not in ("hover", "rating"):
        raise ValueError("mission.transition_power_reference must be hover or rating")
    if aero.drag_model not in ("lift_drag", "polar"):
        raise ValueError("aerodynamics.drag_model must be lift_drag or polar")
    if aero.lift_drag <= 0 or aero.wing_area_m2 <= 0 or aero.cd0 <= 0 or aero.k_induced < 0:
        raise ValueError("Drag inputs must be positive")
    if p.model not in ("constant", "coefficients"):
        raise ValueError("propeller.model must be constant or coefficients")
    if not len(p.J) == len(p.CT) == len(p.CP) >= 2 or p.J[0] != 0:
        raise ValueError("Propeller J, CT, CP tables must have equal length (>=2) and start at J=0")
    if any(j2 <= j1 for j1, j2 in zip(p.J, p.J[1:])) or min(p.CP) <= 0 or p.CT[0] <= 0:
        raise ValueError("Propeller J must increase, CP must be positive and CT(J=0) positive")
    # Rotor layout and emergency assumptions
    if not a.emergency_pairs or any(
            len(pr) != 2 or len(set(pr)) != 2 or any(i not in ALL for i in pr)
            or not any(i < 2 for i in pr) or not any(i >= 2 for i in pr) for pr in a.emergency_pairs):
        raise ValueError("Emergency pairs must each contain one inner (0/1) and one outer (2/3)")
    if not 0 < a.emergency_inner_thrust_fraction < 1 or not 0 <= a.normal_inner_thrust_fraction < 1:
        raise ValueError("Invalid thrust fractions")
    # Battery
    if not 0 < b.soh <= 1 or not 0 <= b.minimum_soc < b.initial_soc <= 1:
        raise ValueError("Invalid SOC/SOH")
    if not 0 <= b.residual_soc_spread <= z.initial_soc_spread < b.initial_soc - b.minimum_soc:
        raise ValueError("Require 0 <= residual spread <= initial spread < usable SOC")
    if b.bus_min_V <= 0 or b.bus_max_V <= b.bus_min_V or b.max_parallel < 1 or b.parallel_count < 0:
        raise ValueError("Invalid bus window or maximum parallel count")
    if len(cell.ocv_V) < 2 or any(v <= 0 for v in cell.ocv_V) or any(
            p1 > p2 for p1, p2 in zip(cell.ocv_V, cell.ocv_V[1:])):
        raise ValueError("OCV table must be positive and nondecreasing")
    if max(cell.ocv_V) > cell.max_V or cell.form not in ("cylindrical", "pouch", "prismatic"):
        raise ValueError("Cell OCV exceeds charge limit or form unsupported")
    # Mission
    if m.cruise_height_m < m.transition_height_m or m.transition_height_m <= 0:
        raise ValueError("Cruise height must be >= positive transition height")
    if not 0 < m.vertical_accel_m_s2 < 9.80665:
        raise ValueError("Vertical acceleration must be between 0 and g")
    if min(m.dt_s, m.transition_s, m.back_transition_s, m.vertical_speed_m_s, m.wing_climb_m_s,
           m.wing_descent_m_s, m.vertical_descent_m_s) <= 0:
        raise ValueError("Mission rates, transitions and timestep must be positive")
    if min(m.initial_hover_s, m.landing_hover_s, m.cruise_s, a.emergency_s) < 0 or a.emergency_s == 0:
        raise ValueError("Durations must be non-negative, emergency duration positive")
    # Cooling, balancing, drives
    if c.fan_rating_margin <= 0:
        raise ValueError("Fan rating margin must be positive")
    if not 0 < c.hover_rejection_fraction <= 2:
        raise ValueError("Cooling hover fraction must be in (0,2]")
    if not 0 < z.duty <= 1 or not 1 <= z.simultaneous_per_board <= z.channels_per_board:
        raise ValueError("Invalid balancing duty/channel schedule")
    if mot.density_kg_m3 <= 0 or c.pump_density_kg_m3 <= 0 or not 0 < b.volume_fill_fraction <= 1:
        raise ValueError("Motor/pump densities must be positive and battery fill fraction in (0,1]")
    if min(c.fan_depth_m, x.inverter.volume_each_L, x.auxiliaries.avionics_volume_L) < 0:
        raise ValueError("Volumes and fan depth must be non-negative")
    if x.inverter.mode not in ("efficiency", "device"):
        raise ValueError("Inverter mode must be efficiency or device")
    for name, value in [("motor efficiency", mot.efficiency), ("prop_eff", p.cruise_prop_eff),
                        ("FM", p.hover_fm), ("inverter_eff", x.inverter.efficiency),
                        ("pump_eff", c.pump_eff), ("fan_eff", c.fan_eff),
                        ("DC/DC_eff", x.auxiliaries.dc_dc_eff)]:
        if not 0 < value <= 1:
            raise ValueError(name + " must be in (0,1]")
    for obj, names in [
            (cell, ("capacity_Ah", "mass_kg", "resistance_ohm", "cp_J_kgK", "max_current_A")),
            (c, ("thermal_step_max_s", "coolant_cp_J_kgK", "coolant_rho_kg_m3", "coolant_mu_Pas",
                 "coolant_k_W_mK", "prop_flow_delta_K", "battery_flow_delta_K",
                 "radiator_UA_per_m3_W_K", "radiator_depth_m", "channel_gap_m", "hose_min_ID_m")),
            (z, ("resistor_ohm", "board_to_ambient_K_W"))]:
        if any(getattr(obj, n) <= 0 for n in names):
            raise ValueError("Physical properties must be positive: " + ", ".join(names))


def series_count(x: Inputs) -> int:
    """Ns: user value, or as many cells as fit under the full-charge bus ceiling."""
    b, cell = x.battery, x.cell
    ns = b.series_count or math.floor((b.bus_max_V - b.charge_margin_V) / cell.max_V)
    if ns < 4 or ns * cell.max_V > b.bus_max_V - b.charge_margin_V + 1e-8:
        raise ValueError("Series count exceeds full-charge bus ceiling or is too small")
    return ns


def size_parallel_count(x: Inputs, ns: int, motors: MotorSizing,
                        segments: list[Segment]) -> tuple[int, dict[int, tuple[bool, list[str]]]]:
    """Smallest Np for which the mission and ALL emergency branches stay inside
    the electrical limits (or the user's fixed Np).

    More parallel cells -> less current per cell, less voltage sag, more
    energy, so feasibility is (almost) monotonic in Np: double Np until it
    works, then bisect, then double-check the counts just below.
    Returns (Np, cache of {Np: (feasible, reasons)}).
    """
    a, b = x.aircraft, x.battery
    cache: dict[int, tuple[bool, list[str]]] = {}

    def feasible(np: int) -> bool:
        if np in cache:
            return cache[np][0]
        try:
            loops = design_cooling(x, ns, np, motors)
            normal = simulate(x, ns, np, loops, motors, segments, thermal=False,
                              stop_on_electrical=True)
            flags = set(normal.issues) & ELECTRICAL_FLAGS
            # Emergency: start a two-rotor hover from the end of EVERY segment.
            # Stop at the first failing case (we only need to know IF it fails).
            cases = [(alt, state, pair) for _, alt, state in normal.checkpoints
                     for pair in a.emergency_pairs]
            for alt, state, pair in cases:
                if flags:
                    break
                emergency = simulate(x, ns, np, loops, motors,
                                     [Segment("emergency_hover", a.emergency_s, alt,
                                              active=tuple(pair))],
                                     state, thermal=False, stop_on_electrical=True)
                flags.update(set(emergency.issues) & ELECTRICAL_FLAGS)
            cache[np] = (not flags, sorted(flags))
        except ValueError as exc:
            # Only "battery too weak" errors mean infeasible; anything else is a
            # real input error and must be shown to the user.
            if "Battery" not in str(exc) and "Cooling sizing/load" not in str(exc):
                raise
            cache[np] = (False, [str(exc)])
        return cache[np][0]

    if b.parallel_count > 0:
        return b.parallel_count, cache
    low, high = 0, 1
    while high < b.max_parallel and not feasible(high):
        low, high = high, min(b.max_parallel, high * 2)
    if not feasible(high):
        raise ValueError(f"No electrical solution through {b.max_parallel}P: {cache[high][1]}")
    while high - low > 1:
        mid = (high + low) // 2
        if feasible(mid):
            high = mid
        else:
            low = mid
    np = high
    while np > 1 and feasible(np - 1):
        np -= 1
    return np, cache


def motor_issues(x: Inputs, motors: MotorSizing) -> list[str]:
    """Warn when the HPDM mass-torque trendline is used outside its data."""
    issues = []
    lo, hi = motor_family.MASS_RANGE_KG
    if x.motor.mass_model == "family" and any(not lo <= m <= hi for m in motors.mass_kg):
        issues.append("motor mass outside HPDM data range (trendline extrapolated)")
    return issues


def run_model(x: Inputs) -> dict[str, Any]:
    """Size and simulate the complete powertrain. Returns a JSON-ready dict."""
    validate(x)
    x = deepcopy(x)  # never modify the caller's inputs
    if x.motor.peak_torque_Nm > 0:
        x.aircraft.mass_kg = mtow_for_torque(x)
    a, b, cell = x.aircraft, x.battery, x.cell
    ns = series_count(x)
    segments = mission_segments(x)
    motors = size_motors(x, segments)
    np, cache = size_parallel_count(x, ns, motors, segments)

    # Final design: full thermal simulation of mission + every emergency branch.
    loops = design_cooling(x, ns, np, motors)
    normal = simulate(x, ns, np, loops, motors, segments)
    emergencies: list[dict[str, Any]] = []
    all_rows = list(normal.rows)
    # Emergency branches all start from the same mission checkpoint state; they
    # are independent "what if" cases, not added to the mission energy.
    for label, alt, state in normal.checkpoints:
        for pair in a.emergency_pairs:
            sim = simulate(x, ns, np, loops, motors,
                           [Segment("emergency_hover", a.emergency_s, alt, active=tuple(pair))], state)
            emergencies.append(dict(checkpoint=label, altitude_AGL_m=alt,
                                    survivors=[NAMES[i] for i in pair], metrics=metrics(sim.rows),
                                    issues=sim.issues, rows=sim.rows))
            all_rows.extend(sim.rows)
    balance = balancing_report(x, ns, np)

    # ---- Mass budget -------------------------------------------------------
    mass_components: dict[str, float] = {}
    for l in loops:
        for k, value in l.masses_kg.items():
            mass_components[k] = mass_components.get(k, 0.0) + value
    cooling_mass = sum(mass_components.values())
    cells_mass = ns * np * cell.mass_kg
    pack_dry = cells_mass * (1 + b.noncooling_packaging_fraction) + balance["hardware_mass_kg"]
    avionics_mass = (x.auxiliaries.other_avionics_actuators_kg
                     + x.auxiliaries.flight_computer_count * x.auxiliaries.flight_computer_each_kg
                     + x.auxiliaries.voter_kg)
    motors_mass = sum(motors.mass_kg)
    # An integrated inverter is part of the motor mass (HPDM-type motors).
    separate_inverters = 0 if x.inverter.integrated_in_motor else 4
    inverters_mass = separate_inverters * x.inverter.mass_each_kg
    accounted = pack_dry + cooling_mass + motors_mass + inverters_mass + avionics_mass

    # ---- Volume budget [L] -------------------------------------------------
    # Battery pack envelope = bare cell volume / fill fraction (the rest is
    # cold plates, BMS, busbars and housing). Cooling parts come from the loop
    # sizing; motors from mass / assumed density.
    cells_volume = sum(l.acquisition.get("bare_cell_m3", 0.0) for l in loops) * 1000
    volume_components: dict[str, float] = {
        "battery_packs": cells_volume / b.volume_fill_fraction}
    for l in loops:
        for k, value in l.volumes_L.items():  # radiator, fan, pump, hoses, reservoir
            volume_components[k] = volume_components.get(k, 0.0) + value
    volume_components["motors"] = motors_mass / x.motor.density_kg_m3 * 1000
    volume_components["inverters"] = separate_inverters * x.inverter.volume_each_L
    volume_components["avionics"] = x.auxiliaries.avionics_volume_L
    total_volume = sum(volume_components.values())

    # ---- Issues ------------------------------------------------------------
    issues = set(normal.issues)
    issues.update(i for e in emergencies for i in e["issues"])
    issues.update(balance["issues"])
    issues.update(motor_issues(x, motors))
    if ns * cell.max_V > x.inverter.device_rating_V * x.inverter.voltage_usable_fraction:
        issues.add("inverter device voltage margin")
    if accounted > a.mass_kg:
        issues.add("accounted subsystem mass exceeds MTOW")
    packaging: list[dict[str, Any]] = []
    for i in ALL:
        podloops = [l for l in loops if l.pod == i]
        face, volume = sum(l.face_m2 for l in podloops), sum(l.core_m3 for l in podloops) * 1000
        fits = face <= x.cooling.pod_core_face_available_m2 and volume <= x.cooling.pod_core_volume_available_L
        if not fits:
            issues.add("radiator core nacelle allowance exceeded")
        battery_L = sum(l.acquisition.get("bare_cell_m3", 0.0) for l in podloops) * 1000
        packaging.append(dict(pod=NAMES[i], radiator_face_m2=face, radiator_core_L=volume,
                              fits_core_allowance=fits,
                              battery_section_cell_count=section_counts(ns)[i] * np,
                              battery_section_envelope_L=battery_L / b.volume_fill_fraction))

    # ---- Per-motor requirements ------------------------------------------
    requirements: list[dict[str, Any]] = []
    for i, name in enumerate(NAMES):
        requirements.append(dict(
            rotor=name,
            installed_peak_requirement_kW=motors.power_W[i] / 1000,
            rated_torque_Nm=motors.torque_Nm[i],
            motor_mass_kg=motors.mass_kg[i],
            maximum_demand_kW=max(r[name + "_shaft_W"] for r in all_rows) / 1000,
            max_torque_Nm=max(r[name + "_torque_Nm"] for r in all_rows),
            max_rpm=max(r[name + "_rpm"] for r in all_rows),
            max_electrical_Hz=max(r[name + "_electrical_Hz"] for r in all_rows),
            max_phase_rms_A=max(r[name + "_phase_rms_A"] for r in all_rows),
            cruise_shaft_kW=max((r[name + "_shaft_W"] for r in normal.rows if r["phase"] == "cruise"),
                                default=0) / 1000))

    previous = cache.get(np - 1, (False, ["not evaluated (fixed pack)" if b.parallel_count
                                          else "minimum count"]))[1]
    return dict(
        model="Albatros III", inputs=asdict(x),
        mtow_kg=a.mass_kg, design_driver=motors.driver,
        motor_family_fit=motor_family.describe(),
        series=ns, parallel=np, cell_count=ns * np,
        full_charge_V=ns * cell.max_V, nominal_V=ns * cell.nominal_V,
        nominal_energy_kWh=ns * np * cell.nominal_V * cell.capacity_Ah / 1000,
        previous_parallel_failure=previous,
        nominal_metrics=metrics(normal.rows),
        all_case_metrics={k: v for k, v in metrics(all_rows).items()
                          if k.startswith("peak_") or k == "min_bus_V"},
        worst_contingency_end_soc=min(e["metrics"]["end_min_group_soc"] for e in emergencies),
        peak_current_nominal_phase=max(normal.rows, key=lambda row: row["cell_A"])["phase"],
        peak_current_nominal_A=max(row["cell_A"] for row in normal.rows),
        sizing_mode="fixed parallel count" if b.parallel_count else "automatic electrical sizing",
        nominal_issues=normal.issues, issues=sorted(issues), warnings=WARNINGS,
        balancing=balance, cooling_loops=[asdict(l) for l in loops],
        cooling_masses_kg=mass_components, cooling_total_kg=cooling_mass,
        battery_cells_kg=cells_mass, battery_dry_with_BMS_kg=pack_dry,
        motors_total_kg=motors_mass, inverters_total_kg=inverters_mass,
        avionics_kg=avionics_mass,
        accounted_subsystems_kg=accounted, remaining_MTOW_kg=a.mass_kg - accounted,
        battery_bare_volume_L=cells_volume,
        battery_pack_envelope_estimate_L=volume_components["battery_packs"],
        volumes_L=volume_components, total_volume_L=total_volume,
        radiator_packaging=packaging, drive_requirements=requirements,
        mission_segments=[asdict(s) for s in segments], mission_rows=normal.rows,
        emergencies=emergencies)


def sweep_values(start: float, stop: float, step: float) -> list[float]:
    """start, start+step, ..., stop (inclusive), for --sweep / --sweep-torque."""
    if step <= 0 or start <= 0 or stop < start:
        raise ValueError("Sweep requires 0 < START <= STOP and STEP > 0")
    count = math.floor((stop - start) / step + 1e-9) + 1
    if count > 10000:
        raise ValueError("Sweep would exceed 10,000 designs; increase step")
    return [start + i * step for i in range(count)]
