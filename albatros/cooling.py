"""Liquid cooling: loop sizing (pumps, hoses, radiators, fans) and the
transient thermal network.

Architecture: 8 independent loops, two per wing pod.
  * propulsion loop: coolant -> inverter -> motor jacket -> radiator
    (inverter integrated in the motor by default: no separate cold plate)
  * battery loop:    coolant -> battery cold plates -> radiator
Radiator sizing uses the effectiveness-NTU method (counterflow surrogate):
  https://www.mathworks.com/help/hydro/ref/entuheattransfer.html
Pipe friction: Darcy-Weisbach with laminar 64/Re or Blasius 0.3164/Re^0.25.
All radiator numbers are ESTIMATES; replace with vendor maps when available.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .atmosphere import atmosphere
from .electrical import ElectricalPoint, auxiliary_power, electrical, section_counts
from .inputs import ALL, NAMES, Cooling, Inputs
from .mission import Segment
from .propulsion import MotorSizing, propulsion
from .state import State


@dataclass
class Loop:
    """One sized cooling loop."""
    name: str
    pod: int  # which rotor pod (0..3) it sits in
    is_battery: bool
    heat_design_W: float  # heat the radiator is sized to reject
    liquid_kg_s: float
    flow_L_min: float
    pump_head_Pa: float
    pump_W: float
    hose_ID_m: float
    hose_Re: float
    air_kg_s: float
    face_m2: float  # radiator face area
    core_m3: float  # radiator core volume
    UA_W_K: float  # radiator conductance
    inlet_m2: float
    full_fan_W: float  # fan power at ground design flow
    fan_rating_W: float
    fan_design_dp_Pa: float  # pressure the fan must make (after downwash credit)
    coolant_kg: float
    acquisition_UA_W_K: float  # battery cells -> coolant conductance (battery loops)
    masses_kg: dict[str, float]
    volumes_L: dict[str, float]  # outer volume of each component of the loop
    acquisition: dict[str, float]  # battery cold-plate details


def hose_pressure(flow: float, diameter: float, length: float, c: Cooling) -> tuple[float, float]:
    """Pressure drop [Pa] and Reynolds number of a hose (friction + minor losses)."""
    velocity = flow / (math.pi * diameter ** 2 / 4)
    re = c.coolant_rho_kg_m3 * velocity * diameter / c.coolant_mu_Pas
    f = 64 / max(re, 1e-12) if re < 2300 else 0.3164 / re ** 0.25
    return (f * length / diameter + c.minor_loss_K) * c.coolant_rho_kg_m3 * velocity ** 2 / 2, re


def battery_plate(x: Inputs, count: int, flow: float) -> dict[str, float]:
    """Cold plates for ``count`` cells: side-contact ribbons for round cells,
    one flat face per cell for pouch/prismatic cells.

    Thermal resistance per cell, core to coolant [K/W]:
        R = R_core + R_TIM + R_wall + 1/(h*A_contact)
    All cells in parallel -> UA = count / R.
    """
    c, cell = x.cooling, x.cell
    if cell.form == "cylindrical":
        contact = cell.contact_fraction * math.pi * cell.diameter_m * cell.height_m
        branches = math.ceil(count / c.cells_per_ribbon)
        length, width = c.cells_per_ribbon * c.ribbon_pitch_m, cell.height_m
        bare_volume = count * math.pi * cell.diameter_m ** 2 * cell.height_m / 4
    else:
        contact = cell.width_m * cell.height_m
        branches, length, width = count, cell.height_m, cell.width_m
        bare_volume = count * cell.width_m * cell.height_m * cell.thickness_m
    gap, wall = c.channel_gap_m, c.channel_wall_m
    dh = 2 * width * gap / (width + gap)  # hydraulic diameter of a flat channel
    velocity = flow / (branches * width * gap)
    re = c.coolant_rho_kg_m3 * velocity * dh / c.coolant_mu_Pas
    f = 96 / max(re, 1e-12) if re < 2300 else 0.3164 / re ** 0.25
    pr = c.coolant_cp_J_kgK * c.coolant_mu_Pas / c.coolant_k_W_mK
    nu = 7.54 if re < 2300 else 0.023 * re ** 0.8 * pr ** 0.4  # laminar slot / Dittus-Boelter
    h = nu * c.coolant_k_W_mK / dh
    resistance = (cell.core_to_surface_K_W + c.tim_thickness_m / (c.tim_k_W_mK * contact)
                  + wall / (c.aluminum_k_W_mK * contact) + 1 / (h * contact))
    return dict(
        branches=float(branches), hydraulic_diameter_m=dh, Reynolds=re,
        channel_velocity_m_s=velocity, channel_length_m=length,
        channel_dp_Pa=(f * length / dh + 5) * c.coolant_rho_kg_m3 * velocity ** 2 / 2,
        cell_core_to_coolant_K_W=resistance, UA_W_K=count / resistance,
        plates_kg=(branches * length * (2 * width * wall + 2 * gap * wall) * c.aluminum_rho_kg_m3
                   + c.battery_manifold_each_kg),
        TIM_kg=count * contact * c.tim_thickness_m * c.tim_rho_kg_m3,
        coolant_m3=branches * length * width * gap, bare_cell_m3=bare_volume)


def effectiveness(UA: float, cc: float, ca: float) -> float:
    """Counterflow heat-exchanger effectiveness from UA and the two capacity rates."""
    cmin, cmax = min(cc, ca), max(cc, ca)
    ratio, ntu = cmin / cmax, UA / cmin
    if abs(ratio - 1) < 1e-8:
        return ntu / (1 + ntu)
    e = math.exp(-ntu * (1 - ratio))
    return (1 - e) / (1 - ratio * e)


def make_loop(x: Inputs, pod: int, is_battery: bool, hover_heat: float, cell_count: int) -> Loop:
    """Size one loop for its hover heat load.

    Steps: coolant flow (from heat and allowed temperature rise) -> hose size
    and pressure drop -> pump power -> radiator duty -> required UA (NTU method)
    -> core volume (limited by airflow area AND by UA) -> fan power -> masses.
    """
    c = x.cooling
    rho_air, ambient, _ = atmosphere(x.mission.field_elevation_m, c.sea_level_ambient_C)
    liquid_delta = c.battery_flow_delta_K if is_battery else c.prop_flow_delta_K
    target = c.battery_hot_coolant_design_C if is_battery else c.prop_hot_coolant_design_C
    line = c.battery_line_length_m if is_battery else c.prop_line_length_m
    # Pump flow carries FULL hover heat (reducing the radiator duty below does
    # not mean we may also reduce the flow that picks the heat up).
    mdot = max(hover_heat, 1.0) / (c.coolant_cp_J_kgK * liquid_delta)
    flow = mdot / c.coolant_rho_kg_m3
    geometry = battery_plate(x, cell_count, flow) if is_battery else {}
    diameter = max(c.hose_min_ID_m, math.sqrt(4 * flow / (math.pi * c.hose_speed_m_s)))
    dp, re = hose_pressure(flow, diameter, line, c)
    dp += c.radiator_liquid_dp_Pa + (geometry["channel_dp_Pa"] if is_battery else c.motor_jacket_dp_Pa)
    head = dp * c.pump_head_margin
    pump_W = head * flow / c.pump_eff
    # Radiator duty: 70 % (default) of hover heat plus all pump power (ends as heat).
    reject = max(hover_heat, 1.0) * c.hover_rejection_fraction + pump_W
    air_mdot = reject / (c.air_cp_J_kgK * c.air_design_rise_K)
    cc, ca = mdot * c.coolant_cp_J_kgK, air_mdot * c.air_cp_J_kgK
    eps = reject / (min(cc, ca) * (target - ambient))  # required effectiveness
    if not 0 < eps < 1:
        raise ValueError("Radiator approach impossible: change design coolant temperature/flow/ambient")
    cr = min(cc, ca) / max(cc, ca)
    ntu = eps / (1 - eps) if abs(cr - 1) < 1e-8 else math.log((1 - eps * cr) / (1 - eps)) / (1 - cr)
    needed_UA = ntu * min(cc, ca)
    face_flow = air_mdot / rho_air / c.radiator_face_speed_m_s
    core = max(face_flow * c.radiator_depth_m, needed_UA / c.radiator_UA_per_m3_W_K)
    face = core / c.radiator_depth_m
    UA = core * c.radiator_UA_per_m3_W_K
    air_flow = air_mdot / rho_air
    # The fans only have to make the pressure the downwash does not deliver
    # at the hover design point (never less than zero).
    fan_dp = max(0.0, c.radiator_air_dp_Pa - c.hover_propwash_pressure_Pa)
    full_fan = fan_dp * air_flow / c.fan_eff
    fan_rating = full_fan * c.fan_rating_margin
    hose_fluid = line * math.pi * diameter ** 2 / 4
    acquired_fluid = geometry["coolant_m3"] if is_battery else c.jacket_and_plate_fluid_each_L / 1000
    fluid = (hose_fluid + acquired_fluid + core * c.radiator_coolant_volume_fraction
             + c.coolant_reserve_each_loop_L / 1000) * c.coolant_rho_kg_m3
    masses = dict(
        radiator=core * c.radiator_envelope_density_kg_m3 + c.radiator_header_kg,
        pump=c.pump_min_mass_kg + c.pump_mass_kg_per_kW * pump_W / 1000,
        fan=0.2 + c.fan_mass_kg_per_kW * fan_rating / 1000,
        hoses=line * math.pi * ((diameter + 2 * c.hose_wall_m) ** 2 - diameter ** 2) / 4 * c.hose_rho_kg_m3,
        coolant=fluid, reservoir=c.reservoirs_each_kg, fittings=c.fittings_each_loop_kg,
        plate=(geometry["plates_kg"] if is_battery
               else 0.0 if x.inverter.integrated_in_motor else c.inverter_plate_each_kg),
        TIM=geometry.get("TIM_kg", 0.0))
    # Outer volumes [L]. Coolant inside the radiator, hoses and plates sits in
    # those parts, so only the reserve (reservoir) is counted on its own. The
    # battery cold plates are inside the battery pack envelope.
    if c.fan_volume_L_per_kW > 0:  # fan volume follows the fan's job (power)
        fan_volume = c.fan_volume_L_per_kW * fan_rating / 1000
    else:  # a layer of fans over (part of) the radiator face
        fan_volume = face * c.fan_face_coverage * c.fan_depth_m * 1000
    volumes = dict(
        radiator=core * 1000,
        fan=fan_volume,
        pump=masses["pump"] / c.pump_density_kg_m3 * 1000,
        hoses=line * math.pi * (diameter + 2 * c.hose_wall_m) ** 2 / 4 * 1000,
        reservoir=c.coolant_reserve_each_loop_L)
    return Loop(
        name=("battery_" if is_battery else "propulsion_") + NAMES[pod], pod=pod,
        is_battery=is_battery, heat_design_W=reject, liquid_kg_s=mdot, flow_L_min=flow * 60000,
        pump_head_Pa=head, pump_W=pump_W, hose_ID_m=diameter, hose_Re=re, air_kg_s=air_mdot,
        face_m2=face, core_m3=core, UA_W_K=UA,
        inlet_m2=air_flow / (c.inlet_velocity_capture * x.aircraft.cruise_kmh / 3.6),
        full_fan_W=full_fan, fan_rating_W=fan_rating, fan_design_dp_Pa=fan_dp, coolant_kg=fluid,
        acquisition_UA_W_K=geometry.get("UA_W_K", 0.0), masses_kg=masses, volumes_L=volumes,
        acquisition=geometry)


def design_cooling(x: Inputs, ns: int, np: int, motors: MotorSizing) -> list[Loop]:
    """Size all 8 loops at the design point: hover at transition height with the
    battery at its end-of-mission reserve (lowest voltage -> most battery heat).

    Pump and fan power add battery load, which adds battery heat, which changes
    the loops, so this is iterated until the auxiliary power stops changing.
    """
    s = Segment("design_hover", 1, x.mission.transition_height_m)
    rotor = propulsion(x, s, 0, motors.power_W)
    soc_min = x.battery.minimum_soc
    soc_mean = soc_min + x.battery.residual_soc_spread / 2
    extra = auxiliary_power(x, False, ns)
    previous = 0.0
    for _ in range(50):
        point = electrical(x, rotor, extra, soc_mean, soc_min, ns, np)
        loops = [make_loop(x, i, False, d.motor_heat_W + d.inverter_heat_W, 0)
                 for i, d in enumerate(point.drives)]
        loops += [make_loop(x, i, True, point.heat_W * n / ns, n * np)
                  for i, n in enumerate(section_counts(ns))]
        extra = auxiliary_power(x, False, ns) + sum(l.pump_W + l.full_fan_W for l in loops)
        if abs(extra - previous) < 0.01:
            return loops
        previous = extra
    raise ValueError("Cooling sizing/load iteration did not converge")


def air_operation(x: Inputs, loops: list[Loop], altitude: float, speed: float,
                  rotor_borne: bool = False) -> tuple[float, float, list[float], float]:
    """Radiator airflow at a flight condition.

    Returns (total fan power W, ram-drag power W, airflow fraction per loop,
    ambient degC). Two things help the fan push air through the radiator:
      * ram pressure from forward speed (counted as drag power, not free)
      * downwash pressure when the rotors carry the aircraft (rotor_borne),
        Cooling.hover_propwash_pressure_Pa; its energy is already part of
        the rotor power, so it is not charged again.
    If the fan rating is too small (thin air at altitude) the achievable
    airflow fraction is found by bisection and the radiators reject less heat.
    """
    c = x.cooling
    rho, ambient, _ = atmosphere(x.mission.field_elevation_m + altitude, c.sea_level_ambient_C)
    rho_ref, _, _ = atmosphere(x.mission.field_elevation_m, c.sea_level_ambient_C)
    propwash = c.hover_propwash_pressure_Pa if rotor_borne else 0.0
    fan, drag = 0.0, 0.0
    air_fractions: list[float] = []
    for l in loops:
        dp_full = c.radiator_air_dp_Pa * rho_ref / rho  # same mass flow -> higher dp in thin air
        ram = 0.5 * rho * speed ** 2 * c.ram_pressure_recovery
        vf_full = l.air_kg_s / rho

        def fan_needed(fraction: float) -> float:
            # Pressure still missing after ram air and downwash, times volume flow.
            missing = max(0.0, dp_full * fraction ** 2 - ram - propwash)
            return missing * vf_full * fraction / c.fan_eff

        fraction = 1.0
        if fan_needed(1.0) > l.fan_rating_W:
            low, high = 0.0, 1.0
            for _ in range(35):
                mid = (low + high) / 2
                if fan_needed(mid) > l.fan_rating_W:
                    high = mid
                else:
                    low = mid
            fraction = low
        air_fractions.append(fraction)
        fan += fan_needed(fraction)
        drag += min(dp_full * fraction ** 2, ram) * vf_full * fraction
    return fan, drag, air_fractions, ambient


def thermal_step(x: Inputs, state: State, point: ElectricalPoint, loops: list[Loop],
                 motors: MotorSizing, ns: int, np: int, ambient: float, dt: float,
                 air_fractions: list[float] | None = None) -> tuple[float, float]:
    """Advance all temperatures by dt (explicit Euler with safe sub-steps).

    Every solid (cells, motor, inverter) is a single lumped node:
        m*cp*dT/dt = heat generated - heat to coolant
    Heat to coolant is limited by the coolant's capacity rate Cflow:
        q = Cflow * (1 - exp(-UA/Cflow)) * (T_solid - T_coolant_in)
    Coolant state = radiator inlet ("hot") temperature. Radiator outlet is
    T_hot - q_rad/Cflow. Propulsion loops: cold coolant visits the inverter
    first, then the motor. Pump power is added to the coolant.

    Returns (average radiator heat W, average reversible battery heat W).
    """
    c = x.cooling
    left, rejected_J, reversible_J = dt, 0.0, 0.0
    counts = section_counts(ns)
    while left > 1e-10:
        # Sub-step small enough for stability of the fastest node.
        h = min(left, c.thermal_step_max_s)
        for l in loops:
            cc = l.liquid_kg_s * c.coolant_cp_J_kgK
            h = min(h, 0.15 * l.coolant_kg * c.coolant_cp_J_kgK / (3 * cc + 1))
        for i in ALL:
            h = min(h, 0.15 * motors.mass_kg[i] * x.motor.cp_J_kgK / x.motor.to_coolant_W_K,
                    0.15 * x.inverter.mass_each_kg * x.inverter.cp_J_kgK / x.inverter.to_coolant_W_K)
        for j, l in enumerate(loops):
            i, hot = l.pod, state.coolant_C[j]
            fraction = air_fractions[j] if air_fractions else 1.0
            cc, ca = l.liquid_kg_s * c.coolant_cp_J_kgK, l.air_kg_s * c.air_cp_J_kgK * fraction
            # Assumed air-side UA scaling when the fan cannot reach design flow.
            actual_UA = l.UA_W_K * fraction ** 0.7
            qrad = effectiveness(actual_UA, cc, ca) * min(cc, ca) * (hot - ambient)
            cold = hot - qrad / cc  # radiator outlet temperature
            if l.is_battery:
                transfer = cc * (-math.expm1(-l.acquisition_UA_W_K / cc)) * (state.battery_C[i] - cold)
                qrev = -point.current_A * counts[i] * (state.battery_C[i] + 273.15) * x.cell.entropy_dU_dT_V_K
                heat = point.heat_W * counts[i] / ns + qrev
                capacity = counts[i] * np * x.cell.mass_kg * x.cell.cp_J_kgK
                state.battery_C[i] += (heat - transfer) * h / capacity
                reversible_J += qrev * h
            else:
                qi = cc * (-math.expm1(-x.inverter.to_coolant_W_K / cc)) * (state.inverter_C[i] - cold)
                motor_inlet = cold + qi / cc
                qm = cc * (-math.expm1(-x.motor.to_coolant_W_K / cc)) * (state.motor_C[i] - motor_inlet)
                state.inverter_C[i] += ((point.drives[i].inverter_heat_W - qi) * h
                                        / (x.inverter.mass_each_kg * x.inverter.cp_J_kgK))
                state.motor_C[i] += ((point.drives[i].motor_heat_W - qm) * h
                                     / (motors.mass_kg[i] * x.motor.cp_J_kgK))
                transfer = qi + qm
            state.coolant_C[j] += (transfer + l.pump_W - qrad) * h / (l.coolant_kg * c.coolant_cp_J_kgK)
            rejected_J += qrad * h
        left -= h
    return rejected_J / dt, reversible_J / dt
