"""Time-varying state of the aircraft systems during the simulation."""
from __future__ import annotations

from dataclasses import dataclass

from .inputs import Inputs


@dataclass
class State:
    time_s: float
    soc_mean: float  # average state of charge of all series groups
    soc_min: float  # weakest series group (sets the reserve and voltage limits)
    battery_C: list[float]  # 4 battery sections (lumped average cell temperature)
    motor_C: list[float]  # 4 motors
    inverter_C: list[float]  # 4 inverters
    coolant_C: list[float]  # 8 loops: 0-3 propulsion, 4-7 battery (radiator inlet)


def initial_state(x: Inputs) -> State:
    """Departure state: charged (minus imbalance), everything at initial temperature."""
    spread = x.battery.residual_soc_spread if x.balancing.enabled else x.balancing.initial_soc_spread
    t0 = x.cooling.initial_C
    return State(0.0, x.battery.initial_soc - spread / 2, x.battery.initial_soc - spread,
                 [t0] * 4, [t0] * 4, [t0] * 4, [t0] * 8)
