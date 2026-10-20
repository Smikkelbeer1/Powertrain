"""Battery, inverter and motor electrical model.

Power chain per rotor:   battery DC  ->  inverter  ->  motor  ->  shaft
    P_motor_in = P_shaft / Motor.efficiency   motor heat    = P_motor_in - P_shaft
    P_dc       = P_motor_in + inverter loss   inverter heat = inverter loss

Battery (constant-resistance Thevenin model, Ns cells in series, Np parallel):
    Voc = Ns * OCV(SOC),  R = Ns * R_cell / Np
    P = I * (Voc - I*R)  ->  I = 2P / (Voc + sqrt(Voc^2 - 4RP))
    battery heat = I^2 * R
A negative discriminant Voc^2 - 4RP means the pack cannot deliver that power.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .inputs import ALL, Balancing, Cell, Inputs
from .propulsion import RotorPoint


@dataclass
class DrivePoint:
    """Electrical result for one motor + inverter."""
    dc_W: float = 0.0  # power drawn from the DC bus
    motor_heat_W: float = 0.0
    inverter_heat_W: float = 0.0
    phase_rms_A: float = 0.0


@dataclass
class ElectricalPoint:
    """Electrical result for the whole aircraft at one instant."""
    current_A: float  # pack current
    voltage_V: float  # pack terminal (bus) voltage
    heat_W: float  # battery irreversible heat I^2 R
    min_cell_V: float  # terminal voltage of the weakest cell group
    terminal_W: float  # total power drawn from the battery
    drives: list[DrivePoint]


# -----------------------------------------------------------------------------
# Battery helpers
# -----------------------------------------------------------------------------
def ocv(soc: float, cell: Cell) -> float:
    """Cell open-circuit voltage: linear interpolation in the OCV table."""
    x = min(1.0, max(0.0, soc)) * (len(cell.ocv_V) - 1)
    i = min(int(x), len(cell.ocv_V) - 2)
    return cell.ocv_V[i] + (x - i) * (cell.ocv_V[i + 1] - cell.ocv_V[i])


def section_counts(ns: int) -> list[int]:
    """Series groups in each of the 4 battery sections (one per wing pod)."""
    return [ns // 4 + (1 if i < ns % 4 else 0) for i in ALL]


def board_count(ns: int, balancing: Balancing) -> int:
    """Number of BMS monitor boards (each section rounded up separately)."""
    return sum(math.ceil(n / balancing.channels_per_board) for n in section_counts(ns))


def battery_point(power_W: float, soc: float, weakest_soc: float,
                  ns: int, np: int, x: Inputs) -> tuple[float, float, float, float]:
    """Return (current A, terminal V, heat W, weakest cell terminal V) for a power demand.

    Uses the lower-current (stable) root of the quadratic. The pack OCV uses the
    mean SOC; the weakest group's voltage is checked separately. Cells inside
    a parallel group are assumed to share current equally.
    """
    cell, b = x.cell, x.battery
    voltage = ns * ocv(soc, cell)
    resistance = ns * cell.resistance_ohm * b.resistance_age_factor / np
    discriminant = voltage ** 2 - 4 * resistance * power_W
    if discriminant < 0:
        raise ValueError("Battery equivalent-circuit maximum power exceeded")
    current = 2 * power_W / (voltage + math.sqrt(discriminant)) if power_W else 0.0
    cell_drop = current * resistance / ns
    return (current, voltage - current * resistance, current ** 2 * resistance,
            ocv(weakest_soc, cell) - cell_drop)


# -----------------------------------------------------------------------------
# Motor and inverter
# -----------------------------------------------------------------------------
def inverter_point(x: Inputs, shaft_W: float, voltage: float) -> DrivePoint:
    """Losses and phase current of one motor + inverter at a given bus voltage."""
    if shaft_W <= 0:
        return DrivePoint()
    inv = x.inverter
    motor_W = shaft_W / x.motor.efficiency
    line_rms_V = inv.modulation_fraction * voltage / math.sqrt(2)
    phase_A = motor_W / (math.sqrt(3) * line_rms_V * inv.power_factor)
    if inv.mode == "efficiency":
        loss = motor_W * (1 / inv.efficiency - 1)
    else:
        # Six-switch bridge, n devices in parallel per switch, sinusoidal currents.
        # Switching energy scales linearly with V and I; diode recovery, dead time
        # and temperature dependence are not modelled.
        n = inv.parallel_devices_per_switch
        conduction = 3 * phase_A ** 2 * inv.rds_hot_ohm / n
        avg_device_A = 2 * math.sqrt(2) * phase_A / (math.pi * n)
        switching = (6 * n * inv.switching_Hz * inv.switching_energy_J
                     * (voltage / inv.reference_V) * (avg_device_A / inv.reference_A))
        gate = 6 * n * inv.gate_charge_C * inv.gate_voltage_V * inv.switching_Hz
        loss = conduction + switching + gate + inv.control_power_W
    return DrivePoint(motor_W + loss, motor_W - shaft_W, loss, phase_A)


def electrical(x: Inputs, rotors: list[RotorPoint], other_W: float,
               soc_mean: float, soc_min: float, ns: int, np: int) -> ElectricalPoint:
    """Solve the whole electrical system at one instant.

    Inverter current depends on bus voltage, and bus voltage depends on the
    current drawn, so we iterate (damped fixed point) until they agree.
    ``other_W`` = auxiliaries + pumps + fans (already on the HV bus).
    """
    voltage = ns * ocv(soc_mean, x.cell)
    for _ in range(60):  # iteration limit (NOT seconds)
        drives = [inverter_point(x, r.shaft_W, voltage) for r in rotors]
        power = sum(d.dc_W for d in drives) + other_W
        current, new_V, heat, min_cell = battery_point(power, soc_mean, soc_min, ns, np, x)
        if abs(new_V - voltage) < 1e-5:
            return ElectricalPoint(current, new_V, heat, min_cell, power, drives)
        voltage = (voltage + new_V) / 2
    raise ValueError("Battery/inverter voltage iteration did not converge")


def auxiliary_power(x: Inputs, wingborne: bool, ns: int) -> float:
    """HV-bus power of all low-voltage consumers (through the DC/DC converter)."""
    aux = x.auxiliaries
    duty = aux.actuator_cruise_duty if wingborne else aux.actuator_manoeuvre_duty
    low_voltage_W = (aux.flight_computer_count * aux.flight_computer_each_W + aux.voter_W
                     + aux.sensors_W + aux.communications_W + aux.bms_master_W
                     + board_count(ns, x.balancing) * x.balancing.board_base_W
                     + aux.actuator_count * (duty * aux.actuator_active_W
                                             + (1 - duty) * aux.actuator_idle_W))
    return low_voltage_W / aux.dc_dc_eff
