"""Time simulation of a mission (or an emergency branch) for a given design.

Each time step:
  1. kinematics (altitude, speed) at the step midpoint
  2. radiator airflow, fan power and cooling drag
  3. rotor thrust/power/torque          (propulsion.py)
  4. battery current and voltage         (electrical.py)
  5. SOC update:  dSOC = I*dt / (Np * capacity * SOH)
  6. temperatures                        (cooling.thermal_step)
  7. limit checks -> ``issues``; one output row per step
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any

from .atmosphere import atmosphere
from .cooling import Loop, air_operation, thermal_step
from .electrical import auxiliary_power, electrical
from .inputs import NAMES, Inputs
from .mission import Segment, time_steps
from .propulsion import MotorSizing, propulsion
from .state import State, initial_state

# Issues that mean "battery too small" (used by the automatic Np sizing).
ELECTRICAL_FLAGS = {"SOC reserve", "cell current", "cell voltage", "bus voltage"}


@dataclass
class Simulation:
    rows: list[dict[str, Any]]  # one dict per time step (goes to CSV)
    state: State  # final state
    issues: list[str]  # limits that were exceeded
    checkpoints: list[tuple[str, float, State]]  # (label, altitude, state) per segment end


def simulate(x: Inputs, ns: int, np: int, loops: list[Loop], motors: MotorSizing,
             segments: list[Segment], start: State | None = None,
             thermal: bool = True, stop_on_electrical: bool = False) -> Simulation:
    """Fly ``segments`` starting from ``start`` (default: departure state).

    thermal=False skips temperatures (fast, used during battery sizing).
    stop_on_electrical=True stops at the first electrical limit violation.
    """
    state = deepcopy(start) if start else initial_state(x)
    rows: list[dict[str, Any]] = []
    issues: set[str] = set()
    checkpoints = [("departure", segments[0].h0_m, deepcopy(state))]
    for s in segments:
        for elapsed, dt, t in time_steps(s, x.mission.dt_s):
            alt, speed = s.altitude(t), s.speed(t)
            rho, ambient, _ = atmosphere(x.mission.field_elevation_m + alt, x.cooling.sea_level_ambient_C)
            # Downwash helps the radiators whenever the rotors carry the weight.
            fan, drag, air_fractions, _ = air_operation(x, loops, alt, speed,
                                                        rotor_borne=s.mode != "wing")
            pump = sum(l.pump_W for l in loops)
            aux = auxiliary_power(x, s.mode == "wing", ns)
            rotors = propulsion(x, s, t, motors.power_W, drag)
            point = electrical(x, rotors, aux + pump + fan,
                               state.soc_mean, state.soc_min, ns, np)
            # Coulomb counting: the same charge leaves every series group.
            removed = point.current_A * dt / (np * x.cell.capacity_Ah * x.battery.soh * 3600)
            state.soc_mean -= removed
            state.soc_min -= removed

            electrical_issues: set[str] = set()
            if state.soc_min < x.battery.minimum_soc - 1e-9:
                electrical_issues.add("SOC reserve")
            # Fewer than 4 rotors running = the short two-rotor emergency, which
            # may use the (higher) short-term cell current limit.
            emergency = len(s.active) < 4
            current_limit = x.cell.emergency_max_current_A if emergency else x.cell.max_current_A
            if point.current_A / np > current_limit:
                electrical_issues.add("cell current")
            if point.min_cell_V < x.cell.min_V:
                electrical_issues.add("cell voltage")
            if not x.battery.bus_min_V <= point.voltage_V <= x.battery.bus_max_V:
                electrical_issues.add("bus voltage")
            issues.update(electrical_issues)
            if electrical_issues and stop_on_electrical:
                return Simulation(rows, state, sorted(issues), checkpoints)

            qrad, qrev = (thermal_step(x, state, point, loops, motors, ns, np, ambient, dt, air_fractions)
                          if thermal else (0.0, 0.0))
            state.time_s += dt
            end = elapsed + dt  # time inside the segment at the END of this step

            if max(state.battery_C) > x.cell.temp_limit_C:
                issues.add("battery temperature")
            if max(state.motor_C) > x.motor.limit_C:
                issues.add("motor temperature")
            if max(state.inverter_C) > x.inverter.temp_limit_C:
                issues.add("inverter temperature")
            if min(air_fractions) < 0.99:
                issues.add("fan rating insufficient at altitude")

            row: dict[str, Any] = dict(
                time_s=state.time_s, dt_s=dt, phase=s.name,
                altitude_AGL_m=s.altitude(end), speed_m_s=s.speed(end),
                rho_kg_m3=rho, ambient_C=ambient,
                soc=state.soc_mean, min_group_soc=state.soc_min, DoD=1 - state.soc_mean,
                bus_V=point.voltage_V, pack_A=point.current_A, cell_A=point.current_A / np,
                C_rate=point.current_A / (np * x.cell.capacity_Ah * x.battery.soh),
                battery_terminal_W=point.terminal_W, battery_heat_W=point.heat_W + qrev,
                battery_irreversible_W=point.heat_W, battery_reversible_W=qrev,
                shaft_W=sum(r.shaft_W for r in rotors), pump_W=pump, fan_W=fan,
                auxiliary_W=aux, ram_drag_power_W=drag, radiator_W=qrad,
                minimum_radiator_airflow_fraction=min(air_fractions),
                motor_heat_W=sum(d.motor_heat_W for d in point.drives),
                inverter_heat_W=sum(d.inverter_heat_W for d in point.drives),
                battery_C=max(state.battery_C), motor_C=max(state.motor_C),
                inverter_C=max(state.inverter_C))
            # Per-rotor columns and per-rotor limit checks
            for i, (r, d) in enumerate(zip(rotors, point.drives)):
                if r.shaft_W > motors.power_W[i] * 1.00001:
                    issues.add("motor peak power rating")
                if r.torque_Nm > motors.torque_Nm[i] * 1.00001:
                    issues.add("motor peak torque rating")
                if r.electrical_Hz > x.motor.electrical_Hz_limit:
                    issues.add("motor electrical frequency limit")
                if r.tip_mach > x.aircraft.tip_mach_limit:
                    issues.add("indicative rotor tip Mach limit")
                if 0 < x.inverter.phase_rms_limit_A < d.phase_rms_A:
                    issues.add("inverter phase current rating")
                for key, value in asdict(r).items():
                    row[NAMES[i] + "_" + key] = value
                row[NAMES[i] + "_phase_rms_A"] = d.phase_rms_A
                row[NAMES[i] + "_motor_C"] = state.motor_C[i]
                row[NAMES[i] + "_inverter_C"] = state.inverter_C[i]
                row[NAMES[i] + "_battery_C"] = state.battery_C[i]
                row[NAMES[i] + "_prop_coolant_C"] = state.coolant_C[i]
                row[NAMES[i] + "_battery_coolant_C"] = state.coolant_C[i + 4]
            rows.append(row)
        checkpoints.append(("after_" + s.name, s.altitude(s.duration_s), deepcopy(state)))
    return Simulation(rows, state, sorted(issues), checkpoints)


def metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Summary numbers of a simulation (energies in kWh, peaks, end SOC)."""
    if not rows:
        return {}
    return dict(
        terminal_energy_kWh=sum(r["battery_terminal_W"] * r["dt_s"] for r in rows) / 3.6e6,
        auxiliary_energy_kWh=sum(r["auxiliary_W"] * r["dt_s"] for r in rows) / 3.6e6,
        cooling_energy_kWh=sum((r["pump_W"] + r["fan_W"]) * r["dt_s"] for r in rows) / 3.6e6,
        peak_terminal_kW=max(r["battery_terminal_W"] for r in rows) / 1000,
        peak_pack_A=max(r["pack_A"] for r in rows),
        end_soc=rows[-1]["soc"], end_min_group_soc=rows[-1]["min_group_soc"],
        min_bus_V=min(r["bus_V"] for r in rows), peak_cell_A=max(r["cell_A"] for r in rows),
        peak_battery_C=max(r["battery_C"] for r in rows),
        peak_motor_C=max(r["motor_C"] for r in rows),
        peak_inverter_C=max(r["inverter_C"] for r in rows))
