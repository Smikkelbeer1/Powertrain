"""Mission profile: splits the flight into segments with simple kinematics.

Each segment has constant vertical acceleration ``az`` and constant horizontal
acceleration ``ax``, so altitude and speed at time t inside it are
    h(t)  = h0 + vz0*t + 0.5*az*t^2
    vz(t) = vz0 + az*t
    V(t)  = max(0, v0 + ax*t)

Profile:  take-off hover -> vertical climb to transition height (accelerate,
constant speed, brake) -> transition to wing-borne -> climb -> cruise ->
descent -> back-transition -> landing hover -> vertical descent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

from .inputs import ALL, Inputs


@dataclass
class Segment:
    name: str
    duration_s: float
    h0_m: float  # altitude AGL at segment start
    vz0_m_s: float = 0.0  # vertical speed at start (positive = up)
    az_m_s2: float = 0.0  # vertical acceleration
    v0_m_s: float = 0.0  # horizontal airspeed at start
    ax_m_s2: float = 0.0  # horizontal acceleration
    # "hover"/"descent": rotor-borne; "wing": wing-borne; "transition": power imposed
    mode: str = "hover"
    power_fraction: float = 1.0  # transition only: fraction of motor rating used
    active: tuple[int, ...] = ALL  # which rotors are running

    def altitude(self, t: float) -> float:
        return self.h0_m + self.vz0_m_s * t + 0.5 * self.az_m_s2 * t * t

    def vertical_speed(self, t: float) -> float:
        return self.vz0_m_s + self.az_m_s2 * t

    def speed(self, t: float) -> float:
        return max(0.0, self.v0_m_s + self.ax_m_s2 * t)

    def distance(self) -> float:
        """Horizontal distance flown in this segment [m] (constant acceleration)."""
        T = self.duration_s
        return self.v0_m_s * T + 0.5 * self.ax_m_s2 * T * T


def mission_range_km(segments: list[Segment]) -> float:
    """Total horizontal distance of a mission [km]."""
    return sum(s.distance() for s in segments) / 1000


def mission_segments(x: Inputs) -> list[Segment]:
    """Build the nominal mission from the Mission inputs."""
    m, v = x.mission, x.aircraft.cruise_kmh / 3.6
    # Vertical climb: accelerate, constant speed, brake (symmetric). If the
    # transition height is too low to reach full speed, the profile becomes
    # triangular (accelerate then brake straight away).
    vmax = min(m.vertical_speed_m_s, math.sqrt(m.transition_height_m * m.vertical_accel_m_s2))
    ta = vmax / m.vertical_accel_m_s2  # time to accelerate (and to brake)
    ha = 0.5 * m.vertical_accel_m_s2 * ta ** 2  # height gained while accelerating
    tc = max(0.0, (m.transition_height_m - 2 * ha) / vmax)  # constant-speed time
    h = m.transition_height_m
    result = [
        Segment("takeoff_hover", m.initial_hover_s, 0),
        Segment("vertical_accelerate", ta, 0, az_m_s2=m.vertical_accel_m_s2),
        Segment("vertical_climb", tc, ha, vz0_m_s=vmax),
        Segment("vertical_brake", ta, h - ha, vmax, -m.vertical_accel_m_s2),
        Segment("transition", m.transition_s, h, ax_m_s2=v / m.transition_s,
                mode="transition", power_fraction=m.transition_peak_fraction),
        Segment("cruise_climb", (m.cruise_height_m - h) / m.wing_climb_m_s,
                h, m.wing_climb_m_s, v0_m_s=v, mode="wing"),
        Segment("cruise", m.cruise_s, m.cruise_height_m, v0_m_s=v, mode="wing"),
        Segment("cruise_descent", (m.cruise_height_m - h) / m.wing_descent_m_s,
                m.cruise_height_m, -m.wing_descent_m_s, v0_m_s=v, mode="wing"),
        Segment("back_transition", m.back_transition_s, h, v0_m_s=v,
                ax_m_s2=-v / m.back_transition_s, mode="transition",
                power_fraction=m.back_transition_peak_fraction),
        Segment("landing_hover", m.landing_hover_s, h),
        Segment("vertical_descent", h / m.vertical_descent_m_s, h,
                -m.vertical_descent_m_s, mode="descent"),
    ]
    return [s for s in result if s.duration_s > 0]


def time_steps(s: Segment, dt_max: float) -> Iterator[tuple[float, float, float]]:
    """Yield (elapsed_before, dt, t_mid) for every simulation step in a segment.

    Forces/powers are evaluated at the step MIDPOINT t_mid (midpoint rule).
    """
    elapsed = 0.0
    while elapsed < s.duration_s - 1e-9:
        dt = min(dt_max, s.duration_s - elapsed)
        yield elapsed, dt, elapsed + dt / 2
        elapsed += dt
