#!/usr/bin/env python3
"""ALBATROS MODEL III -- conceptual sizing, Python 3.10 or newer.

QUICK START (only plotting needs a third-party package):
  python albatros_model_III.py --mass 750 --csv mission.csv --json design.json
  python albatros_model_III.py --sweep 300 1500 100 --csv sweep.csv --plot
  python albatros_model_III.py --mass 850 --plot --save-plot mission.png
  python albatros_model_III.py --write-config inputs.json
  python albatros_model_III.py --config inputs.json --mass 850
  python albatros_model_III.py --mass 750 --parallel 38
  python albatros_model_III.py --self-test
  python -m pip install matplotlib

Edit the dataclasses below, or generate/edit inputs.json. CLI values override
JSON values. A sweep accepts floating-point mass steps; cell counts remain
integers so results are not mathematically continuous. By default a sweep
REDESIGNS the battery, cooling and automatic motor ratings at each mass. A
fixed --parallel locks only Np; it does not lock the radiator design. MTOW is an INPUT, not
an iterated sum: remaining mass must accommodate airframe, rotors, payload etc.

WHAT CHANGED FROM MODEL II
* Exactly four rotors: inner_L/R 1.47 m; outer_L/R 1.04 m.
* Mixed inner/outer emergency pairs only. Default cross-wing pairs (0,3),(1,2)
  are ASSUMED candidate pairs, not certified controllable combinations. A
  configurable inner thrust fraction replaces area-optimal emergency sharing.
* Prescribed altitude/speed mission, ISA pressure and temperature-offset density;
  accelerate to 6 m/s and brake at 60 m, then transition at constant height.
  60 m is a user planning input, NOT an EASA take-off-height compliance claim.
* 190S default: 798 V charge ceiling, 684 V nominal, 500 V minimum bus.
  This means an '800 V class' battery, NOT a regulated 800 V bus.
* P45B-like 21700 data carried forward. Pouch/prismatic geometry supported by
  editing Cell; do not reuse P45B electrical data for a different real cell.
* Passive balancing of SERIES GROUPS (each contains Np parallel cells), with
  resistor/FET heat, scheduling duty, board thermal derating, time and mass.
  Ground top-balancing workload is estimated independently; flight starts at
  the specified residual imbalance. No charging model or in-flight balancing.
* Three flight computers plus voter and sensor/actuator/DC-DC power.
* Eight coolant circuits: four local motor+inverter loops and four local wing
  battery loops. One battery section near each pod. Two radiator cores per pod.
  Electrical sections are in SERIES; all sections remain available after a
  motor/inverter shutdown. A battery section or common-bus failure is NOT covered.
* Radiators sized to 70% of normal hover waste HEAT, not 70% of shaft power.
  Pump flow handles 100% of normal hover heat at its design liquid temperature
  rise. Transient temperatures decide whether this proposed sizing is enough.
* Core mass tied to both required UA and face area using an explicit assumed
  UA-per-core-volume. Vendor pressure/flow/UA maps must replace this estimate.

EQUATIONS AND SOURCES (links are references, not automatic data downloads)
[1] P45B manufacturer specification, 4.5 Ah, 3.6 V, 4.2/2.5 V, 45 A:
https://www.molicel.com/wp-content/uploads/INR21700P45B_1.4_Product-Data-Sheet-of-INR-21700-P45B-80109.pdf
70 g is the inherited conservative cell mass. 15 mOhm is an inherited constant
DC resistance ASSUMPTION, not a measured SOC/temperature-dependent resistance
map. The OCV table, cp, thermal resistance and entropy coefficient are also
assumptions. Do not substitute the datasheet AC impedance for DC resistance.
[2] Passive balancing principles and thermal/duty constraints:
https://www.ti.com/lit/an/sluaa81a/sluaa81a.pdf
The default external resistor and board model are generic, NOT a BQ76952
stacking circuit. A real ~800 V BMS needs suitable isolated, stackable hardware.
[3] Atmosphere reference:
https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html
Implementation uses standard troposphere hydrostatic ideal-gas equations.
[4] Heat exchanger effectiveness-NTU relationships:
https://www.mathworks.com/help/hydro/ref/entuheattransfer.html
Counterflow is an idealised surrogate; crossflow radiator performance must be
calibrated. Darcy-Weisbach, smooth-pipe Blasius, wide-slot laminar Nu=7.54 and
Dittus-Boelter are textbook correlations, not vendor performance guarantees.
[5] Aircraft thermal-management architecture context:
https://ntrs.nasa.gov/citations/20200001620

Hover: Pshaft_i = Ti*sqrt(Ti/(2*rho*Ai))/FM. Axial climb uses induced velocity
sqrt((vz/2)^2+Ti/(2*rho*Ai))-vz/2, hence shaft power Ti*(vz+vi)/FM.
Wingborne: Pshaft = max(0, W*V/(L/D)+W*vz+m*V*ax)/eta_prop.
Transition: imposed fraction of installed peak shaft power; trajectory is NOT
solved aerodynamically. Landing descent uses hover-equivalent power, because
simple axial momentum theory is unreliable in vortex-ring/windmill regimes.
Motor heat: Pshaft*(1/eta_motor-1); inverter heat: Pmotor*(1/eta_inv-1),
or optional approximate 2-level SiC device losses, NOT a validated device map.
Battery: P=I*(Voc-I*R); discriminant Voc^2-4*R*P. Negative discriminant means
requested constant power cannot be supplied in this equivalent circuit.
Qirr=I^2*R; Qrev=-I*T*dVoc/dT (positive current discharges).
Thermal nodes: m*cp*dT/dt=generated heat - transferred heat.

BOUNDARIES
No 6-DOF flight dynamics, control allocation, structural strength, certification,
thermal-runaway containment, fault-isolation design, motor back-EMF/field-
weakening map or hottest-cell/junction model. Thermal temperatures are lumped
averages. Motor mass includes its jacket; inverter coldplate is counted
separately. Rotor/mount/airframe masses remain in the unallocated MTOW budget.
Waterdrop pod inputs describe a radiator packaging allowance only: no CFD,
external nacelle drag or guaranteed propwash recovery. Ram-air cooling drag
is estimated from the heat-exchanger pressure drop. Pump/fan/mass assumptions
are intentionally visible. Automatic ratings are procurement REQUIREMENTS,
not claims that an off-the-shelf motor of the assumed mass meets them.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

NAMES = ("inner_L", "inner_R", "outer_L", "outer_R")
ALL = (0, 1, 2, 3)


@dataclass
class Aircraft:
    mass_kg: float = 750.0
    diameters_m: tuple[float, ...] = (1.47, 1.47, 1.04, 1.04)
    cruise_kmh: float = 234.0
    lift_drag: float = 18.0
    hover_fm: float = 0.6411
    cruise_prop_eff: float = 0.78
    ct_hover: float = 0.10  # T=CT*rho*n^2*D^4; n is rev/s, NOT rad/s.
    cruise_rpm: float = 3061.0
    motor_eff: float = 0.90
    motor_pole_pairs: int = 5
    motor_mass_each_kg: float = 40.0  # placeholder; match supplier power/torque map
    motor_cp_J_kgK: float = 500.0  # specific heat capacity, not power coefficient
    motor_to_coolant_W_K: float = 600.0  # UA including internal thermal path
    motor_limit_C: float = 120.0
    motor_peak_kW: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)  # 0=derive requirement
    rating_margin: float = 1.10
    emergency_s: float = 30.0
    emergency_pairs: tuple[tuple[int, int], ...] = ((0, 3), (1, 2))
    emergency_inner_thrust_fraction: float = 0.50  # geometry/control assumption
    normal_inner_thrust_fraction: float = 0.0  # 0=area-weighted, editable otherwise
    electrical_Hz_limit: float = 2000.0  # assumed drive capability, NOT PWM frequency
    tip_mach_limit: float = 0.85  # screening input


@dataclass
class Mission:
    field_elevation_m: float = 0.0  # MSL
    transition_height_m: float = 60.0  # AGL planning input
    vertical_speed_m_s: float = 6.0
    vertical_accel_m_s2: float = 1.0
    initial_hover_s: float = 20.0
    transition_s: float = 20.0
    transition_peak_fraction: float = 1.0
    cruise_height_m: float = 600.0  # AGL assumption
    wing_climb_m_s: float = 3.0
    cruise_s: float = 3000.0  # retain earlier 50-minute cruise
    wing_descent_m_s: float = 3.0
    back_transition_s: float = 20.0
    back_transition_peak_fraction: float = 0.70
    landing_hover_s: float = 30.0
    vertical_descent_m_s: float = 2.0
    dt_s: float = 2.0


@dataclass
class Cell:
    name: str = "P45B-like 21700 (inherited assumptions)"
    form: str = "cylindrical"  # cylindrical, pouch, prismatic: geometry only
    capacity_Ah: float = 4.5
    nominal_V: float = 3.6
    max_V: float = 4.2
    min_V: float = 2.5
    max_current_A: float = 45.0
    resistance_ohm: float = 0.015
    mass_kg: float = 0.070
    diameter_m: float = 0.0216
    height_m: float = 0.0702
    width_m: float = 0.100  # flat-cell placeholder, ignored for cylindrical
    thickness_m: float = 0.010
    cp_J_kgK: float = 1000.0
    core_to_surface_K_W: float = 3.0
    contact_fraction: float = 0.30
    temp_limit_C: float = 55.0
    entropy_dU_dT_V_K: float = 0.0  # Qrev=-I*T*dU/dT; unknown, disabled
    ocv_V: tuple[float, ...] = (2.50, 3.15, 3.38, 3.52, 3.61, 3.69,
                               3.77, 3.85, 3.94, 4.02, 4.15)


@dataclass
class Battery:
    bus_max_V: float = 800.0  # charge ceiling; inverter transient margin is separate
    bus_min_V: float = 500.0  # assumption: replace with selected drive requirement
    series_count: int = 0  # 0=floor((bus_max-charge_margin)/cell.max_V)
    charge_margin_V: float = 0.0  # design tolerance allowance, not transient allowance
    initial_soc: float = 1.0  # highest group at departure
    residual_soc_spread: float = 0.002  # highest minus weakest group after balancing
    minimum_soc: float = 0.20  # weakest group reserve, also after emergency hover
    soh: float = 1.0
    resistance_age_factor: float = 1.0
    noncooling_packaging_fraction: float = 0.15  # cells * fraction; excludes TMS/BMS
    volume_fill_fraction: float = 0.65
    max_parallel: int = 250
    parallel_count: int = 0  # 0=automatic; fixed positive Np evaluates an existing pack


@dataclass
class Balancing:
    enabled: bool = True
    initial_soc_spread: float = 0.01  # ground workload before balancing
    resistor_ohm: float = 42.0  # ~100 mA at 4.2 V, EXTERNAL bleed path
    switch_ohm: float = 0.10
    resistor_rating_W: float = 1.0
    resistor_usable_fraction: float = 0.50
    duty: float = 0.70  # ADC quiet intervals, scheduling, thermal pauses
    channels_per_board: int = 16  # generic isolated monitor board, not selected IC
    simultaneous_per_board: int = 4
    board_to_ambient_K_W: float = 15.0
    board_base_W: float = 0.25
    board_limit_C: float = 80.0
    board_mass_kg: float = 0.060
    channel_mass_kg: float = 0.002
    master_and_harness_kg: float = 0.60
    minimum_balancing_soc: float = 0.90


@dataclass
class Inverter:
    mode: str = "efficiency"  # or device: approximate two-level six-switch bridge
    efficiency: float = 0.98
    switching_Hz: float = 20000.0
    power_factor: float = 0.90
    modulation_fraction: float = 0.90
    parallel_devices_per_switch: int = 4
    rds_hot_ohm: float = 0.016
    switching_energy_J: float = 0.002  # per device Eon+Eoff at references below
    reference_V: float = 800.0
    reference_A: float = 100.0
    gate_charge_C: float = 200e-9
    gate_voltage_V: float = 18.0
    control_power_W: float = 15.0
    mass_each_kg: float = 4.0
    cp_J_kgK: float = 800.0
    to_coolant_W_K: float = 300.0
    temp_limit_C: float = 85.0  # lumped assembly, NOT silicon junction temperature
    device_rating_V: float = 1200.0
    voltage_usable_fraction: float = 0.80
    phase_rms_limit_A: float = 0.0  # 0=report required rating, not a selected drive


@dataclass
class Auxiliaries:
    flight_computer_count: int = 3
    flight_computer_each_W: float = 80.0
    flight_computer_each_kg: float = 0.80
    voter_W: float = 10.0
    voter_kg: float = 0.20
    sensors_W: float = 50.0
    communications_W: float = 40.0
    bms_master_W: float = 30.0
    actuator_count: int = 8
    actuator_active_W: float = 100.0
    actuator_idle_W: float = 5.0
    actuator_cruise_duty: float = 0.10
    actuator_manoeuvre_duty: float = 0.50
    dc_dc_eff: float = 0.94
    low_voltage_V: float = 28.0
    other_avionics_actuators_kg: float = 5.0
    # Voting power/mass only: independent supplies, software and common causes
    # require a separate architecture assessment. This does not simulate votes.


@dataclass
class Cooling:
    sea_level_ambient_C: float = 25.0
    initial_C: float = 30.0
    hover_rejection_fraction: float = 0.70
    coolant_cp_J_kgK: float = 3600.0
    coolant_rho_kg_m3: float = 1050.0
    coolant_mu_Pas: float = 0.003
    coolant_k_W_mK: float = 0.42
    prop_flow_delta_K: float = 15.0
    battery_flow_delta_K: float = 5.0
    prop_hot_coolant_design_C: float = 60.0
    battery_hot_coolant_design_C: float = 35.0
    prop_line_length_m: float = 2.0  # supply+return per pod, short local hoses
    battery_line_length_m: float = 3.0  # supply+return from wing section to pod
    hose_speed_m_s: float = 1.5
    hose_min_ID_m: float = 0.006
    hose_wall_m: float = 0.0015
    hose_rho_kg_m3: float = 1200.0  # dry hose material ONLY; coolant separately
    minor_loss_K: float = 10.0
    radiator_liquid_dp_Pa: float = 20000.0
    motor_jacket_dp_Pa: float = 50000.0
    pump_eff: float = 0.55
    pump_head_margin: float = 1.20
    pump_min_mass_kg: float = 0.50
    pump_mass_kg_per_kW: float = 2.0
    air_cp_J_kgK: float = 1005.0
    air_design_rise_K: float = 5.0
    radiator_air_dp_Pa: float = 500.0
    radiator_face_speed_m_s: float = 5.0
    ram_pressure_recovery: float = 0.70
    inlet_velocity_capture: float = 0.70
    fan_eff: float = 0.60
    fan_rating_margin: float = 1.25  # electrical headroom for lower air density
    fan_mass_kg_per_kW: float = 1.0
    radiator_depth_m: float = 0.06
    radiator_UA_per_m3_W_K: float = 100000.0  # ASSUMED at design air/liquid flow
    radiator_envelope_density_kg_m3: float = 150.0
    radiator_header_kg: float = 0.40
    radiator_coolant_volume_fraction: float = 0.08
    pod_core_face_available_m2: float = 0.18  # per waterdrop nacelle, editable
    pod_core_volume_available_L: float = 12.0  # radiator cores only, not whole pod
    channel_wall_m: float = 0.0005
    channel_gap_m: float = 0.002
    cells_per_ribbon: int = 20
    ribbon_pitch_m: float = 0.025
    tim_thickness_m: float = 0.0005
    tim_k_W_mK: float = 2.0
    tim_rho_kg_m3: float = 2000.0
    aluminum_rho_kg_m3: float = 2700.0
    aluminum_k_W_mK: float = 180.0
    battery_manifold_each_kg: float = 0.50
    inverter_plate_each_kg: float = 0.50
    reservoirs_each_kg: float = 0.40
    fittings_each_loop_kg: float = 0.40
    coolant_reserve_each_loop_L: float = 0.25
    jacket_and_plate_fluid_each_L: float = 0.20
    thermal_step_max_s: float = 0.50


@dataclass
class Inputs:
    aircraft: Aircraft = field(default_factory=Aircraft)
    mission: Mission = field(default_factory=Mission)
    cell: Cell = field(default_factory=Cell)
    battery: Battery = field(default_factory=Battery)
    balancing: Balancing = field(default_factory=Balancing)
    inverter: Inverter = field(default_factory=Inverter)
    auxiliaries: Auxiliaries = field(default_factory=Auxiliaries)
    cooling: Cooling = field(default_factory=Cooling)


@dataclass
class Segment:
    name: str
    duration_s: float
    h0_m: float
    vz0_m_s: float = 0.0
    az_m_s2: float = 0.0
    v0_m_s: float = 0.0
    ax_m_s2: float = 0.0
    mode: str = "hover"
    power_fraction: float = 1.0
    active: tuple[int, ...] = ALL


@dataclass
class RotorPoint:
    thrust_N: float = 0.0
    shaft_W: float = 0.0
    rpm: float = 0.0
    torque_Nm: float = 0.0
    electrical_Hz: float = 0.0
    tip_mach: float = 0.0


@dataclass
class DrivePoint:
    dc_W: float = 0.0
    motor_heat_W: float = 0.0
    inverter_heat_W: float = 0.0
    phase_rms_A: float = 0.0


@dataclass
class ElectricalPoint:
    current_A: float
    voltage_V: float
    heat_W: float
    min_cell_V: float
    terminal_W: float
    drives: list[DrivePoint]


@dataclass
class State:
    time_s: float
    soc_mean: float
    soc_min: float
    battery_C: list[float]
    motor_C: list[float]
    inverter_C: list[float]
    coolant_C: list[float]


@dataclass
class Loop:
    name: str
    pod: int
    is_battery: bool
    heat_design_W: float
    liquid_kg_s: float
    flow_L_min: float
    pump_head_Pa: float
    pump_W: float
    hose_ID_m: float
    hose_Re: float
    air_kg_s: float
    face_m2: float
    core_m3: float
    UA_W_K: float
    inlet_m2: float
    full_fan_W: float  # requested fan power at ground design flow
    fan_rating_W: float
    coolant_kg: float
    acquisition_UA_W_K: float
    masses_kg: dict[str, float]
    acquisition: dict[str, float]


@dataclass
class Simulation:
    rows: list[dict[str, Any]]
    state: State
    issues: list[str]
    checkpoints: list[tuple[str, float, State]]


def atmosphere(msl_m: float, sea_level_C: float) -> tuple[float, float, float]:
    """Troposphere pressure; offset ISA temperature, ideal gas rho; returns rho,T,a."""
    if not -500 <= msl_m <= 11000:
        raise ValueError("Atmosphere model requires -500 <= MSL altitude <= 11000 m")
    t_isa = 288.15 - 0.0065 * msl_m
    pressure = 101325.0 * (t_isa / 288.15) ** (9.80665 / (287.05 * 0.0065))
    temp_K = t_isa + sea_level_C - 15.0
    return pressure / (287.05 * temp_K), temp_K - 273.15, math.sqrt(1.4 * 287.05 * temp_K)


def ocv(soc: float, cell: Cell) -> float:
    """Placeholder piecewise-linear OCV table, equally spaced in SOC 0..1."""
    x = min(1.0, max(0.0, soc)) * (len(cell.ocv_V) - 1)
    i = min(int(x), len(cell.ocv_V) - 2)
    return cell.ocv_V[i] + (x-i) * (cell.ocv_V[i+1]-cell.ocv_V[i])


def mission_segments(x: Inputs) -> list[Segment]:
    m, v = x.mission, x.aircraft.cruise_kmh / 3.6
    # Accelerate and decelerate symmetrically; use triangular profile if too short.
    vmax = min(m.vertical_speed_m_s, math.sqrt(m.transition_height_m*m.vertical_accel_m_s2))
    ta = vmax/m.vertical_accel_m_s2
    ha = 0.5*m.vertical_accel_m_s2*ta**2
    tc = max(0.0, (m.transition_height_m-2*ha)/vmax)
    h = m.transition_height_m
    result = [Segment("takeoff_hover", m.initial_hover_s, 0),
              Segment("vertical_accelerate", ta, 0, az_m_s2=m.vertical_accel_m_s2),
              Segment("vertical_climb", tc, ha, vz0_m_s=vmax),
              Segment("vertical_brake", ta, h-ha, vmax, -m.vertical_accel_m_s2),
              Segment("transition", m.transition_s, h, ax_m_s2=v/m.transition_s,
                      mode="transition", power_fraction=m.transition_peak_fraction),
              Segment("cruise_climb", (m.cruise_height_m-h)/m.wing_climb_m_s,
                      h, m.wing_climb_m_s, v0_m_s=v, mode="wing"),
              Segment("cruise", m.cruise_s, m.cruise_height_m, v0_m_s=v, mode="wing"),
              Segment("cruise_descent", (m.cruise_height_m-h)/m.wing_descent_m_s,
                      m.cruise_height_m, -m.wing_descent_m_s, v0_m_s=v, mode="wing"),
              Segment("back_transition", m.back_transition_s, h, v0_m_s=v,
                      ax_m_s2=-v/m.back_transition_s, mode="transition",
                      power_fraction=m.back_transition_peak_fraction),
              Segment("landing_hover", m.landing_hover_s, h),
              Segment("vertical_descent", h/m.vertical_descent_m_s, h,
                      -m.vertical_descent_m_s, mode="descent")]
    return [s for s in result if s.duration_s > 0]


def thrust_fractions(a: Aircraft, active: tuple[int, ...]) -> list[float]:
    weights = [0.0]*4
    inner = [i for i in active if i < 2]
    outer = [i for i in active if i >= 2]
    if len(active) == 2:
        f = a.emergency_inner_thrust_fraction
    elif a.normal_inner_thrust_fraction > 0:
        f = a.normal_inner_thrust_fraction
    else:
        area = [a.diameters_m[i]**2 for i in active]
        for i, ai in zip(active, area):
            weights[i] = ai/sum(area)
        return weights
    for i in inner:
        weights[i] = f/len(inner)
    for i in outer:
        weights[i] = (1-f)/len(outer)
    return weights


def propulsion(x: Inputs, s: Segment, t: float, ratings_W: list[float],
               cooling_drag_W: float = 0.0) -> list[RotorPoint]:
    a, m = x.aircraft, x.mission
    h = s.h0_m+s.vz0_m_s*t+0.5*s.az_m_s2*t*t
    rho, _, sound = atmosphere(m.field_elevation_m+h, x.cooling.sea_level_ambient_C)
    vz, v = s.vz0_m_s+s.az_m_s2*t, max(0.0, s.v0_m_s+s.ax_m_s2*t)
    W = a.mass_kg*9.80665
    weights = thrust_fractions(a, s.active)
    result: list[RotorPoint] = []
    for i in ALL:
        if i not in s.active:
            result.append(RotorPoint())
            continue
        frac = weights[i]
        d = a.diameters_m[i]
        if s.mode == "transition":
            # Power command, not a solved aerodynamic force balance. RPM interpolates
            # between indicative hover RPM and commanded cruise RPM.
            thrust = W*frac
            hover_rpm = 60*math.sqrt(thrust/(a.ct_hover*rho*d**4))
            blend = min(1.0, v/(a.cruise_kmh/3.6))
            rpm = (1-blend)*hover_rpm+blend*a.cruise_rpm
            power = s.power_fraction*ratings_W[i]
        elif s.mode == "wing":
            thrust = max(0.0, W/a.lift_drag+W*vz/max(v, 1.0)+a.mass_kg*s.ax_m_s2)*frac
            power = (max(0.0, W*v/a.lift_drag+W*vz+a.mass_kg*v*s.ax_m_s2)
                     +cooling_drag_W)*frac/a.cruise_prop_eff
            rpm = a.cruise_rpm if power > 0 else 0.0
        else:
            thrust = a.mass_kg*max(0.0, 9.80665+s.az_m_s2)*frac
            vi_sq = thrust/(2*rho*math.pi*d*d/4)
            axial = max(0.0, vz)  # conservative hover surrogate in descent, no regen
            power = thrust*(axial/2+math.sqrt((axial/2)**2+vi_sq))/a.hover_fm
            rpm = 60*math.sqrt(thrust/(a.ct_hover*rho*d**4))
        omega = rpm*2*math.pi/60
        result.append(RotorPoint(thrust, power, rpm, power/omega if omega else 0.0,
                                 a.motor_pole_pairs*rpm/60,
                                 math.hypot(math.pi*d*rpm/60, v)/sound))
    return result


def motor_ratings(x: Inputs, segments: list[Segment]) -> list[float]:
    """Required mechanical rating, including mixed-pair hover at cruise altitude."""
    peaks = [0.0]*4
    probes = [s for s in segments if s.mode != "transition"]
    probes += [Segment("emergency", x.aircraft.emergency_s, x.mission.cruise_height_m,
                       active=tuple(pair)) for pair in x.aircraft.emergency_pairs]
    for s in probes:
        for t in (0.0, s.duration_s):
            for i, r in enumerate(propulsion(x, s, t, [0.0]*4)):
                peaks[i] = max(peaks[i], r.shaft_W)
    return [given*1000 if given > 0 else p*x.aircraft.rating_margin
            for given, p in zip(x.aircraft.motor_peak_kW, peaks)]


def inverter_point(x: Inputs, shaft_W: float, voltage: float) -> DrivePoint:
    if shaft_W <= 0:
        return DrivePoint()
    inv = x.inverter
    motor_W = shaft_W/x.aircraft.motor_eff
    line_rms_V = inv.modulation_fraction*voltage/math.sqrt(2)
    phase_A = motor_W/(math.sqrt(3)*line_rms_V*inv.power_factor)
    if inv.mode == "efficiency":
        loss = motor_W*(1/inv.efficiency-1)
    else:
        # Balanced sinusoidal phase currents. Device energies scale linearly here;
        # diode/reverse recovery, dead time and temperature maps are not resolved.
        n = inv.parallel_devices_per_switch
        conduction = 3*phase_A**2*inv.rds_hot_ohm/n
        avg_device_A = 2*math.sqrt(2)*phase_A/(math.pi*n)
        switching = 6*n*inv.switching_Hz*inv.switching_energy_J*(voltage/inv.reference_V)*(avg_device_A/inv.reference_A)
        gate = 6*n*inv.gate_charge_C*inv.gate_voltage_V*inv.switching_Hz
        loss = conduction+switching+gate+inv.control_power_W
    return DrivePoint(motor_W+loss, motor_W-shaft_W, loss, phase_A)


def battery_point(power_W: float, soc: float, weakest_soc: float,
                  ns: int, np: int, x: Inputs) -> tuple[float, float, float, float]:
    """Constant-R Thevenin model, stable lower-current solution of quadratic.

    Mean-SOC OCV approximates the series sum for a small residual SOC spread.
    The weakest group's voltage and reserve are independently checked. Cells
    within a parallel group are assumed identical/equal-sharing, not simulated.
    """
    cell, b = x.cell, x.battery
    voltage = ns*ocv(soc, cell)
    resistance = ns*cell.resistance_ohm*b.resistance_age_factor/np
    discriminant = voltage**2-4*resistance*power_W
    if discriminant < 0:
        raise ValueError("Battery equivalent-circuit maximum power exceeded")
    current = 2*power_W/(voltage+math.sqrt(discriminant)) if power_W else 0.0
    cell_drop = current*resistance/ns
    return current, voltage-current*resistance, current**2*resistance, ocv(weakest_soc, cell)-cell_drop


def electrical(x: Inputs, rotors: list[RotorPoint], other_W: float, state: State,
               ns: int, np: int) -> ElectricalPoint:
    voltage = ns*ocv(state.soc_mean, x.cell)
    for _ in range(60):  # iteration limit, NOT 60 seconds; converge voltage-dependent loss
        drives = [inverter_point(x, r.shaft_W, voltage) for r in rotors]
        power = sum(e.dc_W for e in drives)+other_W
        current, new_V, heat, min_cell = battery_point(power, state.soc_mean, state.soc_min, ns, np, x)
        if abs(new_V-voltage) < 1e-5:
            return ElectricalPoint(current, new_V, heat, min_cell, power, drives)
        voltage = (voltage+new_V)/2
    raise ValueError("Battery/inverter voltage iteration did not converge")


def board_count(ns: int, balancing: Balancing) -> int:
    return sum(math.ceil(n/balancing.channels_per_board) for n in section_counts(ns))


def auxiliary_power(x: Inputs, wingborne: bool, ns: int) -> float:
    aux = x.auxiliaries
    duty = aux.actuator_cruise_duty if wingborne else aux.actuator_manoeuvre_duty
    lowV = (aux.flight_computer_count*aux.flight_computer_each_W+aux.voter_W+
            aux.sensors_W+aux.communications_W+aux.bms_master_W+
            board_count(ns, x.balancing)*x.balancing.board_base_W+
            aux.actuator_count*(duty*aux.actuator_active_W+(1-duty)*aux.actuator_idle_W))
    return lowV/aux.dc_dc_eff


def section_counts(ns: int) -> list[int]:
    return [ns//4+(1 if i < ns % 4 else 0) for i in ALL]


def balancing_report(x: Inputs, ns: int, np: int) -> dict[str, Any]:
    """Ground equalisation workload, NOT a charger simulation.

    One resistor channel spans one series group of Np parallel cells. Required
    charge removal is Np*Ah*SOH*deltaSOC. Average current includes duty and board
    thermal derating. Work is scheduled across board channels; estimates use
    constant top-of-charge voltage and uniform initial SOC spread. Disabled
    balancing preserves the initial spread in the flight model.
    """
    z, b, cell = x.balancing, x.battery, x.cell
    voltage = ocv(b.initial_soc, cell)
    on_A = voltage/(z.resistor_ohm+z.switch_ohm)
    resistor_W = on_A**2*z.resistor_ohm
    fet_W = on_A**2*z.switch_ohm
    heat_per_channel = resistor_W+fet_W
    thermal_budget_W = max(0.0, (z.board_limit_C-x.cooling.sea_level_ambient_C)/z.board_to_ambient_K_W-z.board_base_W)
    duty = min(z.duty, thermal_budget_W/(z.simultaneous_per_board*heat_per_channel))
    target = b.residual_soc_spread
    spread = z.initial_soc_spread
    excess = max(0.0, spread-target)
    worst_Ah = np*cell.capacity_Ah*b.soh*excess
    max_boards_time_h = 0.0
    total_removed_Ah = 0.0
    max_board_heat_W = 0.0
    for count in section_counts(ns):
        for first in range(0, count, z.channels_per_board):
            n = min(z.channels_per_board, count-first)
            # Evenly distributed group SOC; same distribution assumed in each board.
            charges = [np*cell.capacity_Ah*b.soh*max(0.0, spread*i/max(1,n-1)-target) for i in range(n)]
            total_removed_Ah += sum(charges)
            if duty > 0:
                board_time = max(max(charges, default=0.0), sum(charges)/z.simultaneous_per_board)/(on_A*duty)
                max_boards_time_h = max(max_boards_time_h, board_time)
            max_board_heat_W = max(max_board_heat_W, min(n,z.simultaneous_per_board)*heat_per_channel*duty+z.board_base_W)
    issues: list[str] = []
    if resistor_W > z.resistor_rating_W*z.resistor_usable_fraction:
        issues.append("Bleed resistor exceeds derated ON-state power rating")
    if b.initial_soc-spread < z.minimum_balancing_soc:
        issues.append("Some groups below chosen top-balancing SOC threshold; charging model needed")
    if duty <= 0 and excess > 0:
        issues.append("No board thermal budget for balancing")
    return dict(enabled=z.enabled, series_group_channels=ns, monitor_boards=board_count(ns,z),
                on_current_A=on_A, effective_duty=duty, average_channel_A=on_A*duty,
                resistor_on_W=resistor_W, switch_on_W=fet_W,
                worst_group_charge_to_remove_Ah=worst_Ah,
                estimated_ground_hours=max_boards_time_h if z.enabled and duty > 0 else None,
                ground_energy_dissipated_Wh=voltage*total_removed_Ah if z.enabled else 0.0,
                maximum_board_heat_W=max_board_heat_W,
                estimated_board_C=x.cooling.sea_level_ambient_C+z.board_to_ambient_K_W*max_board_heat_W,
                hardware_mass_kg=board_count(ns,z)*z.board_mass_kg+ns*z.channel_mass_kg+z.master_and_harness_kg,
                flight_balancing_W=0.0, issues=issues,
                note="Ground-only constant-voltage workload estimate; residual flight imbalance is an input, not a simulated charging outcome.")


def hose_pressure(flow: float, diameter: float, length: float, c: Cooling) -> tuple[float, float]:
    velocity = flow/(math.pi*diameter**2/4)
    re = c.coolant_rho_kg_m3*velocity*diameter/c.coolant_mu_Pas
    f = 64/max(re,1e-12) if re < 2300 else 0.3164/re**0.25
    return (f*length/diameter+c.minor_loss_K)*c.coolant_rho_kg_m3*velocity**2/2, re


def battery_plate(x: Inputs, count: int, flow: float) -> dict[str, float]:
    """Side-contact ribbon for round cells; one broad coldplate face for flat cells.

    Rcell = Rcore + RTIM + Rwall + Rconvection, in K/W PER CELL.
    Identical cells/parallel passages give UA=count/Rcell. Channel mass includes
    two walls and side edges. Fluid and TIM are separately accounted for.
    """
    c, cell = x.cooling, x.cell
    if cell.form == "cylindrical":
        contact = cell.contact_fraction*math.pi*cell.diameter_m*cell.height_m
        branches = math.ceil(count/c.cells_per_ribbon)
        length, width = c.cells_per_ribbon*c.ribbon_pitch_m, cell.height_m
        bare_volume = count*math.pi*cell.diameter_m**2*cell.height_m/4
    else:
        contact = cell.width_m*cell.height_m
        branches, length, width = count, cell.height_m, cell.width_m
        bare_volume = count*cell.width_m*cell.height_m*cell.thickness_m
    gap, wall = c.channel_gap_m, c.channel_wall_m
    dh = 2*width*gap/(width+gap)
    velocity = flow/(branches*width*gap)
    re = c.coolant_rho_kg_m3*velocity*dh/c.coolant_mu_Pas
    f = 96/max(re,1e-12) if re < 2300 else 0.3164/re**0.25
    pr = c.coolant_cp_J_kgK*c.coolant_mu_Pas/c.coolant_k_W_mK
    nu = 7.54 if re < 2300 else 0.023*re**0.8*pr**0.4
    h = nu*c.coolant_k_W_mK/dh
    resistance = (cell.core_to_surface_K_W+c.tim_thickness_m/(c.tim_k_W_mK*contact)+
                  wall/(c.aluminum_k_W_mK*contact)+1/(h*contact))
    return dict(branches=float(branches), hydraulic_diameter_m=dh, Reynolds=re,
                channel_velocity_m_s=velocity, channel_length_m=length,
                channel_dp_Pa=(f*length/dh+5)*c.coolant_rho_kg_m3*velocity**2/2,
                cell_core_to_coolant_K_W=resistance, UA_W_K=count/resistance,
                plates_kg=branches*length*(2*width*wall+2*gap*wall)*c.aluminum_rho_kg_m3+c.battery_manifold_each_kg,
                TIM_kg=count*contact*c.tim_thickness_m*c.tim_rho_kg_m3,
                coolant_m3=branches*length*width*gap, bare_cell_m3=bare_volume)


def effectiveness(UA: float, cc: float, ca: float) -> float:
    cmin, cmax = min(cc,ca), max(cc,ca)
    ratio, ntu = cmin/cmax, UA/cmin
    if abs(ratio-1) < 1e-8:
        return ntu/(1+ntu)
    e = math.exp(-ntu*(1-ratio))
    return (1-e)/(1-ratio*e)


def make_loop(x: Inputs, pod: int, is_battery: bool, hover_heat: float,
              cell_count: int) -> Loop:
    c = x.cooling
    rho_air, ambient, _ = atmosphere(x.mission.field_elevation_m,c.sea_level_ambient_C)
    liquid_delta = c.battery_flow_delta_K if is_battery else c.prop_flow_delta_K
    target = c.battery_hot_coolant_design_C if is_battery else c.prop_hot_coolant_design_C
    line = c.battery_line_length_m if is_battery else c.prop_line_length_m
    # Flow is based on FULL hover loss. Reducing radiator duty is not permission
    # to reduce heat acquisition/pump flow by the same factor.
    mdot = max(hover_heat,1.0)/(c.coolant_cp_J_kgK*liquid_delta)
    flow = mdot/c.coolant_rho_kg_m3
    geometry = battery_plate(x,cell_count,flow) if is_battery else {}
    diameter = max(c.hose_min_ID_m,math.sqrt(4*flow/(math.pi*c.hose_speed_m_s)))
    dp, re = hose_pressure(flow,diameter,line,c)
    dp += c.radiator_liquid_dp_Pa+(geometry["channel_dp_Pa"] if is_battery else c.motor_jacket_dp_Pa)
    head = dp*c.pump_head_margin
    pump_W = head*flow/c.pump_eff
    # Pump electrical power is conservatively all dumped into coolant. Size the
    # radiator for 70% of component hover heat PLUS pump heat.
    reject = max(hover_heat,1.0)*c.hover_rejection_fraction+pump_W
    air_mdot = reject/(c.air_cp_J_kgK*c.air_design_rise_K)
    cc, ca = mdot*c.coolant_cp_J_kgK, air_mdot*c.air_cp_J_kgK
    eps = reject/(min(cc,ca)*(target-ambient))
    if not 0 < eps < 1:
        raise ValueError("Radiator approach impossible: change design coolant temperature/flow/ambient")
    cr = min(cc,ca)/max(cc,ca)
    ntu = eps/(1-eps) if abs(cr-1) < 1e-8 else math.log((1-eps*cr)/(1-eps))/(1-cr)
    needed_UA = ntu*min(cc,ca)
    face_flow = air_mdot/rho_air/c.radiator_face_speed_m_s
    # Both airflow and heat-transfer capacity constrain radiator geometry.
    core = max(face_flow*c.radiator_depth_m, needed_UA/c.radiator_UA_per_m3_W_K)
    face = core/c.radiator_depth_m
    UA = core*c.radiator_UA_per_m3_W_K
    air_flow = air_mdot/rho_air
    full_fan = c.radiator_air_dp_Pa*air_flow/c.fan_eff
    hose_fluid = line*math.pi*diameter**2/4
    acquired_fluid = geometry["coolant_m3"] if is_battery else c.jacket_and_plate_fluid_each_L/1000
    fluid = (hose_fluid+acquired_fluid+core*c.radiator_coolant_volume_fraction+
             c.coolant_reserve_each_loop_L/1000)*c.coolant_rho_kg_m3
    masses = dict(radiator=core*c.radiator_envelope_density_kg_m3+c.radiator_header_kg,
                  pump=c.pump_min_mass_kg+c.pump_mass_kg_per_kW*pump_W/1000,
                  fan=0.2+c.fan_mass_kg_per_kW*full_fan*c.fan_rating_margin/1000,
                  hoses=line*math.pi*((diameter+2*c.hose_wall_m)**2-diameter**2)/4*c.hose_rho_kg_m3,
                  coolant=fluid, reservoir=c.reservoirs_each_kg, fittings=c.fittings_each_loop_kg,
                  plate=geometry["plates_kg"] if is_battery else c.inverter_plate_each_kg,
                  TIM=geometry.get("TIM_kg",0.0))
    return Loop(("battery_" if is_battery else "propulsion_")+NAMES[pod],pod,is_battery,
                reject,mdot,flow*60000,head,pump_W,diameter,re,air_mdot,face,core,UA,
                air_flow/(c.inlet_velocity_capture*x.aircraft.cruise_kmh/3.6),full_fan,full_fan*c.fan_rating_margin,fluid,
                geometry.get("UA_W_K",0.0),masses,geometry)


def design_cooling(x: Inputs, ns: int, np: int, ratings: list[float]) -> list[Loop]:
    """Fixed installed hardware; hover design point is at the end-SOC reserve."""
    s = Segment("design_hover",1,x.mission.transition_height_m)
    rotor = propulsion(x,s,0,ratings)
    state = initial_state(x)
    state.soc_mean = x.battery.minimum_soc+x.battery.residual_soc_spread/2
    state.soc_min = x.battery.minimum_soc
    extra = auxiliary_power(x,False,ns)
    previous = 0.0
    for _ in range(50):  # fixed-point loop for pump/fan power -> battery heat -> TMS size
        point = electrical(x,rotor,extra,state,ns,np)
        loops = [make_loop(x,i,False,d.motor_heat_W+d.inverter_heat_W,0)
                 for i,d in enumerate(point.drives)]
        loops += [make_loop(x,i,True,point.heat_W*n/ns,n*np)
                  for i,n in enumerate(section_counts(ns))]
        extra = auxiliary_power(x,False,ns)+sum(l.pump_W+l.full_fan_W for l in loops)
        if abs(extra-previous) < 0.01:
            return loops
        previous = extra
    raise ValueError("Cooling sizing/load iteration did not converge")


def air_operation(x: Inputs, loops: list[Loop], altitude: float,
                  speed: float) -> tuple[float,float,list[float],float]:
    """Fan + ram pressure determine achievable flow through the nacelle cores.

    Aim for design air mass flow with a controllable inlet/fan. At unchanged
    mass flow, pressure drop increases as air density falls. If fan rating is
    insufficient, solve the pressure/power balance for a reduced flow; thermal
    rejection then uses that reduced flow. No unmeasured propwash credit.
    Ram pressure*volume flow is counted as aerodynamic power, not free cooling.
    """
    c = x.cooling
    rho, ambient, _ = atmosphere(x.mission.field_elevation_m+altitude,c.sea_level_ambient_C)
    rho_ref, _, _ = atmosphere(x.mission.field_elevation_m,c.sea_level_ambient_C)
    fan, drag = 0.0,0.0
    air_fractions: list[float] = []
    for l in loops:
        dp_full = c.radiator_air_dp_Pa*rho_ref/rho
        ram = 0.5*rho*speed**2*c.ram_pressure_recovery
        vf_full = l.air_kg_s/rho
        def fan_needed(fraction: float) -> float:
            return max(0.0,dp_full*fraction**2-ram)*vf_full*fraction/c.fan_eff
        fraction = 1.0
        if fan_needed(1.0) > l.fan_rating_W:
            low,high = 0.0,1.0
            for _ in range(35):
                mid = (low+high)/2
                if fan_needed(mid) > l.fan_rating_W:
                    high = mid
                else:
                    low = mid
            fraction = low
        air_fractions.append(fraction)
        fan += fan_needed(fraction)
        drag += min(dp_full*fraction**2,ram)*vf_full*fraction
    return fan,drag,air_fractions,ambient


def initial_state(x: Inputs) -> State:
    spread = x.battery.residual_soc_spread if x.balancing.enabled else x.balancing.initial_soc_spread
    return State(0.0,x.battery.initial_soc-spread/2,x.battery.initial_soc-spread,
                 [x.cooling.initial_C]*4,[x.cooling.initial_C]*4,
                 [x.cooling.initial_C]*4,[x.cooling.initial_C]*8)


def thermal_step(x: Inputs, state: State, point: ElectricalPoint, loops: list[Loop],
                 ns: int, np: int, ambient: float, dt: float,
                 air_fractions: list[float] | None = None) -> tuple[float,float]:
    """Energy-conserving finite-capacity thermal network.

    Coolant state is radiator HOT inlet/return temperature. Radiator outlet is
    Tc-Qrad/(mdot*cp). In propulsion loops, cold coolant visits inverter FIRST,
    then motor. For each solid q=Cflow*(1-exp(-UA/Cflow))*(Tsolid-Tin).
    This limits transfer by coolant heat capacity without an arbitrary UA cap.
    Battery loops use the same relationship. Pump heat joins the return node.
    Heat rejected by the radiator is not clipped to its design duty: a hotter
    coolant can reject more, at the expense of higher component temperatures.
    """
    c = x.cooling
    left, rejected_J, reversible_J = dt,0.0,0.0
    counts = section_counts(ns)
    while left > 1e-10:
        # Explicit integration uses a conservative time-constant bound for each
        # coolant/solid node. Thermal substeps do not change electrical SOC step.
        h = min(left,c.thermal_step_max_s)
        for l in loops:
            cc = l.liquid_kg_s*c.coolant_cp_J_kgK
            h = min(h,0.15*l.coolant_kg*c.coolant_cp_J_kgK/(3*cc+1))
        for i in ALL:
            h = min(h,0.15*x.aircraft.motor_mass_each_kg*x.aircraft.motor_cp_J_kgK/x.aircraft.motor_to_coolant_W_K,
                    0.15*x.inverter.mass_each_kg*x.inverter.cp_J_kgK/x.inverter.to_coolant_W_K)
        for j,l in enumerate(loops):
            i, hot = l.pod,state.coolant_C[j]
            fraction = air_fractions[j] if air_fractions else 1.0
            cc, ca = l.liquid_kg_s*c.coolant_cp_J_kgK,l.air_kg_s*c.air_cp_J_kgK*fraction
            # Assumed air-side UA scaling when a fan cannot sustain design flow.
            actual_UA = l.UA_W_K*fraction**0.7
            qrad = effectiveness(actual_UA,cc,ca)*min(cc,ca)*(hot-ambient)
            cold = hot-qrad/cc
            if l.is_battery:
                transfer = cc*(-math.expm1(-l.acquisition_UA_W_K/cc))*(state.battery_C[i]-cold)
                qrev = -point.current_A*counts[i]*(state.battery_C[i]+273.15)*x.cell.entropy_dU_dT_V_K
                heat = point.heat_W*counts[i]/ns+qrev
                capacity = counts[i]*np*x.cell.mass_kg*x.cell.cp_J_kgK
                state.battery_C[i] += (heat-transfer)*h/capacity
                reversible_J += qrev*h
            else:
                qi = cc*(-math.expm1(-x.inverter.to_coolant_W_K/cc))*(state.inverter_C[i]-cold)
                motor_inlet = cold+qi/cc
                qm = cc*(-math.expm1(-x.aircraft.motor_to_coolant_W_K/cc))*(state.motor_C[i]-motor_inlet)
                state.inverter_C[i] += (point.drives[i].inverter_heat_W-qi)*h/(x.inverter.mass_each_kg*x.inverter.cp_J_kgK)
                state.motor_C[i] += (point.drives[i].motor_heat_W-qm)*h/(x.aircraft.motor_mass_each_kg*x.aircraft.motor_cp_J_kgK)
                transfer = qi+qm
            state.coolant_C[j] += (transfer+l.pump_W-qrad)*h/(l.coolant_kg*c.coolant_cp_J_kgK)
            rejected_J += qrad*h
        left -= h
    return rejected_J/dt,reversible_J/dt


def simulate(x: Inputs, ns: int, np: int, loops: list[Loop], ratings: list[float],
             segments: list[Segment], start: State | None = None,
             thermal: bool = True, stop_on_electrical: bool = False) -> Simulation:
    state = deepcopy(start) if start else initial_state(x)
    rows: list[dict[str, Any]] = []
    issues: set[str] = set()
    checkpoints = [("departure",segments[0].h0_m,deepcopy(state))]
    for s in segments:
        elapsed = 0.0
        while elapsed < s.duration_s-1e-9:
            dt = min(x.mission.dt_s,s.duration_s-elapsed)
            t = elapsed+dt/2  # midpoint kinematics for force/power integration
            alt = s.h0_m+s.vz0_m_s*t+0.5*s.az_m_s2*t*t
            speed = max(0.0,s.v0_m_s+s.ax_m_s2*t)
            rho,ambient,_ = atmosphere(x.mission.field_elevation_m+alt,x.cooling.sea_level_ambient_C)
            fan,drag,air_fractions,_ = air_operation(x,loops,alt,speed)
            pump = sum(l.pump_W for l in loops)
            aux = auxiliary_power(x,s.mode == "wing",ns)
            rotors = propulsion(x,s,t,ratings,drag)
            point = electrical(x,rotors,aux+pump+fan,state,ns,np)
            removed = point.current_A*dt/(np*x.cell.capacity_Ah*x.battery.soh*3600)
            state.soc_mean -= removed
            state.soc_min -= removed
            electrical_issues: set[str] = set()
            if state.soc_min < x.battery.minimum_soc-1e-9:
                electrical_issues.add("SOC reserve")
            if point.current_A/np > x.cell.max_current_A:
                electrical_issues.add("cell current")
            if point.min_cell_V < x.cell.min_V:
                electrical_issues.add("cell voltage")
            if not x.battery.bus_min_V <= point.voltage_V <= x.battery.bus_max_V:
                electrical_issues.add("bus voltage")
            issues.update(electrical_issues)
            if electrical_issues and stop_on_electrical:
                return Simulation(rows,state,sorted(issues),checkpoints)
            qrad,qrev = thermal_step(x,state,point,loops,ns,np,ambient,dt,air_fractions) if thermal else (0.0,0.0)
            state.time_s += dt
            elapsed += dt
            if max(state.battery_C) > x.cell.temp_limit_C:
                issues.add("battery temperature")
            if max(state.motor_C) > x.aircraft.motor_limit_C:
                issues.add("motor temperature")
            if max(state.inverter_C) > x.inverter.temp_limit_C:
                issues.add("inverter temperature")
            if min(air_fractions) < 0.99:
                issues.add("fan rating insufficient at altitude")
            row: dict[str,Any] = dict(time_s=state.time_s,dt_s=dt,phase=s.name,
                altitude_AGL_m=s.h0_m+s.vz0_m_s*elapsed+0.5*s.az_m_s2*elapsed**2,
                speed_m_s=max(0.0,s.v0_m_s+s.ax_m_s2*elapsed),rho_kg_m3=rho,ambient_C=ambient,
                soc=state.soc_mean,min_group_soc=state.soc_min,DoD=1-state.soc_mean,
                bus_V=point.voltage_V,pack_A=point.current_A,cell_A=point.current_A/np,
                C_rate=point.current_A/(np*x.cell.capacity_Ah*x.battery.soh),
                battery_terminal_W=point.terminal_W,battery_heat_W=point.heat_W+qrev,
                battery_irreversible_W=point.heat_W,battery_reversible_W=qrev,
                shaft_W=sum(r.shaft_W for r in rotors),pump_W=pump,fan_W=fan,
                auxiliary_W=aux,ram_drag_power_W=drag,radiator_W=qrad,
                minimum_radiator_airflow_fraction=min(air_fractions),
                motor_heat_W=sum(d.motor_heat_W for d in point.drives),
                inverter_heat_W=sum(d.inverter_heat_W for d in point.drives),
                battery_C=max(state.battery_C),motor_C=max(state.motor_C),inverter_C=max(state.inverter_C))
            for i,(r,d) in enumerate(zip(rotors,point.drives)):
                if r.shaft_W > ratings[i]*1.00001:
                    issues.add("motor peak power rating")
                if r.electrical_Hz > x.aircraft.electrical_Hz_limit:
                    issues.add("motor electrical frequency limit")
                if r.tip_mach > x.aircraft.tip_mach_limit:
                    issues.add("indicative rotor tip Mach limit")
                if 0 < x.inverter.phase_rms_limit_A < d.phase_rms_A:
                    issues.add("inverter phase current rating")
                for key,value in asdict(r).items():
                    row[NAMES[i]+"_"+key] = value
                row[NAMES[i]+"_phase_rms_A"] = d.phase_rms_A
                row[NAMES[i]+"_motor_C"] = state.motor_C[i]
                row[NAMES[i]+"_inverter_C"] = state.inverter_C[i]
                row[NAMES[i]+"_battery_C"] = state.battery_C[i]
                row[NAMES[i]+"_prop_coolant_C"] = state.coolant_C[i]
                row[NAMES[i]+"_battery_coolant_C"] = state.coolant_C[i+4]
            rows.append(row)
        end_h = s.h0_m+s.vz0_m_s*s.duration_s+0.5*s.az_m_s2*s.duration_s**2
        checkpoints.append(("after_"+s.name,end_h,deepcopy(state)))
    return Simulation(rows,state,sorted(issues),checkpoints)


def metrics(rows: list[dict[str,Any]]) -> dict[str,float]:
    if not rows:
        return {}
    return dict(terminal_energy_kWh=sum(r["battery_terminal_W"]*r["dt_s"] for r in rows)/3.6e6,
                auxiliary_energy_kWh=sum(r["auxiliary_W"]*r["dt_s"] for r in rows)/3.6e6,
                cooling_energy_kWh=sum((r["pump_W"]+r["fan_W"])*r["dt_s"] for r in rows)/3.6e6,
                peak_terminal_kW=max(r["battery_terminal_W"] for r in rows)/1000,
                peak_pack_A=max(r["pack_A"] for r in rows),
                end_soc=rows[-1]["soc"],end_min_group_soc=rows[-1]["min_group_soc"],
                min_bus_V=min(r["bus_V"] for r in rows),peak_cell_A=max(r["cell_A"] for r in rows),
                peak_battery_C=max(r["battery_C"] for r in rows),
                peak_motor_C=max(r["motor_C"] for r in rows),peak_inverter_C=max(r["inverter_C"] for r in rows))


def validate(x: Inputs) -> None:
    a,m,b,c,cell,z = x.aircraft,x.mission,x.battery,x.cooling,x.cell,x.balancing
    if a.mass_kg <= 0 or len(a.diameters_m) != 4 or min(a.diameters_m) <= 0:
        raise ValueError("Positive mass and exactly four positive rotor diameters required")
    if len(a.motor_peak_kW) != 4 or min(a.motor_peak_kW) < 0:
        raise ValueError("Four non-negative motor peak ratings required")
    if not a.emergency_pairs or any(len(p)!=2 or len(set(p))!=2 or any(i not in ALL for i in p) or not any(i<2 for i in p) or not any(i>=2 for i in p) for p in a.emergency_pairs):
        raise ValueError("Emergency pairs must each contain one inner (0/1) and one outer (2/3)")
    if not 0 < a.emergency_inner_thrust_fraction < 1 or not 0 <= a.normal_inner_thrust_fraction < 1:
        raise ValueError("Invalid thrust fractions")
    if not 0 < b.soh <= 1 or not 0 <= b.minimum_soc < b.initial_soc <= 1:
        raise ValueError("Invalid SOC/SOH")
    if not 0 <= b.residual_soc_spread <= z.initial_soc_spread < b.initial_soc-b.minimum_soc:
        raise ValueError("Require 0 <= residual spread <= initial spread < usable SOC")
    if b.bus_min_V <= 0 or b.bus_max_V <= b.bus_min_V or b.max_parallel < 1 or b.parallel_count < 0:
        raise ValueError("Invalid bus window or maximum parallel count")
    if len(cell.ocv_V)<2 or any(v<=0 for v in cell.ocv_V) or any(p>q for p,q in zip(cell.ocv_V,cell.ocv_V[1:])):
        raise ValueError("OCV table must be positive and nondecreasing")
    if max(cell.ocv_V) > cell.max_V or cell.form not in ("cylindrical","pouch","prismatic"):
        raise ValueError("Cell OCV exceeds charge limit or form unsupported")
    if m.cruise_height_m < m.transition_height_m or m.transition_height_m <= 0:
        raise ValueError("Cruise height must be >= positive transition height")
    if not 0 < m.vertical_accel_m_s2 < 9.80665:
        raise ValueError("Vertical acceleration must be between 0 and g")
    if min(m.dt_s,m.transition_s,m.back_transition_s,m.vertical_speed_m_s,m.wing_climb_m_s,m.wing_descent_m_s,m.vertical_descent_m_s) <= 0:
        raise ValueError("Mission rates, transitions and timestep must be positive")
    if min(m.initial_hover_s,m.landing_hover_s,m.cruise_s,a.emergency_s) < 0 or a.emergency_s == 0:
        raise ValueError("Durations must be non-negative, emergency duration positive")
    if c.fan_rating_margin <= 0:
        raise ValueError("Fan rating margin must be positive")
    if not 0 < c.hover_rejection_fraction <= 2:
        raise ValueError("Cooling hover fraction must be in (0,2]")
    if not 0 < z.duty <= 1 or not 1 <= z.simultaneous_per_board <= z.channels_per_board:
        raise ValueError("Invalid balancing duty/channel schedule")
    if x.inverter.mode not in ("efficiency","device"):
        raise ValueError("Inverter mode must be efficiency or device")
    for name,value in [("motor_eff",a.motor_eff),("prop_eff",a.cruise_prop_eff),("FM",a.hover_fm),
                       ("inverter_eff",x.inverter.efficiency),("pump_eff",c.pump_eff),
                       ("fan_eff",c.fan_eff),("DC/DC_eff",x.auxiliaries.dc_dc_eff)]:
        if not 0 < value <= 1:
            raise ValueError(name+" must be in (0,1]")
    # Fail early on nonsensical physical values instead of a later ZeroDivisionError.
    for obj,names in [(cell,("capacity_Ah","mass_kg","resistance_ohm","cp_J_kgK","max_current_A")),
                      (c,("thermal_step_max_s","coolant_cp_J_kgK","coolant_rho_kg_m3","coolant_mu_Pas","coolant_k_W_mK","prop_flow_delta_K","battery_flow_delta_K","radiator_UA_per_m3_W_K","radiator_depth_m","channel_gap_m","hose_min_ID_m")),
                      (z,("resistor_ohm","board_to_ambient_K_W"))]:
        if any(getattr(obj,n)<=0 for n in names):
            raise ValueError("Physical properties must be positive: "+", ".join(names))


def run_model(x: Inputs) -> dict[str,Any]:
    validate(x)
    a,b,cell = x.aircraft,x.battery,x.cell
    ns = b.series_count or math.floor((b.bus_max_V-b.charge_margin_V)/cell.max_V)
    if ns < 4 or ns*cell.max_V > b.bus_max_V-b.charge_margin_V+1e-8:
        raise ValueError("Series count exceeds full-charge bus ceiling or is too small")
    segments = mission_segments(x)
    ratings = motor_ratings(x,segments)
    electrical_flags = {"SOC reserve","cell current","cell voltage","bus voltage"}
    cache: dict[int,tuple[bool,list[str]]] = {}

    def feasible(np: int) -> bool:
        if np in cache:
            return cache[np][0]
        try:
            loops = design_cooling(x,ns,np,ratings)
            normal = simulate(x,ns,np,loops,ratings,segments,thermal=False,stop_on_electrical=True)
            flags = set(normal.issues)&electrical_flags
            if not flags:
                for _,alt,state in normal.checkpoints:
                    for pair in a.emergency_pairs:
                        emergency = simulate(x,ns,np,loops,ratings,
                            [Segment("emergency_hover",a.emergency_s,alt,active=tuple(pair))],
                            state,thermal=False,stop_on_electrical=True)
                        flags.update(set(emergency.issues)&electrical_flags)
                        if flags:
                            break
                    if flags:
                        break
            cache[np] = (not flags,sorted(flags))
        except ValueError as exc:
            # Configuration errors should not masquerade as battery undersizing.
            if "Battery" not in str(exc) and "Cooling sizing/load" not in str(exc):
                raise
            cache[np] = (False,[str(exc)])
        return cache[np][0]

    # Bracket/bisect under constant-R, equal-capacity sizing assumptions. More
    # parallel cells reduce sag/current and increase usable capacity; small
    # discrete TMS mass/auxiliary steps are included. Check the preceding count.
    if b.parallel_count > 0:
        np = b.parallel_count
    else:
        low,high = 0,1
        while high < b.max_parallel and not feasible(high):
            low,high = high,min(b.max_parallel,high*2)
        if not feasible(high):
            raise ValueError(f"No electrical solution through {b.max_parallel}P: {cache[high][1]}")
        while high-low > 1:
            mid = (high+low)//2
            if feasible(mid):
                high = mid
            else:
                low = mid
        np = high
        while np > 1 and feasible(np-1):
            np -= 1
    loops = design_cooling(x,ns,np,ratings)
    normal = simulate(x,ns,np,loops,ratings,segments)
    emergencies: list[dict[str,Any]] = []
    all_rows = list(normal.rows)
    # Independent branches: emergencies are never concatenated or counted as
    # simultaneous mission energy. Each starts from the SAME checkpoint state.
    for label,alt,state in normal.checkpoints:
        for pair in a.emergency_pairs:
            sim = simulate(x,ns,np,loops,ratings,
                [Segment("emergency_hover",a.emergency_s,alt,active=tuple(pair))],state)
            emergencies.append(dict(checkpoint=label,altitude_AGL_m=alt,
                                    survivors=[NAMES[i] for i in pair],metrics=metrics(sim.rows),
                                    issues=sim.issues,rows=sim.rows))
            all_rows.extend(sim.rows)
    balance = balancing_report(x,ns,np)
    mass_components: dict[str,float] = {}
    for l in loops:
        for k,value in l.masses_kg.items():
            mass_components[k] = mass_components.get(k,0.0)+value
    cooling_mass = sum(mass_components.values())
    cells_mass = ns*np*cell.mass_kg
    pack_dry = cells_mass*(1+b.noncooling_packaging_fraction)+balance["hardware_mass_kg"]
    avionics_mass = (x.auxiliaries.other_avionics_actuators_kg+
                     x.auxiliaries.flight_computer_count*x.auxiliaries.flight_computer_each_kg+x.auxiliaries.voter_kg)
    accounted = pack_dry+cooling_mass+4*(a.motor_mass_each_kg+x.inverter.mass_each_kg)+avionics_mass
    warnings = ["Control/CG alignment unverified; mixed-pair selection and thrust split are assumptions.",
                "Transition path imposed; full power does not prove constant-altitude transition.",
                "Cooling and component masses use uncalibrated estimates; compare vendor maps.",
                "Two-motor contingency assumes intact battery/bus/cooling and immediate attained hover; no fault-transition/landing analysis."]
    issues = set(normal.issues)
    issues.update(i for e in emergencies for i in e["issues"])
    issues.update(balance["issues"])
    if ns*cell.max_V > x.inverter.device_rating_V*x.inverter.voltage_usable_fraction:
        issues.add("inverter device voltage margin")
    if accounted > a.mass_kg:
        issues.add("accounted subsystem mass exceeds MTOW")
    packaging: list[dict[str,Any]] = []
    for i in ALL:
        podloops = [l for l in loops if l.pod == i]
        face,volume = sum(l.face_m2 for l in podloops),sum(l.core_m3 for l in podloops)*1000
        fits = face <= x.cooling.pod_core_face_available_m2 and volume <= x.cooling.pod_core_volume_available_L
        if not fits:
            issues.add("radiator core nacelle allowance exceeded")
        packaging.append(dict(pod=NAMES[i],radiator_face_m2=face,radiator_core_L=volume,
                              fits_core_allowance=fits,
                              battery_section_cell_count=section_counts(ns)[i]*np))
    requirements: list[dict[str,Any]] = []
    for name,rating in zip(NAMES,ratings):
        requirements.append(dict(rotor=name,installed_peak_requirement_kW=rating/1000,
            maximum_demand_kW=max(r[name+"_shaft_W"] for r in all_rows)/1000,
            max_torque_Nm=max(r[name+"_torque_Nm"] for r in all_rows),
            max_rpm=max(r[name+"_rpm"] for r in all_rows),
            max_electrical_Hz=max(r[name+"_electrical_Hz"] for r in all_rows),
            max_phase_rms_A=max(r[name+"_phase_rms_A"] for r in all_rows),
            cruise_shaft_kW=max((r[name+"_shaft_W"] for r in normal.rows if r["phase"]=="cruise"),default=0)/1000))
    return dict(model="Albatros III",inputs=asdict(x),series=ns,parallel=np,cell_count=ns*np,
        full_charge_V=ns*cell.max_V,nominal_V=ns*cell.nominal_V,
        nominal_energy_kWh=ns*np*cell.nominal_V*cell.capacity_Ah/1000,
        previous_parallel_failure=cache.get(np-1,(False,["not evaluated (fixed pack)" if b.parallel_count else "minimum count"]))[1],
        nominal_metrics=metrics(normal.rows),
        all_case_metrics={k:v for k,v in metrics(all_rows).items() if k.startswith("peak_") or k=="min_bus_V"},
        worst_contingency_end_soc=min(e["metrics"]["end_min_group_soc"] for e in emergencies),
        peak_current_nominal_phase=max(normal.rows,key=lambda row:row["cell_A"])["phase"],
        peak_current_nominal_A=max(row["cell_A"] for row in normal.rows),
        sizing_mode="fixed parallel count" if b.parallel_count else "automatic electrical sizing",
        nominal_issues=normal.issues,issues=sorted(issues),warnings=warnings,
        balancing=balance,cooling_loops=[asdict(l) for l in loops],
        cooling_masses_kg=mass_components,cooling_total_kg=cooling_mass,
        battery_cells_kg=cells_mass,battery_dry_with_BMS_kg=pack_dry,
        accounted_subsystems_kg=accounted,remaining_MTOW_kg=a.mass_kg-accounted,
        battery_bare_volume_L=sum(l.acquisition.get("bare_cell_m3",0.0) for l in loops)*1000,
        battery_pack_envelope_estimate_L=sum(l.acquisition.get("bare_cell_m3",0.0) for l in loops)*1000/b.volume_fill_fraction,
        radiator_packaging=packaging,drive_requirements=requirements,
        mission_segments=[asdict(s) for s in segments],mission_rows=normal.rows,emergencies=emergencies)


def mass_values(start: float, stop: float, step: float) -> list[float]:
    if step <= 0 or start <= 0 or stop < start:
        raise ValueError("Sweep requires 0 < START <= STOP and STEP > 0")
    count = math.floor((stop-start)/step+1e-9)+1
    if count > 10000:
        raise ValueError("Sweep would exceed 10,000 designs; increase mass step")
    return [start+i*step for i in range(count)]


def load_inputs(path: Path | None) -> Inputs:
    x = Inputs()
    if path is None:
        return x
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("Configuration must be a JSON object")
    for section,overrides in data.items():
        if section not in {f.name for f in fields(x)} or not isinstance(overrides,dict):
            raise ValueError("Unknown config section or non-object: "+section)
        obj = getattr(x,section)
        valid = {f.name for f in fields(obj)}
        for key,value in overrides.items():
            if key not in valid:
                raise ValueError(f"Unknown input {section}.{key}")
            if isinstance(getattr(obj,key),tuple):
                value = tuple(tuple(v) if isinstance(v,list) else v for v in value)
            setattr(obj,key,value)
    return x


def write_csv(path: Path, rows: list[dict[str,Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer = csv.DictWriter(handle,fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def print_design(result: dict[str,Any]) -> None:
    r,m = result,result["nominal_metrics"]
    print(f"\nAlbatros Model III | imposed MTOW {r['inputs']['aircraft']['mass_kg']:.1f} kg")
    print(f"Battery {r['series']}S {r['parallel']}P | {r['cell_count']} cells | charge ceiling {r['full_charge_V']:.1f} V | nominal {r['nominal_V']:.1f} V")
    print(f"Nominal energy {r['nominal_energy_kWh']:.1f} kWh | mission terminal energy {m['terminal_energy_kWh']:.1f} kWh")
    print(f"Cells {r['battery_cells_kg']:.1f} kg | dry battery incl packaging/BMS {r['battery_dry_with_BMS_kg']:.1f} kg | all cooling {r['cooling_total_kg']:.1f} kg")
    print(f"Remaining MTOW for airframe, rotors, payload etc: {r['remaining_MTOW_kg']:.1f} kg")
    print(f"Nominal end weakest SOC {100*m['end_min_group_soc']:.1f}% | minimum bus {m['min_bus_V']:.1f} V | peak cell {m['peak_cell_A']:.1f} A")
    print(f"Nominal peak temperatures: cells {m['peak_battery_C']:.1f}, motor {m['peak_motor_C']:.1f}, inverter {m['peak_inverter_C']:.1f} C")
    print("Sizing mode:",r["sizing_mode"],"| peak nominal current phase:",r["peak_current_nominal_phase"])
    print("Previous parallel-count check:",", ".join(r["previous_parallel_failure"]))
    balance = r["balancing"]
    hours = balance["estimated_ground_hours"]
    print(f"Passive balance: {balance['series_group_channels']} channels, {balance['on_current_A']*1000:.0f} mA ON, estimated ground time {hours if hours is None else round(hours,2)} h")
    print("Rotor             peak kW    torque Nm   phase A    max rpm   electrical Hz")
    for d in r["drive_requirements"]:
        print(f"{d['rotor']:16} {d['installed_peak_requirement_kW']:8.1f} {d['max_torque_Nm']:11.1f} {d['max_phase_rms_A']:9.1f} {d['max_rpm']:10.0f} {d['max_electrical_Hz']:12.0f}")
    print("Loop                    L/min   head kPa   pump W fan rated W  core L   UA W/K")
    for l in r["cooling_loops"]:
        print(f"{l['name']:23} {l['flow_L_min']:6.2f} {l['pump_head_Pa']/1000:10.1f} {l['pump_W']:8.1f} {l['fan_rating_W']:8.1f} {l['core_m3']*1000:9.2f} {l['UA_W_K']:8.1f}")
    print(f"Worst contingency end weakest SOC: {100*r['worst_contingency_end_soc']:.1f}%")
    print(f"Emergency cases checked independently: {len(r['emergencies'])} (duration {r['inputs']['aircraft']['emergency_s']:.0f} s each)")
    print("MODEL LIMIT EXCEEDANCES:","; ".join(r["issues"]) or "none under stated assumptions")
    for note in r["warnings"]:
        print("Assumption:",note)


def plot_results(data: dict[str,Any] | list[dict[str,Any]], save: Path | None, show: bool) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ValueError("Plotting requires matplotlib in THIS interpreter: python -m pip install matplotlib") from exc
    fig,axes = plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    if isinstance(data,list):
        ok = [r for r in data if "parallel" in r]
        if not ok:
            raise ValueError("No successful sweep points to plot")
        mass = [r["mass_kg"] for r in ok]
        for ax,key,label in [(axes[0,0],"battery_dry_kg","Dry battery incl BMS (kg)"),
                             (axes[0,1],"cooling_kg","Cooling mass (kg)"),
                             (axes[1,0],"remaining_kg","Remaining MTOW (kg)"),
                             (axes[1,1],"worst_motor_C","All-case motor temperature (C)")]:
            ax.plot(mass,[r[key] for r in ok],"o-")
            ax.set(xlabel="Imposed MTOW (kg)",ylabel=label)
            ax.grid(alpha=0.3)
    else:
        rows = data["mission_rows"]
        t = [r["time_s"]/60 for r in rows]
        axes[0,0].plot(t,[100*r["min_group_soc"] for r in rows],label="weakest SOC (%)")
        axes[0,0].set(ylabel="SOC (%)")
        right = axes[0,0].twinx()
        right.plot(t,[r["bus_V"] for r in rows],color="tab:orange",label="bus")
        right.set_ylabel("Bus (V)")
        for key,label in [("battery_terminal_W","Battery input"),("shaft_W","Shaft")]:
            axes[0,1].plot(t,[r[key]/1000 for r in rows],label=label)
        axes[0,1].set_ylabel("Power (kW)")
        for key,label in [("battery_C","Cells"),("motor_C","Motor"),("inverter_C","Inverter")]:
            axes[1,0].plot(t,[r[key] for r in rows],label=label)
        axes[1,0].set_ylabel("Lumped temperature (C)")
        axes[1,1].plot(t,[r["altitude_AGL_m"] for r in rows],label="Altitude AGL")
        axes[1,1].set_ylabel("Altitude (m)")
        for ax in axes.flat:
            ax.set_xlabel("Mission time (min)")
            ax.grid(alpha=0.3)
            ax.legend()
    if save:
        save.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(save,dpi=160)
    if show:
        plt.show()
    plt.close(fig)


def self_test() -> None:
    x = Inputs()
    rho,_,_ = atmosphere(0,15)
    assert abs(rho-1.225) < 0.001
    assert atmosphere(2000,15)[0] < rho
    I,V,Q,_ = battery_point(100000,0.8,0.798,190,20,x)
    assert math.isclose(I*V,100000,rel_tol=1e-12)
    assert math.isclose(I*190*ocv(0.8,x.cell),100000+Q,rel_tol=1e-12)
    assert effectiveness(1000,500,1000) < 1
    vertical = [s for s in mission_segments(x) if s.name.startswith("vertical_") and s.name != "vertical_descent"]
    last = vertical[-1]
    assert math.isclose(last.h0_m+last.vz0_m_s*last.duration_s+0.5*last.az_m_s2*last.duration_s**2,60)
    assert math.isclose(last.vz0_m_s+last.az_m_s2*last.duration_s,0)
    p1 = sum(r.shaft_W for r in propulsion(x,Segment("hover",1,0),0,[0.0]*4))
    doubled = replace(x,aircraft=replace(x.aircraft,mass_kg=1500))
    p2 = sum(r.shaft_W for r in propulsion(doubled,Segment("hover",1,0),0,[0.0]*4))
    assert math.isclose(p2/p1,2**1.5,rel_tol=1e-12)
    r = propulsion(x,Segment("emergency",30,60,active=(0,3)),0,[0.0]*4)
    assert r[1].shaft_W == r[2].shaft_W == 0
    assert math.isclose(r[0].thrust_N+r[3].thrust_N,750*9.80665)
    bal1,bal2 = balancing_report(x,190,10),balancing_report(x,190,20)
    assert math.isclose(bal2["estimated_ground_hours"],2*bal1["estimated_ground_hours"])
    assert mass_values(300,300.5,0.25)==[300,300.25,300.5]
    ratings = motor_ratings(x,mission_segments(x))
    loops = design_cooling(x,190,38,ratings)
    state = initial_state(x)
    point = electrical(x,propulsion(x,Segment("hover",1,0),0,ratings),0,state,190,38)
    def stored_J(st: State) -> float:
        return (sum(st.motor_C)*x.aircraft.motor_mass_each_kg*x.aircraft.motor_cp_J_kgK+
                sum(st.inverter_C)*x.inverter.mass_each_kg*x.inverter.cp_J_kgK+
                sum(t*n*38*x.cell.mass_kg*x.cell.cp_J_kgK for t,n in zip(st.battery_C,section_counts(190)))+
                sum(t*l.coolant_kg*x.cooling.coolant_cp_J_kgK for t,l in zip(st.coolant_C,loops)))
    before = stored_J(state)
    qrad,qrev = thermal_step(x,state,point,loops,190,38,25.0,0.1)
    generated = point.heat_W+qrev+sum(d.motor_heat_W+d.inverter_heat_W for d in point.drives)+sum(l.pump_W for l in loops)
    assert math.isclose(stored_J(state)-before,(generated-qrad)*0.1,rel_tol=1e-8)
    _,_,fractions,_ = air_operation(x,loops,6000,0)
    assert min(fractions)<1  # limited fan must reduce airflow, not invent cooling
    print("Self-tests passed: atmosphere, battery energy, vertical kinematics, hover scaling, mixed-pair thrust, balancing, float sweep, thermal energy conservation, fan-limited airflow.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mass",type=float,help="MTOW kg, can be a decimal")
    parser.add_argument("--sweep",nargs=3,type=float,metavar=("START","STOP","STEP"))
    parser.add_argument("--config",type=Path)
    parser.add_argument("--write-config",type=Path,help="Write all editable defaults and exit")
    parser.add_argument("--csv",type=Path,help="Mission rows or sweep summary")
    parser.add_argument("--json",type=Path,help="Detailed design or sweep summaries")
    parser.add_argument("--plot",action="store_true",help="Display interactive plot")
    parser.add_argument("--save-plot",type=Path,help="Save a PNG; works without --plot")
    parser.add_argument("--inverter",choices=("efficiency","device"))
    parser.add_argument("--parallel",type=int,help="Evaluate fixed Np instead of automatically sizing the pack")
    parser.add_argument("--self-test",action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            return
        x = load_inputs(args.config)
        if args.mass is not None:
            x.aircraft.mass_kg = args.mass
        if args.inverter:
            x.inverter.mode = args.inverter
        if args.parallel is not None:
            x.battery.parallel_count = args.parallel
        if args.write_config:
            args.write_config.parent.mkdir(parents=True,exist_ok=True)
            args.write_config.write_text(json.dumps(asdict(x),indent=2)+"\n",encoding="utf-8")
            print("Wrote",args.write_config)
            return
        data: dict[str,Any] | list[dict[str,Any]]
        if args.sweep:
            summary: list[dict[str,Any]] = []
            for mass in mass_values(*args.sweep):
                trial = replace(x,aircraft=replace(x.aircraft,mass_kg=mass))
                print(f"Calculating {mass:g} kg ...",flush=True)
                try:
                    r = run_model(trial)
                    row = dict(mass_kg=mass,series=r["series"],parallel=r["parallel"],
                        battery_dry_kg=r["battery_dry_with_BMS_kg"],cooling_kg=r["cooling_total_kg"],
                        remaining_kg=r["remaining_MTOW_kg"],mission_kWh=r["nominal_metrics"]["terminal_energy_kWh"],
                        end_soc=r["nominal_metrics"]["end_min_group_soc"],
                        worst_motor_C=r["all_case_metrics"]["peak_motor_C"],
                        worst_inverter_C=r["all_case_metrics"]["peak_inverter_C"],
                        worst_battery_C=r["all_case_metrics"]["peak_battery_C"],issues="; ".join(r["issues"]))
                except ValueError as exc:
                    row = dict(mass_kg=mass,error=str(exc))
                summary.append(row)
                print(json.dumps(row),flush=True)
            data = summary
            if args.csv:
                write_csv(args.csv,summary)
        else:
            data = run_model(x)
            print_design(data)
            if args.csv:
                write_csv(args.csv,data["mission_rows"])
        if args.json:
            args.json.parent.mkdir(parents=True,exist_ok=True)
            args.json.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        if args.plot or args.save_plot:
            plot_results(data,args.save_plot,args.plot)
    except (ValueError,OSError,TypeError) as exc:
        parser.exit(2,f"Model input/output error: {exc}\n")


if __name__ == "__main__":
    main()
