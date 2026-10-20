"""Rotor thrust/power/torque, aircraft drag and motor sizing.

Physics used (per rotor, T = thrust, A = disc area, FM = figure of merit):
  Hover / vertical climb (momentum theory):
      vi = sqrt((vz/2)^2 + T/(2*rho*A)) - vz/2      induced velocity
      P_shaft = T * (vz + vi) / FM
      rpm from T = CT * rho * n^2 * D^4  (n in rev/s)
  Vertical descent: hover power is used (momentum theory is unreliable in
      vortex-ring state; no energy recovery).
  Wing-borne:
      required thrust = Drag + W*vz/V + m*ax  (+ cooling drag)
      "constant" propeller: P_shaft = thrust_power / cruise_prop_eff
      "coefficients" propeller: rpm solved from CT(J), power from CP(J)
  Transition: NOT solved aerodynamically. Each motor delivers a fixed fraction
      of its rated power and rpm is blended between hover and cruise rpm.
  Torque = P_shaft / omega,  omega = 2*pi*rpm/60.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, replace

from . import motor_family
from .atmosphere import G0, atmosphere
from .inputs import ALL, Aircraft, Inputs, Propeller
from .mission import Segment, mission_segments, time_steps


@dataclass
class RotorPoint:
    """Operating point of one rotor at one instant."""
    thrust_N: float = 0.0
    shaft_W: float = 0.0
    rpm: float = 0.0
    torque_Nm: float = 0.0
    electrical_Hz: float = 0.0
    tip_mach: float = 0.0


@dataclass
class MotorSizing:
    """Result of the motor sizing step (one value per rotor)."""
    power_W: list[float]  # installed peak shaft power
    torque_Nm: list[float]  # installed peak torque
    mass_kg: list[float]  # motor mass (incl. cooling jacket)
    driver: str  # "MTOW" or "torque": which input drove the design


# -----------------------------------------------------------------------------
# Drag (aerodynamics department)
# -----------------------------------------------------------------------------
def drag_N(x: Inputs, weight_N: float, rho: float, speed: float) -> float:
    """Aircraft drag in wing-borne flight (lift = weight assumed)."""
    aero = x.aerodynamics
    if aero.drag_model == "lift_drag":
        return weight_N / aero.lift_drag
    q_S = 0.5 * rho * max(speed, 1.0) ** 2 * aero.wing_area_m2  # dynamic pressure * area
    cl = weight_N / q_S
    return q_S * (aero.cd0 + aero.k_induced * cl ** 2)


# -----------------------------------------------------------------------------
# Propeller (propeller department)
# -----------------------------------------------------------------------------
def prop_coefficients(p: Propeller, J: float) -> tuple[float, float]:
    """CT and CP at advance ratio J, linear in the table (clamped at its ends)."""
    if J <= p.J[0]:
        return p.CT[0], p.CP[0]
    if J >= p.J[-1]:
        return p.CT[-1], p.CP[-1]
    i = bisect.bisect_right(p.J, J) - 1
    f = (J - p.J[i]) / (p.J[i + 1] - p.J[i])
    return (p.CT[i] + f * (p.CT[i + 1] - p.CT[i]),
            p.CP[i] + f * (p.CP[i + 1] - p.CP[i]))


def hover_constants(p: Propeller) -> tuple[float, float]:
    """(CT_hover, figure of merit). From the J=0 table row in coefficient mode.

    FM = ideal power / actual power = CT^1.5 * sqrt(2/pi) / CP  (n in rev/s).
    """
    if p.model == "coefficients":
        ct0, cp0 = p.CT[0], p.CP[0]
        return ct0, ct0 ** 1.5 * math.sqrt(2 / math.pi) / cp0
    return p.ct_hover, p.hover_fm


def solve_cruise_rotor(p: Propeller, thrust: float, speed: float, d: float,
                       rho: float) -> tuple[float, float]:
    """Find (rpm, shaft power) that give ``thrust`` at ``speed`` using CT(J), CP(J).

    Thrust T(n) = rho*n^2*D^4*CT(V/(n*D)) increases with rpm, so bisection works.
    The lowest rpm considered is the one at the last table J (no data beyond it);
    if that already gives too much thrust, that point is used (conservative).
    """
    if thrust <= 0:
        return 0.0, 0.0

    def thrust_at(n: float) -> float:
        return rho * n * n * d ** 4 * prop_coefficients(p, speed / (n * d))[0]

    low = speed / (d * p.J[-1]) if speed > 0 else 1e-6
    if thrust_at(low) >= thrust:
        n = low
    else:
        high = 2 * low
        while thrust_at(high) < thrust:
            high *= 2
            if high > 1e5:
                raise ValueError("Propeller table cannot produce the required cruise thrust")
        for _ in range(80):
            mid = (low + high) / 2
            low, high = (mid, high) if thrust_at(mid) < thrust else (low, mid)
        n = high
    cp = prop_coefficients(p, speed / (n * d))[1]
    return 60 * n, cp * rho * n ** 3 * d ** 5


# -----------------------------------------------------------------------------
# Rotor operating points
# -----------------------------------------------------------------------------
def thrust_fractions(a: Aircraft, active: tuple[int, ...]) -> list[float]:
    """Share of the total thrust carried by each rotor (0 for stopped rotors)."""
    weights = [0.0] * 4
    inner = [i for i in active if i < 2]
    outer = [i for i in active if i >= 2]
    if len(active) == 2:  # emergency pair: fixed inner/outer split
        f = a.emergency_inner_thrust_fraction
    elif a.normal_inner_thrust_fraction > 0:  # user-defined inner/outer split
        f = a.normal_inner_thrust_fraction
    else:  # proportional to disc area (D^2)
        area = [a.diameters_m[i] ** 2 for i in active]
        for i, ai in zip(active, area):
            weights[i] = ai / sum(area)
        return weights
    for i in inner:
        weights[i] = f / len(inner)
    for i in outer:
        weights[i] = (1 - f) / len(outer)
    return weights


def propulsion(x: Inputs, s: Segment, t: float, ratings_W: list[float],
               cooling_drag_W: float = 0.0) -> list[RotorPoint]:
    """Thrust, shaft power, rpm and torque of all four rotors at time t in segment s.

    ``ratings_W`` (installed peak power) is only used in transition segments.
    ``cooling_drag_W`` is the extra power lost to radiator ram drag (wing-borne).
    """
    a, p = x.aircraft, x.propeller
    h = s.altitude(t)
    rho, _, sound = atmosphere(x.mission.field_elevation_m + h, x.cooling.sea_level_ambient_C)
    vz, v = s.vertical_speed(t), s.speed(t)
    W = a.mass_kg * G0
    ct_hover, fm = hover_constants(p)
    weights = thrust_fractions(a, s.active)
    result: list[RotorPoint] = []
    for i in ALL:
        if i not in s.active:
            result.append(RotorPoint())  # stopped rotor
            continue
        frac = weights[i]
        d = a.diameters_m[i]
        if s.mode == "transition":
            # Power command, not a solved force balance. rpm moves linearly (with
            # speed) from the hover rpm to the cruise rpm.
            thrust = W * frac
            hover_rpm = 60 * math.sqrt(thrust / (ct_hover * rho * d ** 4))
            blend = min(1.0, v / (a.cruise_kmh / 3.6))
            rpm = (1 - blend) * hover_rpm + blend * p.cruise_rpm
            if x.mission.transition_power_reference == "hover":
                # Same rotor hovering here: P = T * sqrt(T/(2*rho*A)) / FM
                hover_W = thrust * math.sqrt(thrust / (2 * rho * math.pi * d * d / 4)) / fm
                power = s.power_fraction * hover_W
            else:
                power = s.power_fraction * ratings_W[i]
        elif s.mode == "wing":
            drag = drag_N(x, W, rho, v)
            if p.model == "coefficients":
                total = max(0.0, drag + W * vz / max(v, 1.0) + a.mass_kg * s.ax_m_s2
                            + cooling_drag_W / max(v, 1.0))
                thrust = total * frac
                rpm, power = solve_cruise_rotor(p, thrust, v, d, rho)
            else:
                thrust = max(0.0, drag + W * vz / max(v, 1.0) + a.mass_kg * s.ax_m_s2) * frac
                power = (max(0.0, drag * v + W * vz + a.mass_kg * v * s.ax_m_s2)
                         + cooling_drag_W) * frac / p.cruise_prop_eff
                rpm = p.cruise_rpm if power > 0 else 0.0
        else:  # hover, vertical climb/brake, vertical descent
            thrust = a.mass_kg * max(0.0, G0 + s.az_m_s2) * frac
            vi_sq = thrust / (2 * rho * math.pi * d * d / 4)  # hover induced velocity^2
            axial = max(0.0, vz)  # descent treated as hover (conservative, no regen)
            power = thrust * (axial / 2 + math.sqrt((axial / 2) ** 2 + vi_sq)) / fm
            rpm = 60 * math.sqrt(thrust / (ct_hover * rho * d ** 4))
        omega = rpm * 2 * math.pi / 60
        result.append(RotorPoint(
            thrust_N=thrust, shaft_W=power, rpm=rpm,
            torque_Nm=power / omega if omega else 0.0,
            electrical_Hz=x.motor.pole_pairs * rpm / 60,
            tip_mach=math.hypot(math.pi * d * rpm / 60, v) / sound))
    return result


# -----------------------------------------------------------------------------
# Motor sizing
# -----------------------------------------------------------------------------
def emergency_probes(x: Inputs) -> list[Segment]:
    """Two-rotor emergency hover at cruise height (thinnest air = worst case)."""
    return [Segment("emergency", x.aircraft.emergency_s, x.mission.cruise_height_m,
                    active=tuple(pair)) for pair in x.aircraft.emergency_pairs]


def required_ratings(x: Inputs, segments: list[Segment]) -> tuple[list[float], list[float]]:
    """Peak shaft power [W] and peak torque [Nm] each motor needs at this MTOW.

    1. Power: largest demand over all mission segments plus the emergency
       cases, times ``rating_margin`` (or the user's fixed peak_kW).
    2. Torque: the same probes times the margin.
    With transition_power_reference = "rating" the transition power depends on
    the rating itself, so transitions are left out of step 1 and only their
    torque (at the resulting rating) is added afterwards.
    """
    m = x.motor
    by_rating = x.mission.transition_power_reference == "rating"
    peak_P, peak_Q = [0.0] * 4, [0.0] * 4
    probes = [s for s in segments if not (by_rating and s.mode == "transition")]
    probes += emergency_probes(x)
    for s in probes:
        for t in (0.0, s.duration_s):  # start and end of each segment
            for i, r in enumerate(propulsion(x, s, t, [0.0] * 4)):
                peak_P[i] = max(peak_P[i], r.shaft_W)
                peak_Q[i] = max(peak_Q[i], r.torque_Nm)
    power = [given * 1000 if given > 0 else pk * m.rating_margin
             for given, pk in zip(m.peak_kW, peak_P)]
    torque = [q * m.rating_margin for q in peak_Q]
    # Rating-based transition torque, sampled at exactly the simulation steps.
    for s in segments:
        if by_rating and s.mode == "transition":
            for _, _, t in time_steps(s, x.mission.dt_s):
                for i, r in enumerate(propulsion(x, s, t, power)):
                    torque[i] = max(torque[i], r.torque_Nm)
    return power, torque


def size_motors(x: Inputs, segments: list[Segment]) -> MotorSizing:
    """Power, torque and MASS of the four motors.

    MTOW-driven: torque = what the mission needs; torque-driven: the given
    torque for all motors. Mass then follows from the HPDM trendline (or the
    fixed masses).
    """
    m = x.motor
    power, torque = required_ratings(x, segments)
    driver = "MTOW"
    if m.peak_torque_Nm > 0:
        torque, driver = [m.peak_torque_Nm] * 4, "torque"
    if m.mass_model == "family":
        mass = [motor_family.mass_from_torque(q) for q in torque]
    else:
        mass = list(m.mass_each_kg)
    return MotorSizing(power, torque, mass, driver)


def mtow_for_torque(x: Inputs) -> float:
    """TORQUE-DRIVEN MODE: largest MTOW whose most loaded motor needs exactly
    ``motor.peak_torque_Nm`` (including the rating margin).

    Required torque grows (about linearly) with mass, so a bisection on MTOW
    is used. Only the cheap sizing step runs here, not the full simulation.
    """
    target = x.motor.peak_torque_Nm

    def excess(mass: float) -> float:
        trial = replace(x, aircraft=replace(x.aircraft, mass_kg=mass))
        return max(required_ratings(trial, mission_segments(trial))[1]) - target

    low, high = 1.0, 100.0
    if excess(low) > 0:
        raise ValueError(f"Motor torque {target:g} Nm is too small even for a 1 kg aircraft")
    while excess(high) < 0:
        low, high = high, high * 2
        if high > 1e6:
            raise ValueError("Torque-driven MTOW search did not converge")
    for _ in range(60):
        mid = (low + high) / 2
        low, high = (mid, high) if excess(mid) < 0 else (low, mid)
        if high - low < 1e-6:
            break
    return low
